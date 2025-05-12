from fastapi import FastAPI, HTTPException, Depends, Form, File, UploadFile, Query, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional, Literal
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from passlib.context import CryptContext
import os
import re

from reflects.db import get_db_connection
from reflects.auth import create_access_token, get_current_user
from reflects.redis_client import hybrid_rate_limiter
from reflects.auth import hash_password
from reflects.auth import verify_password

app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Models -----
class UserCreate(BaseModel):
    name: constr(min_length=1, max_length=50)
    email: EmailStr
    password: constr(min_length=8, max_length=100)  # enforce strong minimum
    role: Literal["student", "teacher"]

    @validator("password")
    def password_strength(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must include at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must include at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must include at least one special character.")
        return v

class UserUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=50)]
    password: Optional[constr(min_length=6, max_length=100)]

class FeedbackCreate(BaseModel):
    reflection_id: int
    status: Literal['understood', 'needs_review']
    comment: Optional[constr(max_length=500)]

class SubjectCreate(BaseModel):
    name: constr(min_length=1, max_length=100)

class SubjectUpdate(BaseModel):
    name: constr(min_length=1, max_length=100)

class ChapterCreate(BaseModel):
    title: constr(min_length=1, max_length=100)

class ChapterUpdate(BaseModel):
    title: constr(min_length=1, max_length=100)

# ----- Environment Config -----
ENV = os.getenv("ENV", "local")
AZURE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "uploads")
AZURE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# ----- Utility Functions -----
def upload_to_azure(file, object_name: str):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER)
        blob_client = container_client.get_blob_client(object_name)
        blob_client.upload_blob(file.file, overwrite=True)
    except Exception as e:
        raise Exception(f"Azure upload failed: {str(e)}")

def get_sas_url(blob_name: str):
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONN_STR)
    blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob=blob_name)
    return blob_client.url


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ----- Routes -----
@app.get("/test-version")
def test_version():
    return {"version": "api-docs-fix"}

@app.post("/create-user")
def create_user(user: UserCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        hashed_pw = hash_password(user.password)
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (user.name.strip(), user.email.lower(), hashed_pw, user.role)
        )
        conn.commit()
        return {"message": "User created successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, password, role FROM users WHERE email = %s", (form_data.username,))
        user = cur.fetchone()
        if not user or not verify_password(form_data.password, user[1]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token({"user_id": user[0], "role": user[2]})
        return {"access_token": token, "token_type": "bearer"}
    finally:
        cur.close()
        conn.close()

@app.get("/me")
def read_me(user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT email FROM users WHERE id = %s", (user["user_id"],))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return {**user, "email": result[0]}
    finally:
        cur.close()
        conn.close()

@app.patch("/update-user")
def update_user(updates: UserUpdate, user=Depends(get_current_user)):
    if not updates.name and not updates.password:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if updates.name:
            cur.execute("UPDATE users SET name = %s WHERE id = %s", (updates.name.strip(), user["user_id"]))
        if updates.password:
            hashed_pw = hash_password(updates.password)
            cur.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_pw, user["user_id"]))
        conn.commit()
        return {"message": "User updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/submit-reflection")
def submit_reflection(
    chapter_id: int = Form(...),
    text_summary: str = Form(None),
    video_file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    if not hybrid_rate_limiter(user["user_id"], "reflection", 30):
        raise HTTPException(status_code=429, detail="Reflection rate limit reached.")

    file_name = f"{user['user_id']}_{chapter_id}_{video_file.filename}"

    if ENV == "production":
        upload_to_azure(video_file, file_name)
    else:
        os.makedirs("uploads", exist_ok=True)
        with open(f"uploads/{file_name}", "wb") as f:
            f.write(video_file.file.read())

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO reflections (user_id, chapter_id, video_url, text_summary, submitted_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user["user_id"], chapter_id, file_name, text_summary.strip() if text_summary else None, datetime.utcnow()))
        conn.commit()
        return {"message": "Reflection submitted successfully"}
    except Exception as e:
        conn.rollback()
        if "unique_user_chapter" in str(e):
            raise HTTPException(status_code=400, detail="Already submitted for this chapter.")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/my-reflections")
def get_my_reflections(user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT r.chapter_id, c.name, r.video_url, r.text_summary, r.submitted_at
            FROM reflections r
            JOIN chapters c ON r.chapter_id = c.id
            WHERE r.user_id = %s
            ORDER BY r.submitted_at DESC
        """, (user["user_id"],))
        return [{
            "chapter": row[1],
            "video_url": get_sas_url(row[2]),
            "summary": row[3],
            "submitted_at": row[4].isoformat()
        } for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

@app.get("/chapters")
def get_chapters():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM chapters ORDER BY id")
        return [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@app.get("/subjects")
def get_subjects(user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM subjects ORDER BY name")
        return [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@app.post("/subjects")
def create_subject(subject: SubjectCreate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can create subjects")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO subjects (name) VALUES (%s) RETURNING id", (subject.name.strip(),))
        conn.commit()
        return {"id": cur.fetchone()[0], "name": subject.name}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.patch("/subjects/{subject_id}")
def update_subject(subject_id: int, updates: SubjectUpdate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can update subjects")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE subjects SET name = %s WHERE id = %s", (updates.name.strip(), subject_id))
        conn.commit()
        return {"message": "Subject updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can delete subjects")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
        conn.commit()
        return {"message": "Subject deleted"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.get("/subjects/{subject_id}/chapters")
def get_chapters_for_subject(subject_id: int, user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title FROM chapters WHERE subject_id = %s ORDER BY id", (subject_id,))
        return [{"id": row[0], "title": row[1]} for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@app.post("/subjects/{subject_id}/chapters")
def create_chapter(subject_id: int, chapter: ChapterCreate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can create chapters")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO chapters (subject_id, title) VALUES (%s, %s) RETURNING id",
            (subject_id, chapter.title.strip())
        )
        conn.commit()
        return {"id": cur.fetchone()[0], "title": chapter.title}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.patch("/chapters/{chapter_id}")
def update_chapter(chapter_id: int, updates: ChapterUpdate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can update chapters")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE chapters SET title = %s WHERE id = %s", (updates.title.strip(), chapter_id))
        conn.commit()
        return {"message": "Chapter updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: int, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can delete chapters")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM chapters WHERE id = %s", (chapter_id,))
        conn.commit()
        return {"message": "Chapter deleted"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()
        

@app.get("/students/emails")
def get_student_emails(user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT email FROM users WHERE role = 'student'")
        return [row[0] for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

@app.get("/all-reflections")
def get_all_reflections(subject: Optional[str] = Query(None), email: Optional[str] = Query(None), user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    query = """
        SELECT r.id, u.email, r.chapter_id, r.video_url, r.text_summary, r.submitted_at,
               f.status, f.comment
        FROM reflections r
        JOIN users u ON r.user_id = u.id
        LEFT JOIN feedback f ON r.id = f.reflection_id
        WHERE 1=1
    """
    params = []
    if subject:
        query += " AND r.chapter_id::text = %s"
        params.append(subject)
    if email:
        query += " AND u.email = %s"
        params.append(email)

    query += " ORDER BY r.submitted_at DESC"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, tuple(params))
        return [{
            "id": r[0], "email": r[1], "chapter_id": r[2], "video_url": get_sas_url(r[3]),
            "text_summary": r[4], "submitted_at": r[5].isoformat(),
            "status": r[6], "comment": r[7],
        } for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

@app.post("/teacher/feedback")
def submit_feedback(data: FeedbackCreate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can give feedback")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO feedback (reflection_id, teacher_id, status, comment, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (reflection_id) DO UPDATE
            SET status = EXCLUDED.status, comment = EXCLUDED.comment, updated_at = NOW()
        """, (data.reflection_id, user["user_id"], data.status, data.comment))
        conn.commit()
        return {"message": "Feedback saved"}
    finally:
        cur.close()
        conn.close()

@app.get("/teacher/feedback")
def get_teacher_feedback(
    email: Optional[str] = Query(None),
    chapter_id: Optional[int] = Query(None),
    status: Optional[Literal["understood", "needs_review"]] = Query(None),
    user=Depends(get_current_user)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    query = """
        SELECT f.id, u.email, r.chapter_id, r.video_url, f.status, f.comment, f.updated_at
        FROM feedback f
        JOIN reflections r ON f.reflection_id = r.id
        JOIN users u ON r.user_id = u.id
        WHERE f.teacher_id = %s
    """
    params = [user["user_id"]]

    if email:
        query += " AND u.email = %s"
        params.append(email)
    if chapter_id:
        query += " AND r.chapter_id = %s"
        params.append(chapter_id)
    if status:
        query += " AND f.status = %s"
        params.append(status)

    query += " ORDER BY f.updated_at DESC"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, tuple(params))
        return [{
            "feedback_id": r[0],
            "student_email": r[1],
            "chapter_id": r[2],
            "video_url": get_sas_url(r[3]),
            "status": r[4],
            "comment": r[5],
            "updated_at": r[6].isoformat() if r[6] else None
        } for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()
