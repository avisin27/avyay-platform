
# 🌿 Reflects

*A reflection-based learning platform that prioritizes deep thinking, student introspection, and guided feedback.*

---

### ✨ Overview

**Reflects** enables students to submit subject-wise reflections in video or text form and receive structured, thoughtful feedback from teachers. Designed for asynchronous learning, it transforms daily education into a meaningful journey of introspection and personal growth.

---

### 🧠 Key Features

#### 👩‍🎓 For Students

* 📹 Submit chapter-wise video reflections (with optional summary)
* 📜 View personal reflection history, filtered by subject and chapter
* 🔎 View curriculum  (subject, chapter)
* ⏱️ Rate-limited submissions (10 per day or 10 every 24h via hybrid model)

#### 👨‍🏫 For Teachers

* 📚 Create, update, and delete students, subjects and chapters
* 🔎 View all reflections with advanced filters (subject, chapter, student email)
* ⏱️ Rate-limited feedback submissions (20 per day or 20 every 24h via hybrid model)
* 💬 Provide categorized feedback ("Understood" / "Needs Review")
* 🔁 Update past feedback entries
* 🗃️ Soft-delete users content for auditability and resilience (subjects and chapters)

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

* **HTML + TailwindCSS + Vanilla JS** — Lightweight, framework-free UI
* **Responsive UI** Clean and adaptive layout using TailwindCSS with dynamic content loading via JS `fetch`
* **Containerized** — Built and served via an NGINX container in production

#### 🛰️ Infrastructure & Deployment

* **Kubernetes Cluster** — All components deployed via YAML on AKS/Custom K8s
* **Container Image Management** — All services are Dockerized, versioned, and pushed to Azure Container Registry (ACR) with rollback tags (latest, rollback, pr-<hash>)
* **Rolling Deployments** — Zero downtime updates across services
* **GitHub Actions CI/CD** — Full container pipeline with image promotion and rollback
* **NGINX** is used as a lightweight, high-performance web server to serve the containerized frontend in production.


#### 🔐 Security

* JWT-based Authentication — Secure, role-based access with hashed passwords
* Encrypted Secrets — Managed via GitHub Secrets and Azure environment variables
* Redis over SSL — All Redis communication uses encrypted channels and protected command set
* Azure SAS Tokens — Time-limited, scoped URLs for secure video upload/download
* Soft-Delete Strategy — Obsolete data is flagged, not deleted, to preserve auditability
* Image & Dockerfile Scanning — CI workflows include vulnerability scans of Docker images before promotion
* Secrets Never Hardcoded — All API keys, DB creds, and tokens are injected securely at runtime

---

### 🧪 How to Log In (Test Accounts)

| Role    | Email                                             | Password    |
| ------- | ------------------------------------------------- | ----------- |
| Student | [student@reflects.com] | `Myreflects1!` |
| Teacher | [teacher@reflects.com] | `Myreflects1!` |

---

### 🧭 Platform Flow — How to Explore

#### Student

1. **Login** at `index.html`
2. **Dashboard** at `dashboard.html`
3. **Submit Reflection**: `submit.html` → Upload video + summary
4. **View Past Reflections**: `my-reflections.html`
5. **Curriculum View**: `curriculum.html` → View subjects & chapters

#### Teacher

1. **Login** at `index.html`
2. **Dashboard** at `dashboard.html`
3. **Curriculum Management**: `curriculum.html` → Manage subjects & chapters
4. **Reflection Review**: `teacher-refs.html` → Filter & view student submissions
5. **Give Feedback**: `teacher-refs.html`→ Give & view feedback on student submissions
6. **Student Management**: `students.html` → delete/edit profiles

---

### 🗂️ Code Structure

```
backend/
├── main.py              # FastAPI app
├── auth.py              # JWT, OAuth2, password utils
├── db.py                # PostgreSQL connector
├── redis_client.py      # Redis hybrid rate limiter

frontend/
├── index.html
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
| **Security**         | SSL Redis, SAS tokens, hashed passwords, JWT, env secrets    |
| **Rate Limiting**    | Hybrid sliding/fixed limiter with Redis                    |
| **Video Upload**     | Azure Blob Storage + signed SAS tokens                     |
| **Soft Delete**      | Logical deletion to preserve audit trail                   |
| **CI/CD**            | GitHub Actions for PR checks, linting, secret scan         |
| **Containerization** | Both frontend and backend are fully containerized          |
| **Kubernetes**       | Cluster with namespace isolation and rolling updates |
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
