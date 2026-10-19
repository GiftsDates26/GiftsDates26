# Seed/cleanup for iteration 29 UI checks: python seed_iter29_ui.py seed|clean
import os, sys, json
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
me = db.users.find_one({"email": "testuser@giftsdates.com"}); ad = db.users.find_one({"email": "giftsdates@gmail.com"})
SNAP = "/tmp/iter29_snap.json"
if sys.argv[1] == "seed":
    json.dump({"vip_until": me.get("vip_until"), "vip": me.get("vip"), "vip_own_place": me.get("vip_own_place")}, open(SNAP, "w"), default=str)
    vip = dict(me.get("vip") or {}); vip["places"] = ["own"]
    db.users.update_one({"id": me["id"]}, {"$set": {"vip_until": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(), "vip": vip,
        "vip_own_place": {"address": "12 Nowhere Fakeway", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada", "lat": None, "lng": None, "unverified": True}}})
    s = (datetime.now(timezone.utc) + timedelta(days=8)).replace(microsecond=0).isoformat()
    db.date_bookings.insert_one({"id": "TEST_ui29_db", "from_id": me["id"], "to_id": ad["id"], "venue": "TEST_ui29 Bar", "city": "Toronto", "address": "12 Nowhere Fakeway",
        "postal_code": "M5H 2N2", "country": "Canada", "lat": None, "lng": None, "unverified": True, "scheduled_at": s, "coins": 100, "status": "escrow", "activities": ["a","b","c"], "created_at": s})
    day = (datetime.now(timezone.utc) + timedelta(days=8)).strftime("%Y-%m-%d")
    db.vip_sched.insert_one({"id": "TEST_ui29_vs", "vip_id": ad["id"], "requester_id": me["id"], "date": day, "start": "18:00", "end": "19:00", "status": "pending",
        "venue": "TEST_ui29", "place": "your", "location": {"address": "12 Nowhere Fakeway", "city": "Toronto", "postal_code": "M5H 2N2", "country": "Canada", "lat": None, "lng": None, "unverified": True},
        "coins": 10, "hours": 1, "length": 1, "tz": "UTC", "created_at": s, "scheduled_at": f"{day}T18:00:00"})
    print("seeded")
else:
    s = json.load(open(SNAP))
    upd = {k: v for k, v in s.items() if v is not None}; uns = {k: "" for k, v in s.items() if v is None}
    if upd: db.users.update_one({"id": me["id"]}, {"$set": upd})
    if uns: db.users.update_one({"id": me["id"]}, {"$unset": uns})
    db.date_bookings.delete_many({"id": "TEST_ui29_db"}); db.vip_sched.delete_many({"id": "TEST_ui29_vs"})
    print("cleaned", db.users.find_one({"id": me["id"]}, {"_id": 0, "vip_until": 1, "vip_own_place": 1}))
