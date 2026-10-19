"""Re-import smoke: auth (register/login/admin), main page APIs, Stripe checkout session creation."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = ("giftsdates@gmail.com", "Admin@12345")
USER = ("testuser@giftsdates.com", "Test@12345")


def _login(email, pw):
    return requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=20)


@pytest.fixture(scope="module")
def user_s():
    r = _login(*USER)
    if r.status_code != 200:
        pytest.skip(f"user login failed {r.status_code} {r.text}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def admin_s():
    r = _login(*ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code} {r.text}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


# Health
def test_health():
    r = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert r.status_code == 200 and r.json().get("ok") is True


# Auth
def test_register_new_user_and_me():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "Test@12345", "name": "TEST Smoke", "age": 25,
        "gender": "male", "interested_in": "female", "orientation": "straight",
        "city": "Berlin", "country": "Germany"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["email"] == email and "password" not in d["user"]
    me = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {d['token']}"}, timeout=15)
    assert me.status_code == 200 and me.json()["email"] == email
    # login with newly registered creds
    assert _login(email, "Test@12345").status_code == 200


def test_register_duplicate():
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": USER[0], "password": "x", "name": "x", "age": 25, "gender": "male",
        "interested_in": "female", "city": "a", "country": "b"}, timeout=20)
    assert r.status_code == 400


def test_login_user_ok():
    r = _login(*USER)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == USER[0]


def test_login_wrong_password():
    assert _login(USER[0], "wrong").status_code == 401


def test_admin_login_and_wallet_is_admin(admin_s):
    r = admin_s.get(f"{BASE_URL}/api/wallet", timeout=15)
    assert r.status_code == 200
    assert r.json().get("is_admin") is True


# Main page APIs
@pytest.mark.parametrize("path", ["/api/meta", "/api/wallet", "/api/auth/me"])
def test_main_endpoints(user_s, path):
    r = user_s.get(f"{BASE_URL}{path}", timeout=20)
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"


def _checkout(s, pkg, usd=None):
    r = s.post(f"{BASE_URL}/api/payments/checkout",
               json={"package_id": pkg, "origin_url": BASE_URL, "usd_amount": usd}, timeout=40)
    assert r.status_code == 200, f"{pkg}: {r.status_code} {r.text}"
    d = r.json()
    assert d["checkout_url"].startswith("https://checkout.stripe.com"), d
    assert d["session_id"].startswith("cs_test_"), d
    return d


# Stripe checkout
def test_checkout_first_coin_package(user_s):
    meta = user_s.get(f"{BASE_URL}/api/meta", timeout=15).json()
    pkg = meta["coin_packages"][0]["id"]
    d = _checkout(user_s, pkg)
    st = requests.get(f"{BASE_URL}/api/payments/status/{d['session_id']}", timeout=20)
    assert st.status_code == 200 and st.json()["payment_status"] != "paid"


def test_checkout_custom(user_s):
    _checkout(user_s, "custom", 20)


def test_checkout_premium(user_s):
    _checkout(user_s, "premium_monthly")


def test_checkout_premium_lite(user_s):
    _checkout(user_s, "premium_lite_monthly")


def test_checkout_vip(user_s):
    _checkout(user_s, "vip_monthly")


def test_checkout_unknown(user_s):
    r = user_s.post(f"{BASE_URL}/api/payments/checkout", json={"package_id": "nope", "origin_url": BASE_URL}, timeout=20)
    assert r.status_code == 400


def test_webhook_rejects_bad_signature():
    r = requests.post(f"{BASE_URL}/api/stripe/webhook", data="{}", headers={"stripe-signature": "bad"}, timeout=15)
    assert r.status_code == 400
