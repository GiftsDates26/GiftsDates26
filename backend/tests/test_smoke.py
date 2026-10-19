"""GiftsDates smoke tests: meta, auth (register/login/me), profiles listing."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://giftsdates21.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASSWORD = "Admin@12345"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Meta ----------
def test_meta_endpoint(session):
    r = session.get(f"{BASE_URL}/api/meta", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "gifts" in data and isinstance(data["gifts"], list)
    assert "coin_packages" in data
    assert "premium" in data


# ---------- Admin login ----------
def test_admin_login(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and isinstance(data["token"], str)
    assert data["user"]["email"] == ADMIN_EMAIL


def test_admin_me(session):
    tok = session.post(f"{BASE_URL}/api/auth/login",
                       json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15).json()["token"]
    r = session.get(f"{BASE_URL}/api/auth/me",
                    headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == ADMIN_EMAIL


# ---------- Signup + login + me + profiles ----------
@pytest.fixture(scope="module")
def new_user(session):
    uniq = uuid.uuid4().hex[:10]
    email = f"TEST_user_{uniq}@example.com"
    password = "TestPass#12345"
    payload = {
        "email": email, "password": password, "name": f"TEST User {uniq}",
        "age": 28, "gender": "female", "interested_in": "male",
        "orientation": "straight", "city": "London", "country": "UK",
        "bio": "test", "language": "en",
    }
    r = session.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    return {"email": email, "password": password, "token": data["token"], "user": data["user"]}


def test_signup_login_me(session, new_user):
    # login
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": new_user["email"], "password": new_user["password"]}, timeout=15)
    assert r.status_code == 200
    tok = r.json()["token"]
    # /auth/me
    r2 = session.get(f"{BASE_URL}/api/auth/me",
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    assert r2.status_code == 200
    assert r2.json()["email"].lower() == new_user["email"].lower()


def test_me_requires_auth(session):
    r = session.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert r.status_code == 401


def test_login_invalid(session):
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": "nonexistent@example.com", "password": "wrong"}, timeout=10)
    assert r.status_code == 401


# ---------- Profiles listing (browse) ----------
def test_profiles_listing(session, new_user):
    headers = {"Authorization": f"Bearer {new_user['token']}"}
    # try common endpoints: /api/profiles, /api/users, /api/browse
    tried = []
    for path in ("/api/profiles", "/api/users", "/api/browse", "/api/match/profiles"):
        r = session.get(f"{BASE_URL}{path}", headers=headers, timeout=15)
        tried.append((path, r.status_code))
        if r.status_code == 200:
            return
    pytest.fail(f"No profiles listing endpoint returned 200. Tried: {tried}")


# ---------- Date ideas (requires auth) ----------
def test_date_ideas(session, new_user):
    r = session.get(f"{BASE_URL}/api/date-ideas",
                    headers={"Authorization": f"Bearer {new_user['token']}"}, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
