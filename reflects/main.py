from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime

from reflects.db import get_db_connection
from reflects.auth import create_access_token, get_current_user

app = FastAPI()

# 1. Create user
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str  # "student" or "teacher"

@app.post("/create-user")
def create_user(user: UserCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (user.name, user.email, user.password, user.role)
        )
        conn.commit()
        return {"message": "User created successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# 2. Login
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

# 3. Get current user info
@app.get("/me")
def read_me(user = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "role": user["role"]
    }


from typing import Optional

class ReflectionCreate(BaseModel):
    chapter_id: int
    video_url: str
    text_summary: Optional[str] = None

@app.post("/submit-reflection")
def submit_reflection(reflection: ReflectionCreate, user = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO reflections (user_id, chapter_id, video_url, text_summary, submitted_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user["user_id"],
            reflection.chapter_id,
            reflection.video_url,
            reflection.text_summary,
            datetime.utcnow()
        ))
        conn.commit()
        return {"message": "Reflection submitted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

from typing import Literal

class FeedbackCreate(BaseModel):
    reflection_id: int
    status: Literal['understood', 'needs_review']
    comment: Optional[str] = None

@app.post("/teacher/feedback")
def give_feedback(feedback: FeedbackCreate, user = Depends(get_current_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can give feedback")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # If feedback already exists, update it
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
            feedback.comment
        ))
        conn.commit()
        return {"message": "Feedback recorded"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

from typing import Optional

class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None

@app.patch("/update-user")
def update_user(updates: UserUpdate, user = Depends(get_current_user)):
    if not updates.name and not updates.password:
        raise HTTPException(status_code=400, detail="Nothing to update.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if updates.name:
            cur.execute("UPDATE users SET name = %s WHERE id = %s", (updates.name, user["user_id"]))
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
