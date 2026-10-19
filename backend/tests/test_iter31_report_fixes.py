"""Run with -n0. Iteration 31: retest of iteration_30 report fixes.
- admin_resolve sets REFUNDED + no double settlement (status + paid_out/refunded guards)
- invite_cancel blocked (UNDER_REVIEW) while a report is open
- invite_report only for active statuses
- admin 'dismiss' action for invite reports
- GET /api/dates sanitises booking.report
Seeded docs tagged seed:true, iter31:true and removed at teardown.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pymongo
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("giftsdates@gmail.com", "Admin@12345")
USER = ("testuser@giftsdates.com", "Test@12345")
REP = {"reasons": ["No-show"], "details": "TEST_ The other person never showed up.", "photos": []}


def _login(e, p):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": e, "password": p}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def db():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    cli = pymongo.MongoClient(os.environ["MONGO_URL"])
    d = cli[os.environ["DB_NAME"]]
    yield d
    for c in ("dates", "date_bookings"):
        d[c].delete_many({"seed": True, "iter31": True})
    cli.close()


@pytest.fixture(scope="module")
def tok():
    return {"admin": _login(*ADMIN), "user": _login(*USER)}


@pytest.fixture(scope="module")
def ids(db):
    return {"admin": db.users.find_one({"email": ADMIN[0]})["id"], "user": db.users.find_one({"email": USER[0]})["id"]}


def H(t): return {"Authorization": f"Bearer {t}"}
def now(): return datetime.now(timezone.utc)
def bal(db, uid):
    u = db.users.find_one({"id": uid})
    return {k: int(u.get(k) or 0) for k in ("coins", "escrow", "withdrawable")}


def seed_invite(db, inviter, recipient, hold=100, status="DATE_CONFIRMED", **extra):
    did = f"iter31-inv-{uuid.uuid4().hex[:8]}"
    s = now() - timedelta(hours=1)
    doc = {"id": did, "seed": True, "iter31": True, "inviter_id": inviter, "recipient_id": recipient,
           "status": status, "coins": hold, "total_hold": hold, "paid_out": False, "refunded": False,
           "report": None, "verification": None, "options": [], "status_log": [],
           "location": {"venue": "TEST cafe", "city": "X", "scheduled_start": s.isoformat(),
                        "scheduled_end": (s + timedelta(hours=3)).isoformat()},
           "created_at": now().isoformat(), "updated_at": now().isoformat()}
    doc.update(extra)
    db.dates.insert_one(doc)
    return did


def resolve(tok, did, action, who="admin"):
    return requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action={action}", headers=H(tok[who]))


# ---------- Admin resolve: no double settlement ----------
class TestNoDoubleSettlement:
    @pytest.mark.parametrize("action", ["refund_inviter", "split", "reporter_wins"])
    def test_refund_sets_refunded_and_second_resolve_400(self, db, tok, ids, action):
        did = seed_invite(db, ids["admin"], ids["user"], hold=80)
        assert requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"])).status_code == 200
        r = resolve(tok, did, action)
        assert r.status_code == 200, r.text
        d = db.dates.find_one({"id": did})
        assert d["status"] == "REFUNDED" and d["refunded"] is True
        assert d["report"]["status"] == "resolved"
        ba, bu = bal(db, ids["admin"]), bal(db, ids["user"])
        for a2 in ("payout_recipient", "refund_inviter", "split", "dismiss"):
            r2 = resolve(tok, did, a2)
            assert r2.status_code == 400 and "Coins already settled" in r2.text, (a2, r2.status_code, r2.text)
        assert bal(db, ids["admin"]) == ba and bal(db, ids["user"]) == bu

    def test_flags_guard_even_if_status_not_final(self, db, tok, ids):
        for flag in ("paid_out", "refunded"):
            did = seed_invite(db, ids["admin"], ids["user"], hold=60, status="REPORTED",
                              **{flag: True, "report": {"reporter_id": ids["admin"], "reporter_role": "inviter", "status": "open"}})
            bu = bal(db, ids["user"])
            r = resolve(tok, did, "payout_recipient")
            assert r.status_code == 400 and "Coins already settled" in r.text
            assert bal(db, ids["user"]) == bu

    def test_payout_then_second_resolve_400(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"], hold=50)
        requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["user"]))
        assert resolve(tok, did, "reporter_wins").status_code == 200
        assert db.dates.find_one({"id": did})["status"] == "COMPLETED"
        ba = bal(db, ids["admin"])
        r = resolve(tok, did, "refund_inviter")
        assert r.status_code == 400 and bal(db, ids["admin"]) == ba


# ---------- invite_cancel while under review ----------
class TestCancelUnderReview:
    def test_cancel_reported_both_sides(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"], hold=200)
        assert requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"])).status_code == 200
        ba, bu = bal(db, ids["admin"]), bal(db, ids["user"])
        for who in ("user", "admin"):
            r = requests.post(f"{BASE_URL}/api/invites/{did}/cancel", headers=H(tok[who]))
            assert r.status_code == 400 and "UNDER_REVIEW" in r.text, (who, r.status_code, r.text)
        d = db.dates.find_one({"id": did})
        assert d["status"] == "REPORTED" and not d.get("refunded")
        assert bal(db, ids["admin"]) == ba and bal(db, ids["user"]) == bu

    def test_cancel_open_report_non_reported_status(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"], hold=40, status="PHOTO_VERIFICATION_PENDING",
                          report={"reporter_id": ids["user"], "reporter_role": "recipient", "status": "open"})
        r = requests.post(f"{BASE_URL}/api/invites/{did}/cancel", headers=H(tok["admin"]))
        assert r.status_code == 400 and "UNDER_REVIEW" in r.text


# ---------- invite_report allowed statuses ----------
class TestReportStatuses:
    @pytest.mark.parametrize("status", ["COMPLETED", "CANCELLED", "REFUNDED", "INVITATION_SENT", "REPORTED"])
    def test_report_rejected_for_inactive(self, db, tok, ids, status):
        did = seed_invite(db, ids["admin"], ids["user"], status=status)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"]))
        assert r.status_code == 400, r.text
        d = db.dates.find_one({"id": did})
        assert d["status"] == status and not d.get("report")

    @pytest.mark.parametrize("status", ["DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING"])
    def test_report_allowed_for_active(self, db, tok, ids, status):
        did = seed_invite(db, ids["admin"], ids["user"], status=status)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["user"]))
        assert r.status_code == 200, r.text
        d = db.dates.find_one({"id": did})
        assert d["status"] == "REPORTED" and d["report"]["prev_status"] == status


# ---------- Admin dismiss ----------
class TestDismiss:
    @pytest.mark.parametrize("status", ["DATE_CONFIRMED", "PHOTO_VERIFICATION_PENDING"])
    def test_dismiss_restores_prev_status_no_coins(self, db, tok, ids, status):
        did = seed_invite(db, ids["admin"], ids["user"], hold=90, status=status)
        assert requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"])).status_code == 200
        assert resolve(tok, did, "dismiss", who="user").status_code == 403
        ba, bu = bal(db, ids["admin"]), bal(db, ids["user"])
        r = resolve(tok, did, "dismiss")
        assert r.status_code == 200, r.text
        d = db.dates.find_one({"id": did})
        assert d["status"] == status
        assert d["report"]["status"] == "dismissed" and d["report"]["outcome"] == "dismiss"
        assert not d.get("refunded") and not d.get("paid_out")
        assert bal(db, ids["admin"]) == ba and bal(db, ids["user"]) == bu
        # after dismiss the date is no longer under review: cancel no longer UNDER_REVIEW
        lst = requests.get(f"{BASE_URL}/api/invites", headers=H(tok["admin"]))
        print("invites list status", lst.status_code)

    def test_dismiss_without_report_400(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"])
        r = resolve(tok, did, "dismiss")
        assert r.status_code == 400 and "No report" in r.text


# ---------- GET /api/dates sanitisation ----------
class TestDatesSanitise:
    def test_booking_report_sanitised(self, db, tok, ids):
        bid = f"iter31-bk-{uuid.uuid4().hex[:8]}"
        db.date_bookings.insert_one({"id": bid, "seed": True, "iter31": True, "from_id": ids["admin"], "to_id": ids["user"],
                                     "status": "accepted", "coins": 10, "venue": "TEST bar",
                                     "scheduled_at": (now() - timedelta(hours=1)).isoformat(), "created_at": now().isoformat(),
                                     "report": {"reporter_id": ids["admin"], "reporter_role": "inviter", "reasons": ["No-show"],
                                                "details": "TEST_ details", "evidence": "SECRET_EVIDENCE", "photos": ["giftsdates/x/secret.png"],
                                                "status": "open", "reply_deadline": now().isoformat(), "created_at": now().isoformat(),
                                                "prev_status": "accepted", "admin_alerted": True,
                                                "reply": {"by": ids["user"], "details": "SECRET_REPLY", "photos": ["giftsdates/y.png"], "at": now().isoformat()}}})
        allowed = {"reporter_id", "reporter_role", "reasons", "details", "status", "reply_deadline", "created_at", "reply"}
        for who, key in (("user", "incoming"), ("admin", "outgoing")):
            r = requests.get(f"{BASE_URL}/api/dates", headers=H(tok[who]))
            assert r.status_code == 200
            b = next(x for x in r.json()[key] if x["id"] == bid)
            rep = b["report"]
            assert set(rep.keys()) == allowed, set(rep.keys())
            assert set(rep["reply"].keys()) == {"at"}
            assert "SECRET" not in str(rep)
