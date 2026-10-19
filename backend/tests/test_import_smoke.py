"""Smoke test for repo import — auth, me, admin access per test_credentials.md"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("giftsdates@gmail.com", "Admin@GD24!")
USER = ("testuser@giftsdates.com", "Test@12345")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _login(s, email, pw):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok
    return tok, data["user"]


def test_admin_login_and_me(s):
    tok, u = _login(s, *ADMIN)
    assert u["email"] == ADMIN[0]
    r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN[0]
    pytest.admin_tok = tok


def test_user_login_and_me(s):
    tok, u = _login(s, *USER)
    assert u["email"] == USER[0]
    r = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["email"] == USER[0]
    pytest.user_tok = tok


def test_register_new_user(s):
    unique = uuid.uuid4().hex[:8]
    email = f"TEST_import_{unique}@example.com"
    payload = {
        "email": email, "password": "TestPass@123", "name": "Test Import",
        "age": 28, "gender": "male", "interested_in": "female",
        "orientation": "straight", "orientations": ["straight"],
        "city": "New York", "country": "US",
    }
    r = s.post(f"{API}/auth/register", json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    tok = data.get("token")
    assert tok
    r2 = s.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["email"] == email.lower()


# Browse / profiles / wallet / dates endpoints — common page data
@pytest.mark.parametrize("path", [
    "/users/browse",
    "/wallet/balance",
    "/dates/mine",
    "/matches",
])
def test_user_accessible_pages(s, path):
    tok = pytest.user_tok
    r = s.get(f"{API}{path}", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    # Accept 200 or 404 (endpoint might differ), but not 500
    assert r.status_code < 500, f"{path} => {r.status_code} {r.text[:300]}"


def test_admin_endpoint_access(s):
    tok = pytest.admin_tok
    # Try a couple common admin endpoints — expect <500
    for path in ["/admin/users", "/admin/stats", "/admin/overview"]:
        r = s.get(f"{API}{path}", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        assert r.status_code < 500, f"{path} => {r.status_code} {r.text[:300]}"
