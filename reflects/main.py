from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, constr
from typing import Optional, Literal
from datetime import datetime

from reflects.db import get_db_connection
from reflects.auth import create_access_token, get_current_user
from reflects.redis_client import hybrid_rate_limiter
from reflects.s3_utils import upload_to_s3  # you’ll define this below
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Or ["*"] if you want wide open for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 1. User Management ---

class UserCreate(BaseModel):
    name: constr(min_length=1, max_length=50)
    email: EmailStr
    password: constr(min_length=6, max_length=100)
    role: Literal["student", "teacher"]

@app.post("/create-user")
def create_user(user: UserCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (user.name.strip(), user.email.lower(), user.password, user.role)
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
        result = cur.fetchone()
        if not result or result[1] != form_data.password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user_id, _, role = result
        access_token = create_access_token({"user_id": user_id, "role": role})
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        cur.close()
        conn.close()

#@app.get("/me")
#def read_me(user = Depends(get_current_user)):
#    return {"user_id": user["user_id"], "role": user["role"]}

@app.get("/me")
def read_me(user = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT email FROM users WHERE id = %s", (user["user_id"],))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        email = result[0]
        return {
            "user_id": user["user_id"],
            "role": user["role"],
            "email": email  # ✅ Now email is included
        }
    finally:
        cur.close()
        conn.close()


class UserUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=50)] = None
    password: Optional[constr(min_length=6, max_length=100)] = None

@app.patch("/update-user")
def update_user(updates: UserUpdate, user = Depends(get_current_user)):
    if not updates.name and not updates.password:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if updates.name:
            cur.execute("UPDATE users SET name = %s WHERE id = %s", (updates.name.strip(), user["user_id"]))
        if updates.password:
            cur.execute("UPDATE users SET password = %s WHERE id = %s", (updates.password, user["user_id"]))
        conn.commit()
        return {"message": "User updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- Reflections ---
class ReflectionCreate(BaseModel):
    chapter_id: int
    video_url: constr(min_length=10, max_length=300)
    text_summary: Optional[constr(max_length=500)] = None


from fastapi import Form, File, UploadFile

ENV = os.getenv("ENV", "local")  # set ENV=production on your EC2/s3 setup

@app.post("/submit-reflection")
def submit_reflection(
    chapter_id: int = Form(...),
    text_summary: str = Form(None),
    video_file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    if not hybrid_rate_limiter(user["user_id"], "reflection", 30):
        raise HTTPException(status_code=429, detail="Reflection rate limit reached.")

    if ENV == "production":
        # ✅ Upload to S3
        video_url = upload_to_s3(video_file, f"{user['user_id']}_{chapter_id}")
    else:
        # ✅ Save locally
        os.makedirs("uploads", exist_ok=True)
        filename = f"{user['user_id']}_{chapter_id}_{video_file.filename}"
        file_path = f"uploads/{filename}"
        with open(file_path, "wb") as f:
            f.write(video_file.file.read())
        video_url = f"/uploads/{filename}"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO reflections (user_id, chapter_id, video_url, text_summary, submitted_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user["user_id"],
            chapter_id,
            video_url,
            text_summary.strip() if text_summary else None,
            datetime.utcnow()
        ))
        conn.commit()
        return {"message": "Reflection submitted successfully"}
    except Exception as e:
        conn.rollback()
        if "unique_user_chapter" in str(e):
            raise HTTPException(status_code=400, detail="You’ve already submitted for this chapter.")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()



@app.get("/chapters")
def get_chapters():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM chapters ORDER BY id")
        chapters = [{"id": row[0], "name": row[1]} for row in cur.fetchall()]
        return chapters
    finally:
        cur.close()
        conn.close()


from typing import List

class ReflectionOut(BaseModel):
    id: int
    chapter_id: int
    video_url: str
    text_summary: Optional[str]
    submitted_at: str

@app.get("/my-reflections")
def get_my_reflections(user = Depends(get_current_user)):
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
        reflections = [
            {
                "chapter": row[1],
                "video_url": row[2],
                "summary": row[3],
                "submitted_at": row[4].isoformat()
            }
            for row in cur.fetchall()
        ]
        return reflections
    finally:
        cur.close()
        conn.close()



from fastapi import Query

@app.get("/all-reflections")
def get_all_reflections(
    subject: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    user = Depends(get_current_user)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT r.id, u.email, r.chapter_id, r.video_url, r.text_summary, r.submitted_at
            FROM reflections r
            JOIN users u ON r.user_id = u.id
            WHERE 1=1
        """
        params = []
        if subject:
            query += " AND r.chapter_id::text = %s"  # assuming chapter_id = subject mapping
            params.append(subject)
        if email:
            query += " AND u.email = %s"
            params.append(email)

        query += " ORDER BY r.submitted_at DESC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "email": r[1],
                "chapter_id": r[2],
                "video_url": r[3],
                "text_summary": r[4],
                "submitted_at": r[5].isoformat()
            } for r in rows
        ]
    finally:
        cur.close()
        conn.close()


# --- Feedback ---
class FeedbackCreate(BaseModel):
    reflection_id: int
    status: Literal['understood', 'needs_review']
    comment: Optional[constr(max_length=500)] = None

@app.post("/teacher/feedback")
def give_feedback(feedback: FeedbackCreate, user = Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can give feedback")

    if not hybrid_rate_limiter(user["user_id"], "feedback", 20):
        raise HTTPException(status_code=429, detail="Feedback rate limit reached.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO feedback (reflection_id, teacher_id, status, comment)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (reflection_id) DO UPDATE
            SET status = EXCLUDED.status,
                comment = EXCLUDED.comment,
                updated_at = CURRENT_TIMESTAMP
        """, (
            feedback.reflection_id,
            user["user_id"],
            feedback.status,
            feedback.comment.strip() if feedback.comment else None
        ))
        conn.commit()
        return {"message": "Feedback recorded"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


from fastapi import Query

@app.get("/teacher/feedback")
def get_teacher_feedback(
    email: Optional[str] = Query(None),
    chapter_id: Optional[int] = Query(None),
    status: Optional[Literal["understood", "needs_review"]] = Query(None),
    user = Depends(get_current_user)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view this.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
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

        if chapter_id is not None:
            query += " AND r.chapter_id = %s"
            params.append(chapter_id)

        if status:
            query += " AND f.status = %s"
            params.append(status)

        query += " ORDER BY f.updated_at DESC"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return [
            {
                "feedback_id": r[0],
                "student_email": r[1],
                "chapter_id": r[2],
                "video_url": r[3],
                "status": r[4],
                "comment": r[5],
                "updated_at": r[6].isoformat() if r[6] else None
            } for r in rows
        ]
    finally:
        cur.close()
        conn.close()
