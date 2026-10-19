"""Backend tests for VIP no-show evidence feature (iter 22).

Covers:
- POST /api/vip/schedule/bookings/{id}/no-show (multipart) - validations, happy path
- GET /api/files/{path} - private file auth (no auth / client / admin)
- GET /api/admin/no-show-reports (admin only)
- POST /api/admin/no-show-reports/{id}/resolve action=valid|reversed
"""
import os
import io
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://gd24-preview.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "giftsdates@gmail.com"
ADMIN_PASS = "Admin@GD24!"
VIP_EMAIL = "testuser@giftsdates.com"
VIP_PASS = "Test@12345"
VIP_ID = "b486a9ec-21a5-46f2-ac7b-4bd42fcb91e6"


# ---- helpers ----
def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def vip_token():
    return _login(VIP_EMAIL, VIP_PASS)


@pytest.fixture(scope="module")
def admin_id(admin_token):
    r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    return r.json()["id"]


def _make_booking(db, admin_id, status="confirmed", in_window=True, coins=100):
    """Create a vip_sched doc directly (requester=admin, vip=VIP) placed inside the no-show window."""
    now = datetime.now(timezone.utc)
    if in_window:
        start_dt = now - timedelta(minutes=30)
        end_dt = now + timedelta(minutes=30)
    else:
        start_dt = now + timedelta(hours=5)
        end_dt = now + timedelta(hours=6)
    bid = f"TEST_ns_{uuid.uuid4()}"
    doc = {
        "id": bid,
        "requester_id": admin_id,
        "vip_id": VIP_ID,
        "status": status,
        "date": start_dt.strftime("%Y-%m-%d"),
        "start": start_dt.strftime("%H:%M"),
        "end": end_dt.strftime("%H:%M"),
        "tz": "UTC",
        "coins": coins,
        "created_at": now.isoformat(),
    }
    db.vip_sched.insert_one(doc)
    # Add coins to admin and escrow to VIP so refund math is observable
    db.users.update_one({"id": admin_id}, {"$inc": {"coins": 0}})
    db.users.update_one({"id": VIP_ID}, {"$inc": {"escrow": coins}})
    return bid


def _cleanup(db, bid):
    db.vip_sched.delete_one({"id": bid})


# ---- Validation tests ----
class TestNoShowValidation:
    def test_requires_auth(self, db, admin_id):
        bid = _make_booking(db, admin_id)
        try:
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/no-show", data={"note": "x"}, timeout=15)
            assert r.status_code in (401, 403)
        finally:
            _cleanup(db, bid)

    def test_only_client_can_report(self, db, admin_id, vip_token):
        bid = _make_booking(db, admin_id)
        try:
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/no-show",
                              headers={"Authorization": f"Bearer {vip_token}"},
                              data={"note": "nope"}, timeout=15)
            assert r.status_code == 403
        finally:
            _cleanup(db, bid)

    def test_outside_window_returns_400(self, db, admin_id, admin_token):
        bid = _make_booking(db, admin_id, in_window=False)
        try:
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/no-show",
                              headers={"Authorization": f"Bearer {admin_token}"},
                              data={"note": "early"}, timeout=15)
            assert r.status_code == 400
            assert "NO_SHOW_WINDOW" in r.text
        finally:
            _cleanup(db, bid)

    def test_evidence_required(self, db, admin_id, admin_token):
        bid = _make_booking(db, admin_id)
        try:
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/no-show",
                              headers={"Authorization": f"Bearer {admin_token}"},
                              data={"note": "   "}, timeout=15)
            assert r.status_code == 400
            assert "EVIDENCE_REQUIRED" in r.text
        finally:
            _cleanup(db, bid)

    def test_non_image_rejected(self, db, admin_id, admin_token):
        bid = _make_booking(db, admin_id)
        try:
            files = {"photo": ("evil.txt", b"not an image", "text/plain")}
            r = requests.post(f"{API}/vip/schedule/bookings/{bid}/no-show",
                              headers={"Authorization": f"Bearer {admin_token}"},
                              data={"note": ""}, files=files, timeout=15)
            assert r.status_code == 400
            assert "IMAGE_ONLY" in r.text
        finally:
            _cleanup(db, bid)

    def test_not_found(self, admin_token):
        r = requests.post(f"{API}/vip/schedule/bookings/does-not-exist/no-show",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          data={"note": "x"}, timeout=15)
        assert r.status_code == 404


# ---- Happy path + private file + admin resolve ----
class TestNoShowFlow:
    def _get_coins(self, db, uid):
        u = db.users.find_one({"id": uid}, {"_id": 0, "coins": 1, "escrow": 1, "withdrawable": 1}) or {}
        return int(u.get("coins") or 0), int(u.get("escrow") or 0), int(u.get("withdrawable") or 0)

    def test_full_flow_with_photo(self, db, admin_id, admin_token, vip_token):
        coins_amt = 150
        bid = _make_booking(db, admin_id, coins=coins_amt)
        try:
            client_before = self._get_coins(db, admin_id)
            vip_before = self._get_coins(db, VIP_ID)

            # 1x1 PNG
            png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
                b"\x5a\xa8\xcf\xf1\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            files = {"photo": ("evidence.png", png, "image/png")}
            r = requests.post(
                f"{API}/vip/schedule/bookings/{bid}/no-show",
                headers={"Authorization": f"Bearer {admin_token}"},
                data={"note": "VIP did not arrive"},
                files=files,
                timeout=20,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "cancelled"
            assert body["refunded"] == coins_amt

            # Persisted
            doc = db.vip_sched.find_one({"id": bid}, {"_id": 0})
            assert doc["status"] == "cancelled"
            assert doc.get("no_show") is True
            rep = doc.get("no_show_report") or {}
            assert rep.get("status") == "open"
            assert rep.get("note") == "VIP did not arrive"
            photo_path = rep.get("photo")
            assert photo_path and photo_path.startswith("giftsdates/no-show/")

            # Refund math: client coins +coins_amt (parallel tests may touch VIP escrow,
            # so we only strictly assert the client-side refund here).
            client_after = self._get_coins(db, admin_id)
            assert client_after[0] - client_before[0] == coins_amt

            # Private file: no auth -> 403
            r2 = requests.get(f"{API}/files/{photo_path}", timeout=15)
            assert r2.status_code == 403, f"got {r2.status_code}: {r2.text[:200]}"

            # Admin via ?auth=
            r3 = requests.get(f"{API}/files/{photo_path}?auth={admin_token}", timeout=15)
            assert r3.status_code == 200
            assert r3.headers.get("content-type", "").startswith("image/")

            # Client (uploader) via Bearer
            r4 = requests.get(
                f"{API}/files/{photo_path}",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=15,
            )
            assert r4.status_code == 200

            # VIP (not uploader, not admin, not viewer) -> 403
            r5 = requests.get(
                f"{API}/files/{photo_path}",
                headers={"Authorization": f"Bearer {vip_token}"},
                timeout=15,
            )
            assert r5.status_code == 403

            # Admin list
            lst = requests.get(f"{API}/admin/no-show-reports",
                               headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
            assert lst.status_code == 200
            data = lst.json()
            ids = [x["id"] for x in data.get("reports", [])]
            assert bid in ids
            row = next(x for x in data["reports"] if x["id"] == bid)
            assert row.get("client") and row.get("vip")
            assert (row.get("no_show_report") or {}).get("status") == "open"

            # Non-admin cannot list
            unauth = requests.get(f"{API}/admin/no-show-reports",
                                  headers={"Authorization": f"Bearer {vip_token}"}, timeout=15)
            assert unauth.status_code == 403

            # Resolve with 'valid' - refund kept
            res = requests.post(
                f"{API}/admin/no-show-reports/{bid}/resolve?action=valid",
                headers={"Authorization": f"Bearer {admin_token}"}, timeout=15,
            )
            assert res.status_code == 200
            assert res.json()["status"] == "valid"
            doc2 = db.vip_sched.find_one({"id": bid}, {"_id": 0})
            assert doc2["no_show_report"]["status"] == "valid"
            # Refund kept: client coins unchanged
            assert self._get_coins(db, admin_id)[0] == client_after[0]

            # Second resolve -> 404
            res2 = requests.post(
                f"{API}/admin/no-show-reports/{bid}/resolve?action=valid",
                headers={"Authorization": f"Bearer {admin_token}"}, timeout=15,
            )
            assert res2.status_code == 404
        finally:
            _cleanup(db, bid)
            # cleanup file record
            if 'photo_path' in dir():
                try:
                    db.files.delete_many({"storage_path": {"$regex": f"^giftsdates/no-show/{bid}/"}})
                except Exception:
                    pass

    def test_resolve_reversed_pays_vip(self, db, admin_id, admin_token):
        coins_amt = 80
        bid = _make_booking(db, admin_id, coins=coins_amt)
        try:
            # Report with note only
            r = requests.post(
                f"{API}/vip/schedule/bookings/{bid}/no-show",
                headers={"Authorization": f"Bearer {admin_token}"},
                data={"note": "nope"},
                timeout=15,
            )
            assert r.status_code == 200

            client_before = self._get_coins(db, admin_id)[0]
            vip_before_w = self._get_coins(db, VIP_ID)[2]

            res = requests.post(
                f"{API}/admin/no-show-reports/{bid}/resolve?action=reversed",
                headers={"Authorization": f"Bearer {admin_token}"}, timeout=15,
            )
            assert res.status_code == 200
            assert res.json()["status"] == "reversed"

            doc = db.vip_sched.find_one({"id": bid}, {"_id": 0})
            assert doc["no_show_report"]["status"] == "reversed"
            assert doc["status"] == "completed"
            amount = int(doc.get("no_show_reversed_coins") or 0)
            assert amount > 0
            assert amount <= coins_amt

            client_after = self._get_coins(db, admin_id)[0]
            vip_after_w = self._get_coins(db, VIP_ID)[2]
            assert client_before - client_after == amount
            assert vip_after_w - vip_before_w == amount
        finally:
            _cleanup(db, bid)

    def test_resolve_bad_action(self, db, admin_id, admin_token):
        bid = _make_booking(db, admin_id, coins=50)
        try:
            r = requests.post(
                f"{API}/vip/schedule/bookings/{bid}/no-show",
                headers={"Authorization": f"Bearer {admin_token}"},
                data={"note": "x"}, timeout=15,
            )
            assert r.status_code == 200
            bad = requests.post(
                f"{API}/admin/no-show-reports/{bid}/resolve?action=zzz",
                headers={"Authorization": f"Bearer {admin_token}"}, timeout=15,
            )
            assert bad.status_code == 400
        finally:
            _cleanup(db, bid)
