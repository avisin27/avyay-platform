# Avyay Reflects  
A reflection-based learning platform that prioritizes deep thinking, student introspection, and guided feedback.

---

## Overview

**Avyay Reflects** is a web platform where students submit reflections (via video or optional summaries) on what they’ve learned, and teachers provide structured feedback. It enables thoughtful, asynchronous learning and encourages reflection as a daily practice — rather than rote memorization.

"Avyay" means imperishable in Sanskrit, aligning with our mission to make learning meaningful and lasting.

---

## Features

### For Students
- Submit chapter-wise reflections (video + optional summary)
- View personal reflection history, organized by subject and chapter
- Submit up to 3 reflections/day (or every 24h via sliding window)
- Protected submission limits to ensure quality over quantity

### For Teachers
- Create, update, and delete subjects and chapters
- View all student reflections with advanced filters (by subject, chapter, or email)
- Provide categorized feedback: "understood" or "needs review"
- Update previous feedback
- Soft-delete users and content (mark as obsolete rather than hard-deleting)

---

## Tech Stack

**Backend:**
- FastAPI for API logic and routing
- PostgreSQL for data storage (accessed via `psycopg2`)
- Redis for hybrid rate limiting (fixed and sliding window logic)
- Azure Blob Storage for video file storage with signed SAS access
- JWT for authentication and role-based access control

**Frontend:**
- TailwindCSS for responsive and elegant UI
- HTML + Vanilla JavaScript (no frontend framework)
- Role-based dashboard routing and dynamic UI components

**DevOps & Security:**
- GitHub Actions for CI (linting, testing, and builds)
- Branch protection rules
- Secrets handled via environment variables and `.env`
- Redis connections use SSL
- SAS URLs for secure file access
- Soft-deletion system with `obsolete` flags across resources

---

## How to Log In (Test Accounts)

Use these credentials to explore the platform:

### Teacher
- **Email:** `teacher@example.com`
- **Password:** `Avyay@123`

### Student
- **Email:** `student@example.com`
- **Password:** `Avyay@123`

---

## Platform Flow — How to Test Each Feature

### As a **Student**:
1. **Login** at `login.html`
2. Go to:
   - `submit.html` → Upload a reflection video (with optional summary)
   - `my-reflections.html` → See your submission history, filtered by subject
3. View feedback from teachers when available

### As a **Teacher**:
1. **Login** at `login.html`
2. Go to:
   - `curriculum.html` → Add or update subjects and chapters
   - `teacher-refs.html` → Browse and filter all student reflections
   - `students.html` → Manage student accounts (edit/delete)
   - `teacher-feedback.html` → View/update feedback history

---

## Code Structure

backend/
├── main.py # FastAPI app
├── auth.py # JWT auth, password hashing/verification
├── db.py # PostgreSQL connection
├── redis_client.py # Rate limiter (fixed + sliding window)
├── models.py # Pydantic schemas

frontend/
├── login.html
├── dashboard.html
├── curriculum.html
├── submit.html
├── my-reflections.html
├── teacher-refs.html
├── students.html
├── styles.css # Tailwind-based styles



---

## Engineering Highlights

| Area         | Description |
|--------------|-------------|
| **FastAPI**  | Role-based routing, JWT, OAuth2, modular APIs |
| **Redis**    | Implemented hybrid sliding and fixed window rate limiter |
| **Azure**    | Secure file uploads via signed SAS tokens |
| **CI/CD**    | GitHub Actions pipeline for PR checks, linting, testing |
| **Security** | Secrets via `.env`, SSL Redis, no hardcoded credentials |
| **Frontend** | Pure HTML + Tailwind with JS fetch, no frameworks |
| **Dev Practice** | Branch protection rules, review flow, conventional commits |

---

## Areas for Improvement

| Category                  | Improvement Needed |
|---------------------------|--------------------|
| **Testing**               | Add end-to-end and backend unit tests |
| **File upload**           | Enforce max size & accepted formats |
| **Test containers**       | Use separate Kubernetes namespaces |
| **CI/CD Templates**       | Add reusable workflows for PRs and deployments |
| **Rate limit switching**  | Automate fixed/sliding mode switching based on calendar or load |
| **Pagination**            | Add pagination to large lists (e.g., reflections, feedback) |
| **Obsolete filtering**    | UI/Backend toggle to view or hide obsolete reflections |

---

## Vision

Avyay Reflects isn’t just a learning app — it’s a step toward humanizing education. It makes space for **slower, deeper reflection** and gives teachers the tools to guide with precision and care. The platform is designed to be lightweight, aesthetic, and extensible — blending technical rigor with educational empathy.

---
