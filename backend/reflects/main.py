from fastapi import FastAPI, HTTPException, Depends, Form, File, UploadFile, Query, Body
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, constr, validator
from typing import Optional, Literal
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
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
    name: constr(min_length=1, max_length=100)

class ChapterUpdate(BaseModel):
    name: constr(min_length=1, max_length=100)

# Patch: Add validator to StudentUpdate for password strength
class StudentUpdate(BaseModel):
    name: Optional[str]
    password: Optional[str]

    @validator("password")
    def password_strength(cls, v):
        if v is None:
            return v
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must include at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must include at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must include at least one special character.")
        return v


# Patch: Health check endpoint
@app.get("/healthz")
def health_check():
    return {"status": "ok"}

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

    # Get the storage account key from an env variable
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_key:
        raise RuntimeError("AZURE_STORAGE_ACCOUNT_KEY is not set in environment variables.")

    sas_token = generate_blob_sas(
        account_name=blob_client.account_name,
        container_name=blob_client.container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )

    return f"{blob_client.url}?{sas_token}"



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
        cur.execute("SELECT name, email FROM users WHERE id = %s", (user["user_id"],))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return {**user, "name": result[0], "email": result[1]}
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


# Patch: Alternative route for frontend compatibility
@app.delete("/delete-user")
def delete_user(email: str = Query(...), user=Depends(get_current_user)):
    return delete_student(email=email, user=user)


# Patch: Override delete_student to mark reflections and feedback as obsolete
@app.delete("/students/{email}")
def delete_student(email: str, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can delete students")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE email = %s AND role = 'student'", (email,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        student_id = student[0]

        # Delete all feedback related to the student
        cur.execute("""
            DELETE FROM feedback
            WHERE reflection_id IN (SELECT id FROM reflections WHERE user_id = %s)
        """, (student_id,))

        # Delete all reflections by the student
        cur.execute("DELETE FROM reflections WHERE user_id = %s", (student_id,))

        # Delete the student account
        cur.execute("DELETE FROM users WHERE id = %s", (student_id,))

        conn.commit()
        return {"message": f"Student {email} and all their data have been permanently deleted."}
    finally:
        cur.close()
        conn.close()



class StudentUpdate(BaseModel):
    name: Optional[str]
    password: Optional[str]

@app.patch("/students/{email}")
def update_student(email: str, updates: StudentUpdate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can update students")
    if not updates.name and not updates.password:
        raise HTTPException(status_code=400, detail="Nothing to update")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if updates.name:
            cur.execute("UPDATE users SET name = %s WHERE email = %s AND role = 'student'", (updates.name.strip(), email))
        if updates.password:
            hashed_pw = hash_password(updates.password)
            cur.execute("UPDATE users SET password = %s WHERE email = %s AND role = 'student'", (hashed_pw, email))
        conn.commit()
        return {"message": f"Student {email} updated successfully"}
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
    if not hybrid_rate_limiter(user["user_id"], "reflection", 10):
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
def get_my_reflections(
    subject_id: Optional[int] = Query(None),
    user=Depends(get_current_user)
):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT r.chapter_id, c.name, r.video_url, r.text_summary, r.submitted_at, r.obsolete
            FROM reflections r
            JOIN chapters c ON r.chapter_id = c.id
            WHERE r.user_id = %s AND r.obsolete = FALSE AND c.obsolete = FALSE
        """
        params = [user["user_id"]]

        if subject_id:
            query += " AND c.subject_id = %s"
            params.append(subject_id)

        query += " ORDER BY r.submitted_at DESC"
        cur.execute(query, tuple(params))

        return [{
            "chapter": row[1],
            "video_url": get_sas_url(row[2]),
            "summary": row[3],
            "submitted_at": row[4].isoformat(),
            "obsolete": row[5]
        } for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@app.get("/chapters")
def get_chapters():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM chapters WHERE obsolete = FALSE ORDER BY id")
        return [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()


@app.get("/subjects")
def get_subjects(user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM subjects WHERE obsolete = FALSE ORDER BY name")
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
        cur.execute("UPDATE subjects SET obsolete = TRUE WHERE id = %s", (subject_id,))
        cur.execute("UPDATE chapters SET obsolete = TRUE WHERE subject_id = %s", (subject_id,))
        cur.execute("""
            UPDATE reflections SET obsolete = TRUE 
            WHERE chapter_id IN (SELECT id FROM chapters WHERE subject_id = %s)
        """, (subject_id,))
        cur.execute("""
            UPDATE feedback SET obsolete = TRUE
            WHERE reflection_id IN (
                SELECT r.id FROM reflections r
                JOIN chapters c ON r.chapter_id = c.id
                WHERE c.subject_id = %s
            )
        """, (subject_id,))
        conn.commit()
        return {"message": "Subject marked as obsolete"}
    finally:
        cur.close()
        conn.close()


@app.get("/subjects/{subject_id}/chapters")
def get_chapters_for_subject(subject_id: int, user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM chapters WHERE subject_id = %s AND obsolete = FALSE ORDER BY id", (subject_id,))
        return [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
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
            "INSERT INTO chapters (subject_id, name) VALUES (%s, %s) RETURNING id",
            (subject_id, chapter.name.strip())
        )
        conn.commit()
        return {"id": cur.fetchone()[0], "name": chapter.name}
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
        cur.execute("UPDATE chapters SET name = %s WHERE id = %s", (updates.name.strip(), chapter_id))
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
        cur.execute("UPDATE chapters SET obsolete = TRUE WHERE id = %s", (chapter_id,))
        cur.execute("UPDATE reflections SET obsolete = TRUE WHERE chapter_id = %s", (chapter_id,))
        cur.execute("""
            UPDATE feedback SET obsolete = TRUE 
            WHERE reflection_id IN (
                SELECT id FROM reflections WHERE chapter_id = %s
            )
        """, (chapter_id,))
        conn.commit()
        return {"message": "Chapter marked as obsolete"}
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
def get_all_reflections(
    email: Optional[str] = Query(None),
    subject_id: Optional[int] = Query(None),
    chapter_id: Optional[int] = Query(None),
    user=Depends(get_current_user)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    query = """
        SELECT 
            r.id, 
            u.email, 
            r.chapter_id, 
            r.video_url, 
            r.text_summary, 
            r.submitted_at,
            f.status, 
            f.comment,
            r.obsolete AS reflection_obsolete,
            c.obsolete AS chapter_obsolete,
            s.obsolete AS subject_obsolete,
            c.name AS chapter_name,
            s.name AS subject_name
        FROM reflections r
        JOIN users u ON r.user_id = u.id
        LEFT JOIN feedback f ON r.id = f.reflection_id
        JOIN chapters c ON r.chapter_id = c.id
        JOIN subjects s ON c.subject_id = s.id
        WHERE (f.obsolete = FALSE OR f.obsolete IS NULL)
    """
    params = []

    if email:
        query += " AND u.email = %s"
        params.append(email)

    if chapter_id:
        query += " AND r.chapter_id = %s"
        params.append(chapter_id)

    elif subject_id:
        # Get chapter IDs for this subject
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM chapters WHERE subject_id = %s", (subject_id,))
            chapter_ids = [row[0] for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

        if not chapter_ids:
            return []  # No chapters = no reflections

        query += " AND r.chapter_id = ANY(%s)"
        params.append(chapter_ids)

    query += " ORDER BY r.submitted_at DESC"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, tuple(params))
        return [{
            "id": r[0],
            "email": r[1],
            "chapter_id": r[2],
            "video_url": get_sas_url(r[3]),
            "text_summary": r[4],
            "submitted_at": r[5].isoformat(),
            "status": r[6],
            "comment": r[7],
            "reflection_obsolete": r[8],
            "chapter_obsolete": r[9],
            "subject_obsolete": r[10],
            "chapter_name": r[11],
            "subject_name": r[12],
        } for r in cur.fetchall()]
    finally:
        cur.close()
        conn.close()



@app.post("/teacher/feedback")
def submit_feedback(data: FeedbackCreate, user=Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can give feedback")

    if not hybrid_rate_limiter(user["user_id"], "feedback", 20):
        raise HTTPException(status_code=429, detail="Feedback rate limit reached.")

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
        JOIN chapters c ON r.chapter_id = c.id
        WHERE f.teacher_id = %s AND f.obsolete = FALSE AND r.obsolete = FALSE AND c.obsolete = FALSE
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
