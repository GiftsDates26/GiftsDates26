"""Smoke test for auth endpoints: register, login, me, admin login."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASSWORD = "Admin@12345"


@pytest.fixture(scope="module")
def session():
    return requests.Session()


def test_admin_login(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # Token may be named token/access_token
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in {data}"
    pytest.admin_token = token


def test_admin_me(session):
    token = pytest.admin_token
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("email") == ADMIN_EMAIL


def test_register_new_user(session):
    unique = uuid.uuid4().hex[:8]
    email = f"TEST_user_{unique}@example.com"
    password = "TestPass@123"
    payload = {
        "email": email,
        "password": password,
        "name": "Test User",
        "age": 28,
        "gender": "male",
        "interested_in": "female",
        "city": "New York",
        "country": "USA",
    }
    r = session.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token on register: {data}"
    pytest.new_email = email
    pytest.new_password = password
    pytest.new_token = token


def test_login_new_user(session):
    r = session.post(f"{API}/auth/login", json={"email": pytest.new_email, "password": pytest.new_password}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token


def test_me_new_user(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {pytest.new_token}"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("email") == pytest.new_email.lower()
