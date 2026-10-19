"""Run with -n0 (module teardown deletes seeds; not xdist-safe).
Iteration 30: reports never cancel/refund automatically; 24h reply window; admin decides.

Covers invite dates (db.dates), booked dates (db.date_bookings), VIP no-show (db.vip_sched),
and the _report_window_alerts admin notification.
All seeded docs are tagged seed:true and removed at teardown.
"""
import os
import uuid
import time
from datetime import datetime, timezone, timedelta

import pytest
import pymongo
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN = ("giftsdates@gmail.com", "Admin@12345")
USER = ("testuser@giftsdates.com", "Test@12345")


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
    for c in ("dates", "date_bookings", "vip_sched"):
        d[c].delete_many({"seed": True, "iter30": True})
    cli.close()


@pytest.fixture(scope="module")
def tok():
    return {"admin": _login(*ADMIN), "user": _login(*USER)}


@pytest.fixture(scope="module")
def ids(db):
    a = db.users.find_one({"email": ADMIN[0]})["id"]
    u = db.users.find_one({"email": USER[0]})["id"]
    return {"admin": a, "user": u}


def H(t): return {"Authorization": f"Bearer {t}"}
def now(): return datetime.now(timezone.utc)
def bal(db, uid):
    u = db.users.find_one({"id": uid})
    return {k: int(u.get(k) or 0) for k in ("coins", "escrow", "withdrawable")}


def seed_invite(db, inviter, recipient, hold=200):
    did = f"iter30-inv-{uuid.uuid4().hex[:8]}"
    s = now() - timedelta(hours=1)
    db.dates.insert_one({"id": did, "seed": True, "iter30": True, "inviter_id": inviter, "recipient_id": recipient,
                         "status": "DATE_CONFIRMED", "coins": hold, "total_hold": hold, "paid_out": False, "refunded": False,
                         "report": None, "verification": None, "options": [], "status_log": [],
                         "location": {"venue": "TEST cafe", "city": "X", "scheduled_start": s.isoformat(),
                                      "scheduled_end": (s + timedelta(hours=3)).isoformat()},
                         "created_at": now().isoformat(), "updated_at": now().isoformat()})
    return did


def seed_booking(db, frm, to, coins=120):
    bid = f"iter30-bk-{uuid.uuid4().hex[:8]}"
    db.date_bookings.insert_one({"id": bid, "seed": True, "iter30": True, "from_id": frm, "to_id": to, "status": "accepted",
                                 "coins": coins, "venue": "TEST bar", "scheduled_at": (now() - timedelta(hours=1)).isoformat(),
                                 "created_at": now().isoformat()})
    db.users.update_one({"id": to}, {"$inc": {"escrow": coins}})
    return bid


def seed_vip(db, req, vip, coins=300):
    bid = f"iter30-vs-{uuid.uuid4().hex[:8]}"
    s = now() - timedelta(minutes=30)
    e = s + timedelta(hours=2)
    db.vip_sched.insert_one({"id": bid, "seed": True, "iter30": True, "vip_id": vip, "requester_id": req, "status": "confirmed",
                             "coins": coins, "tz": "UTC", "date": s.strftime("%Y-%m-%d"), "start": s.strftime("%H:%M"),
                             "end": e.strftime("%H:%M"), "created_at": now().isoformat()})
    db.users.update_one({"id": vip}, {"$inc": {"escrow": coins}})
    return bid


REP = {"reasons": ["No-show"], "details": "TEST_ The other person never showed up.", "photos": []}
REPLY = {"details": "TEST_ I was there on time, here is my side.", "photos": []}


# ---------- Invite dates ----------
class TestInviteReports:
    def test_inviter_report_no_refund_and_duplicate(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"])
        before_a, before_u = bal(db, ids["admin"]), bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"]))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "REPORTED"
        d = db.dates.find_one({"id": did})
        assert d["status"] == "REPORTED"
        rep = d["report"]
        assert rep["reporter_role"] == "inviter" and rep["status"] == "open"
        dl = datetime.fromisoformat(rep["reply_deadline"])
        assert abs((dl - now()).total_seconds() - 24 * 3600) < 120
        assert not d.get("refunded") and not d.get("paid_out")
        assert bal(db, ids["admin"]) == before_a and bal(db, ids["user"]) == before_u
        r2 = requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["user"]))
        # iter31: status guard (REPORTED not reportable) runs before the duplicate check -> 400; 409 also acceptable
        assert r2.status_code in (400, 409), r2.text

    def test_reply_before_and_after_deadline(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"])
        assert requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"])).status_code == 200
        # reporter cannot reply
        r = requests.post(f"{BASE_URL}/api/invites/{did}/report/reply", json=REPLY, headers=H(tok["admin"]))
        assert r.status_code == 403
        r = requests.post(f"{BASE_URL}/api/invites/{did}/report/reply", json=REPLY, headers=H(tok["user"]))
        assert r.status_code == 200 and r.json()["replied"] is True
        assert db.dates.find_one({"id": did})["report"]["reply"]["details"].startswith("TEST_")
        # second date, deadline in the past
        did2 = seed_invite(db, ids["admin"], ids["user"])
        assert requests.post(f"{BASE_URL}/api/invites/{did2}/report", json=REP, headers=H(tok["admin"])).status_code == 200
        db.dates.update_one({"id": did2}, {"$set": {"report.reply_deadline": (now() - timedelta(minutes=1)).isoformat()}})
        r = requests.post(f"{BASE_URL}/api/invites/{did2}/report/reply", json=REPLY, headers=H(tok["user"]))
        assert r.status_code == 400 and "REPLY_WINDOW_CLOSED" in r.text

    def test_reported_invite_cannot_be_cancelled(self, db, tok, ids):
        """A reported date must not be cancellable by either party (would move coins without admin)."""
        did = seed_invite(db, ids["admin"], ids["user"])
        assert requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"])).status_code == 200
        before_a = bal(db, ids["admin"])
        r = requests.post(f"{BASE_URL}/api/invites/{did}/cancel", headers=H(tok["user"]))
        d = db.dates.find_one({"id": did})
        assert r.status_code == 400, f"Reported date was cancelled by party: {r.status_code} {r.text}; status={d['status']} admin_coins {before_a}->{bal(db, ids['admin'])}"

    def test_admin_reporter_wins_inviter_refund(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"], hold=200)
        requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"]))
        b = bal(db, ids["admin"])
        r = requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=reporter_wins", headers=H(tok["admin"]))
        assert r.status_code == 200, r.text
        assert bal(db, ids["admin"])["coins"] == b["coins"] + 200
        d = db.dates.find_one({"id": did})
        assert d["status"] == "REFUNDED", d["status"]
        assert d["report"]["status"] == "resolved" and d["report"]["outcome"] == "refund_inviter"
        r = requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=payout_recipient", headers=H(tok["admin"]))
        assert r.status_code == 400

    def test_no_double_settlement_after_refund(self, db, tok, ids):
        """After refund_inviter, a second resolve (payout_recipient) must be 400 and must not pay the recipient."""
        did = seed_invite(db, ids["admin"], ids["user"], hold=70)
        requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["admin"]))
        assert requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=refund_inviter", headers=H(tok["admin"])).status_code == 200
        bu = bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=payout_recipient", headers=H(tok["admin"]))
        gained = bal(db, ids["user"])["withdrawable"] - bu["withdrawable"]
        assert r.status_code == 400 and gained == 0, f"second resolve {r.status_code}, recipient gained {gained}"

    def test_admin_reporter_wins_recipient_payout(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"], hold=180)
        r = requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["user"]))
        assert r.status_code == 200
        assert db.dates.find_one({"id": did})["report"]["reporter_role"] == "recipient"
        b = bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=reporter_wins", headers=H(tok["admin"]))
        assert r.status_code == 200
        assert bal(db, ids["user"])["withdrawable"] == b["withdrawable"] + 180
        d = db.dates.find_one({"id": did})
        assert d["status"] == "COMPLETED" and d["report"]["outcome"] == "payout_recipient"

    def test_admin_other_wins_and_split_and_nonadmin(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"], hold=100)
        requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["user"]))
        assert requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=other_wins", headers=H(tok["user"])).status_code == 403
        b = bal(db, ids["admin"])
        r = requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=other_wins", headers=H(tok["admin"]))
        assert r.status_code == 200
        assert bal(db, ids["admin"])["coins"] == b["coins"] + 100
        assert db.dates.find_one({"id": did})["status"] == "REFUNDED"
        did2 = seed_invite(db, ids["admin"], ids["user"], hold=100)
        requests.post(f"{BASE_URL}/api/invites/{did2}/report", json=REP, headers=H(tok["admin"]))
        ba, bu = bal(db, ids["admin"]), bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/admin/dates/{did2}/resolve?action=split", headers=H(tok["admin"]))
        assert r.status_code == 200
        assert bal(db, ids["admin"])["coins"] == ba["coins"] + 50
        assert bal(db, ids["user"])["withdrawable"] == bu["withdrawable"] + 25


# ---------- Booked dates ----------
class TestBookingReports:
    def test_booking_report_reply_cancel_blocked_release(self, db, tok, ids):
        bid = seed_booking(db, ids["admin"], ids["user"], coins=120)
        r = requests.post(f"{BASE_URL}/api/dates/report/{bid}", json=REP, headers=H(tok["admin"]))
        assert r.status_code == 200, r.text
        rep = db.date_bookings.find_one({"id": bid})["report"]
        assert rep["reporter_role"] == "inviter" and rep["status"] == "open" and rep.get("reply_deadline")
        assert db.date_bookings.find_one({"id": bid})["status"] == "accepted"
        for who in ("admin", "user"):
            r = requests.post(f"{BASE_URL}/api/dates/cancel/{bid}", headers=H(tok[who]))
            assert r.status_code == 400 and "UNDER_REVIEW" in r.text
        db.date_bookings.update_one({"id": bid}, {"$set": {"report.reply_deadline": (now() - timedelta(minutes=1)).isoformat()}})
        r = requests.post(f"{BASE_URL}/api/dates/report/{bid}/reply", json=REPLY, headers=H(tok["user"]))
        assert r.status_code == 400 and "REPLY_WINDOW_CLOSED" in r.text
        bu = bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/admin/booking-reports/{bid}/resolve?action=release_recipient", headers=H(tok["admin"]))
        assert r.status_code == 200, r.text
        au = bal(db, ids["user"])
        assert au["escrow"] == bu["escrow"] - 120 and au["withdrawable"] == bu["withdrawable"] + 120
        b = db.date_bookings.find_one({"id": bid})
        assert b["status"] == "released" and b["report"]["status"] == "released"

    def test_booking_reply_ok_and_refund_booker(self, db, tok, ids):
        bid = seed_booking(db, ids["admin"], ids["user"], coins=90)
        r = requests.post(f"{BASE_URL}/api/dates/report/{bid}", json=REP, headers=H(tok["user"]))
        assert r.status_code == 200
        assert db.date_bookings.find_one({"id": bid})["report"]["reporter_role"] == "recipient"
        r = requests.post(f"{BASE_URL}/api/dates/report/{bid}", json=REP, headers=H(tok["admin"]))
        assert r.status_code == 409
        r = requests.post(f"{BASE_URL}/api/dates/report/{bid}/reply", json=REPLY, headers=H(tok["admin"]))
        assert r.status_code == 200
        ba, bu = bal(db, ids["admin"]), bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/admin/booking-reports/{bid}/resolve?action=refund_booker", headers=H(tok["admin"]))
        assert r.status_code == 200
        assert bal(db, ids["admin"])["coins"] == ba["coins"] + 90
        assert bal(db, ids["user"])["escrow"] == bu["escrow"] - 90
        assert db.date_bookings.find_one({"id": bid})["status"] == "cancelled"


# ---------- VIP no-show ----------
class TestVipNoShow:
    def test_no_show_reported_and_reply_and_valid(self, db, tok, ids):
        bid = seed_vip(db, ids["admin"], ids["user"], coins=300)
        ba, bu = bal(db, ids["admin"]), bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show", data={"note": "TEST_ VIP did not come at all"}, headers=H(tok["admin"]))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "reported"
        b = db.vip_sched.find_one({"id": bid})
        assert b["status"] == "reported" and b["no_show_report"]["status"] == "open" and b["no_show_report"].get("reply_deadline")
        assert bal(db, ids["admin"]) == ba and bal(db, ids["user"]) == bu
        # client can't reply, short note rejected
        assert requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show/reply", data={"note": "TEST_ I was there for real"}, headers=H(tok["admin"])).status_code == 403
        assert requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show/reply", data={"note": "short"}, headers=H(tok["user"])).status_code == 400
        files = {"photo": ("p.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show/reply", data={"note": "TEST_ I was there for real"}, files=files, headers=H(tok["user"]))
        assert r.status_code == 200, r.text
        assert db.vip_sched.find_one({"id": bid})["no_show_report"]["reply"]["details"].startswith("TEST_")
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show/reply", data={"note": "TEST_ again again again"}, headers=H(tok["user"]))
        assert r.status_code == 409
        r = requests.post(f"{BASE_URL}/api/admin/no-show-reports/{bid}/resolve?action=valid", headers=H(tok["admin"]))
        assert r.status_code == 200
        assert bal(db, ids["admin"])["coins"] == ba["coins"] + 300
        assert bal(db, ids["user"])["escrow"] == bu["escrow"] - 300
        b = db.vip_sched.find_one({"id": bid})
        assert b["status"] == "cancelled" and b["no_show_report"]["status"] == "valid"

    def test_no_show_reply_window_closed_and_reversed(self, db, tok, ids):
        bid = seed_vip(db, ids["admin"], ids["user"], coins=200)
        assert requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show", data={"note": "TEST_ VIP did not come at all"}, headers=H(tok["admin"])).status_code == 200
        db.vip_sched.update_one({"id": bid}, {"$set": {"no_show_report.reply_deadline": (now() - timedelta(minutes=1)).isoformat()}})
        r = requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show/reply", data={"note": "TEST_ I was there for real"}, headers=H(tok["user"]))
        assert r.status_code == 400 and "REPLY_WINDOW_CLOSED" in r.text
        bu = bal(db, ids["user"])
        r = requests.post(f"{BASE_URL}/api/admin/no-show-reports/{bid}/resolve?action=reversed", headers=H(tok["admin"]))
        assert r.status_code == 200
        au = bal(db, ids["user"])
        assert au["escrow"] == bu["escrow"] - 200 and au["withdrawable"] == bu["withdrawable"] + 200
        assert db.vip_sched.find_one({"id": bid})["status"] == "completed"

    def test_reported_vip_not_autocompleted(self, db, tok, ids):
        """Reported booking with end in the past stays 'reported' after the background tick."""
        bid = seed_vip(db, ids["admin"], ids["user"], coins=50)
        assert requests.post(f"{BASE_URL}/api/vip/schedule/bookings/{bid}/no-show", data={"note": "TEST_ VIP did not come at all"}, headers=H(tok["admin"])).status_code == 200
        past = now() - timedelta(hours=3)
        db.vip_sched.update_one({"id": bid}, {"$set": {"date": past.strftime("%Y-%m-%d"), "start": past.strftime("%H:%M"),
                                                      "end": (past + timedelta(hours=1)).strftime("%H:%M")}})
        # trigger VIP listing (lazy autocomplete) and wait for a background tick
        requests.get(f"{BASE_URL}/api/vip/schedule/bookings", headers=H(tok["user"]))
        time.sleep(65)
        assert db.vip_sched.find_one({"id": bid})["status"] == "reported"
        requests.post(f"{BASE_URL}/api/admin/no-show-reports/{bid}/resolve?action=valid", headers=H(tok["admin"]))


# ---------- Report window alerts ----------
class TestWindowAlerts:
    def test_admin_alerted_once(self, db, tok, ids):
        did = seed_invite(db, ids["admin"], ids["user"])
        requests.post(f"{BASE_URL}/api/invites/{did}/report", json=REP, headers=H(tok["user"]))
        db.dates.update_one({"id": did}, {"$set": {"report.reply_deadline": (now() - timedelta(minutes=1)).isoformat()}})
        deadline = time.time() + 90
        while time.time() < deadline:
            if db.dates.find_one({"id": did})["report"].get("admin_alerted"): break
            time.sleep(5)
        assert db.dates.find_one({"id": did})["report"].get("admin_alerted") is True
        n = db.notifications.count_documents({"user_id": ids["admin"], "title": "Report ready for decision", "data.date_id": did})
        assert n == 1, n
        assert db.dates.find_one({"id": did})["status"] == "REPORTED"
        requests.post(f"{BASE_URL}/api/admin/dates/{did}/resolve?action=reporter_wins", headers=H(tok["admin"]))
