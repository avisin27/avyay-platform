
# 🌿 Avyay Reflects

*A reflection-based learning platform that prioritizes deep thinking, student introspection, and guided feedback.*

---

### ✨ Overview

**Avyay Reflects** enables students to submit subject-wise reflections in video or text form and receive structured, thoughtful feedback from teachers. Designed for asynchronous learning, it transforms daily education into a meaningful journey of introspection and personal growth.

> **“Avyay”** means *imperishable* in Sanskrit — reflecting our mission to create learning that lasts.

---

### 🧠 Key Features

#### 👩‍🎓 For Students

* 📹 Submit chapter-wise video reflections (with optional summary)
* 📜 View personal reflection history, filtered by subject and chapter
* ⏱️ Rate-limited submissions (10 per day or 10 every 24h via hybrid model)
* 🛡️ Quality guardrails via Redis-powered rate limiting

#### 👨‍🏫 For Teachers

* 📚 Create, update, and delete students, subjects and chapters
* 🔎 View all reflections with advanced filters (subject, chapter, student email)
* ⏱️ Rate-limited submissions (10 per day or 10 every 24h via hybrid model)
* 💬 Provide categorized feedback ("Understood" / "Needs Review")
* 🔁 Update past feedback entries
* 🗃️ Soft-delete users and content for auditability and resilience

---

### ⚙️ Tech Stack

#### 🔧 Backend

* **FastAPI** — Modern, async Python API framework
* **PostgreSQL** — Relational DB (via `psycopg2`)
* **Redis** — Hybrid fixed + sliding window rate limiter
* **Azure Blob Storage** — Video storage via signed SAS URLs
* **JWT** — Auth with role-based access (student, teacher)
* **Containerized** — Dockerized backend, deployed via Kubernetes

#### 💻 Frontend

* **HTML + TailwindCSS + Vanilla JS** — No frontend framework
* **Responsive UI** with dynamic content loading via JS `fetch`
* **Containerized** — Static frontend served via NGINX container

#### 🛰️ Infrastructure & Deployment

* **Kubernetes Cluster** — All components deployed via Helm or YAML on AKS/Custom K8s
* **Namespace Isolation** — Separate test and production environments
* **Rolling Deployments** — Zero downtime updates across services
* **GitHub Actions CI/CD** — Full container pipeline with image promotion and rollback
* **NGINX** is used as a lightweight, high-performance web server to serve the containerized frontend in production.


#### 🔐 Security

* Encrypted secrets via environment variables
* JWT-based secure authentication with hashed passwords
* Redis over SSL with protected commands
* Azure SAS tokens for secure, time-limited video upload/download
* Soft-delete strategy to retain but hide obsolete content

---

### 🧪 How to Log In (Test Accounts)

| Role    | Email                                             | Password    |
| ------- | ------------------------------------------------- | ----------- |
| Student | [student@example.com](mailto:student@example.com) | `Avyay@123` |
| Teacher | [teacher@example.com](mailto:teacher@example.com) | `Avyay@123` |

---

### 🧭 Platform Flow — How to Explore

#### Student

1. **Login** at `login.html`
2. **Submit Reflection**: `submit.html` → Upload video + summary
3. **View Past Reflections**: `my-reflections.html`
4. **Check Feedback** from teachers per chapter

#### Teacher

1. **Login** at `login.html`
2. **Curriculum Management**: `curriculum.html` → Manage subjects & chapters
3. **Reflection Review**: `teacher-refs.html` → Filter & view student submissions
4. **Give Feedback**: `teacher-feedback.html`
5. **Student Management**: `students.html` → Soft-delete/edit profiles

---

### 🗂️ Code Structure

```
backend/
├── main.py              # FastAPI app
├── auth.py              # JWT, OAuth2, password utils
├── db.py                # PostgreSQL connector
├── redis_client.py      # Redis hybrid rate limiter
├── models.py            # Pydantic schemas

frontend/
├── login.html
├── dashboard.html
├── curriculum.html
├── submit.html
├── my-reflections.html
├── teacher-refs.html
├── students.html
├── styles.css           # TailwindCSS theme
```

---

### 🔍 Engineering Highlights

| Area                 | Description                                                |
| -------------------- | ---------------------------------------------------------- |
| **Security**         | SSL Redis, SAS URLs, hashed passwords, JWT, env secrets    |
| **Rate Limiting**    | Hybrid sliding/fixed limiter with Redis                    |
| **Video Upload**     | Azure Blob Storage + signed SAS tokens                     |
| **Soft Delete**      | Logical deletion to preserve audit trail                   |
| **CI/CD**            | GitHub Actions for PR checks, linting, secret scan         |
| **Containerization** | Both frontend and backend are fully containerized          |
| **Kubernetes**       | Hynix cluster with namespace isolation and rolling updates |
| **Frontend**         | Pure HTML + Tailwind + JS `fetch` (no frameworks)          |

---

### 🧩 Areas for Improvement

| Category          | Improvement Needed                              |
| ----------------- | ----------------------------------------------- |
| ✅ Testing         | Add backend unit tests, and frontend test cases |
| 🎞️ Upload Limits | Enforce video size and format validation        |
| 🧪 Namespaces     | Use test namespace for Kubernetes CI runs       |
| 📦 CI/CD          | Modular GitHub Action templates for reuse       |
| 📅 Rate Logic     | Automate mode switching via date/load           |
| 📑 Pagination     | For large lists like reflections or feedback    |
| 🧹 Obsolete Data  | Toggle in UI to view/hide soft-deleted entries  |

---

### 🌱 Vision

**Avyay Reflects** isn’t just another edtech tool — it’s a quiet revolution in how we approach learning. By replacing rote recitation with thoughtful reflection and feedback, we give students the space to **think**, not just remember.

This project merges aesthetics, minimalism, and engineering rigor into a product that aligns with slow learning and modern values — **empathy, mindfulness, and mastery.**

---
