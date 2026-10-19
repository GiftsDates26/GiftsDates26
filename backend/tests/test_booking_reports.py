"""Backend tests for the Booked Date Reports feature.

Covers:
- POST /api/dates/report/{bid}: happy path, ALREADY_REPORTED (409), REPORT_WINDOW_CLOSED (400) if applicable.
- POST /api/dates/cancel/{bid}: DATE_STARTED (400) after start for accepted bookings.
- POST /api/dates/release-half/{bid}: UNDER_REVIEW while report is open.
- GET  /api/admin/booking-reports: lists reported bookings for admin.
- POST /api/admin/booking-reports/{bid}/resolve: dismiss / refund_booker.
- Private file access on /api/files/{path}: 403 without auth, 200 for reporter and admin.
"""
import io
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASS = "Admin@12345"
USER_EMAIL = "ll_tester@example.com"
USER_PASS = "Test@12345"

BID_REPORTED = "ll-test-1"   # confirmed, already reported by admin (open)
BID_FRESH = "rp-test-2"      # accepted, started, admin→ll_tester, not reported


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module", autouse=True)
def _reset_seed():
    """Reset the seeded bookings so tests are idempotent across runs."""
    import pymongo
    from datetime import datetime, timezone, timedelta
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "test_database")
    cli = pymongo.MongoClient(mongo_url)
    db = cli[db_name]
    now = datetime.now(timezone.utc)
    db.date_bookings.update_one({"id": BID_REPORTED}, {"$set": {
        "status": "confirmed",
        "report": {
            "reporter_id": "08077228-239b-459b-af1e-44d8a28d5b45",
            "reasons": ["No-show"],
            "details": "She never showed up at the cafe",
            "evidence": None,
            "photos": ["giftsdates/uploads/08077228-239b-459b-af1e-44d8a28d5b45/c63632dd-5427-48ac-a960-b07bf6ee7ae0.jpg"],
            "status": "open",
            "created_at": now.isoformat(),
        },
    }, "$unset": {"refund": "", "compensation": "", "cancelled_at": "", "cancelled_by": ""}})
    db.date_bookings.update_one({"id": BID_FRESH}, {"$set": {
        "status": "accepted",
        "report": None,
        "scheduled_at": (now - timedelta(hours=2)).isoformat(),
    }, "$unset": {"refund": "", "compensation": "", "cancelled_at": "", "cancelled_by": ""}})
    yield
    cli.close()


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER_EMAIL, USER_PASS)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_list_dates_shows_bookings(user_token):
    r = requests.get(f"{BASE_URL}/api/dates", headers=_h(user_token), timeout=30)
    assert r.status_code == 200
    data = r.json()
    ids = {b["id"] for b in data.get("incoming", [])}
    assert BID_REPORTED in ids and BID_FRESH in ids, f"missing seed bookings in incoming: {ids}"
    reported = next(b for b in data["incoming"] if b["id"] == BID_REPORTED)
    assert reported.get("report") and (reported["report"].get("status") or "open") == "open"


def test_already_reported_409(user_token):
    r = requests.post(f"{BASE_URL}/api/dates/report/{BID_REPORTED}",
                      headers=_h(user_token), json={"reasons": ["No-show"], "details": "duplicate attempt here"},
                      timeout=30)
    assert r.status_code == 409, f"expected 409 ALREADY_REPORTED, got {r.status_code} {r.text}"
    assert r.json().get("detail") == "ALREADY_REPORTED"


def test_release_half_blocked_under_review(user_token):
    r = requests.post(f"{BASE_URL}/api/dates/release-half/{BID_REPORTED}",
                      headers=_h(user_token), timeout=30)
    assert r.status_code == 400
    assert r.json().get("detail") == "UNDER_REVIEW"


def test_cancel_started_date_blocked(admin_token):
    # rp-test-2 is accepted and started -> cancel from booker (admin) must fail
    r = requests.post(f"{BASE_URL}/api/dates/cancel/{BID_FRESH}", headers=_h(admin_token), timeout=30)
    assert r.status_code == 400, f"expected 400 DATE_STARTED, got {r.status_code} {r.text}"
    assert r.json().get("detail") == "DATE_STARTED"


def test_report_requires_min_details(user_token):
    r = requests.post(f"{BASE_URL}/api/dates/report/{BID_FRESH}",
                      headers=_h(user_token), json={"reasons": ["No-show"], "details": "short"},
                      timeout=30)
    assert r.status_code == 400


def _upload_image(tok):
    img = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
           b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01[\xcb\x07"
           b"\xd6\x00\x00\x00\x00IEND\xaeB`\x82")
    files = {"file": ("t.png", io.BytesIO(img), "image/png")}
    r = requests.post(f"{BASE_URL}/api/upload", headers=_h(tok), files=files, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["path"]


def test_report_happy_path_and_private_photos(user_token, admin_token):
    # Upload a photo as the reporter (ll_tester / recipient)
    path = _upload_image(user_token)

    # Submit report on rp-test-2
    r = requests.post(f"{BASE_URL}/api/dates/report/{BID_FRESH}",
                      headers=_h(user_token),
                      json={"reasons": ["No-show"], "details": "He never arrived at the venue",
                            "evidence": "https://example.com/chat", "photos": [path]},
                      timeout=30)
    assert r.status_code == 200, f"report failed: {r.status_code} {r.text}"
    assert r.json().get("ok") is True

    # Second attempt -> 409
    r2 = requests.post(f"{BASE_URL}/api/dates/report/{BID_FRESH}",
                       headers=_h(user_token),
                       json={"reasons": ["No-show"], "details": "duplicate attempt"},
                       timeout=30)
    assert r2.status_code == 409

    # Verify stored in GET /dates
    r3 = requests.get(f"{BASE_URL}/api/dates", headers=_h(user_token), timeout=30)
    booking = next(b for b in r3.json()["incoming"] if b["id"] == BID_FRESH)
    assert booking.get("report")
    assert path in (booking["report"].get("photos") or [])

    # Private file: no auth -> 403
    r_noauth = requests.get(f"{BASE_URL}/api/files/{path}", timeout=30)
    assert r_noauth.status_code == 403, f"expected 403 for anon, got {r_noauth.status_code}"

    # Admin should access it (admin bypass)
    r_admin = requests.get(f"{BASE_URL}/api/files/{path}", headers=_h(admin_token), timeout=30)
    assert r_admin.status_code == 200

    # Reporter (owner) should access it
    r_own = requests.get(f"{BASE_URL}/api/files/{path}", headers=_h(user_token), timeout=30)
    assert r_own.status_code == 200


def test_admin_booking_reports_list(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/booking-reports", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    ids = {b["id"] for b in r.json().get("bookings", [])}
    assert BID_REPORTED in ids
    assert BID_FRESH in ids


def test_admin_booking_reports_requires_admin(user_token):
    r = requests.get(f"{BASE_URL}/api/admin/booking-reports", headers=_h(user_token), timeout=30)
    assert r.status_code in (401, 403)


def test_admin_resolve_dismiss(admin_token):
    # Dismiss the ll-test-1 open report
    r = requests.post(f"{BASE_URL}/api/admin/booking-reports/{BID_REPORTED}/resolve?action=dismiss",
                      headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    # Verify report.status is dismissed by listing again
    r2 = requests.get(f"{BASE_URL}/api/admin/booking-reports", headers=_h(admin_token), timeout=30)
    row = next(b for b in r2.json()["bookings"] if b["id"] == BID_REPORTED)
    assert (row.get("report") or {}).get("status") == "dismissed"


def test_admin_resolve_refund_booker(admin_token):
    # Refund booker on rp-test-2 (was reported in the happy path test)
    # Snapshot admin coins before
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_token), timeout=30).json()
    before = me.get("coins", 0)
    r = requests.post(f"{BASE_URL}/api/admin/booking-reports/{BID_FRESH}/resolve?action=refund_booker",
                      headers=_h(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    me2 = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(admin_token), timeout=30).json()
    assert me2.get("coins", 0) >= before + 100  # 100 coin booking refunded
    # Booking should be cancelled now
    r3 = requests.get(f"{BASE_URL}/api/dates", headers=_h(admin_token), timeout=30)
    booking = next(b for b in r3.json()["outgoing"] if b["id"] == BID_FRESH)
    assert booking["status"] == "cancelled"
