import pytest
from fastapi.testclient import TestClient
from reflects.main import app

client = TestClient(app)

def test_test_version():
    response = client.get("/test-version")
    assert response.status_code == 200
    assert "version" in response.json()

def test_chapters_list():
    response = client.get("/chapters")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_user():
    import uuid
    user_data = {
        "name": "Test User",
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "testpass123",
        "role": "student"
    }
    response = client.post("/create-user", json=user_data)
    assert response.status_code == 200 or "already" in response.text.lower()

def test_login_invalid_user():
    response = client.post("/login", data={"username": "wrong@example.com", "password": "wrongpass"})
    assert response.status_code == 401

# Set up a real test user for this to pass
@pytest.fixture
def auth_header():
    login_data = {
        "username": "teacher@example.com",
        "password": "teacherpass"
    }
    response = client.post("/login", data=login_data)
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    pytest.skip("Auth failed or test user not setup")

def test_get_me(auth_header):
    response = client.get("/me", headers=auth_header)
    assert response.status_code == 200
    assert "email" in response.json()

def test_get_my_reflections(auth_header):
    response = client.get("/my-reflections", headers=auth_header)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_all_reflections_teacher(auth_header):
    response = client.get("/all-reflections", headers=auth_header)
    assert response.status_code in [200, 403]

def test_get_students_emails(auth_header):
    response = client.get("/students/emails", headers=auth_header)
    assert response.status_code in [200, 403]

def test_teacher_feedback_get(auth_header):
    response = client.get("/teacher/feedback", headers=auth_header)
    assert response.status_code in [200, 403]

def test_teacher_feedback_post_invalid(auth_header):
    data = {
        "reflection_id": 9999,
        "status": "understood",
        "comment": "Looks good"
    }
    response = client.post("/teacher/feedback", json=data, headers=auth_header)
    assert response.status_code in [200, 400, 403]
