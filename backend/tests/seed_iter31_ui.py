"""Seed UI data for iteration 31 (seed:true, iter31ui:true). Prints ids. Pass 'clean' to only delete."""
import os, sys, json, uuid
sys.path.insert(0, "/app/backend/tests")
from datetime import timedelta
import requests, pymongo
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import test_iter31_report_fixes as T

db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
for c in ("dates", "date_bookings"): db[c].delete_many({"iter31ui": True})
if len(sys.argv) > 1 and sys.argv[1] == "clean":
    print("cleaned"); sys.exit(0)
a = db.users.find_one({"email": T.ADMIN[0]})["id"]; u = db.users.find_one({"email": T.USER[0]})["id"]
ta, tu = T._login(*T.ADMIN), T._login(*T.USER)
B = T.BASE_URL
out = {}
A = T.seed_invite(db, a, u); requests.post(f"{B}/api/invites/{A}/report", json=T.REP, headers=T.H(ta)); out["inv_open"] = A
D = T.seed_invite(db, a, u); requests.post(f"{B}/api/invites/{D}/report", json=T.REP, headers=T.H(ta)); out["inv_dismiss"] = D
E = T.seed_invite(db, a, u); out["inv_unreported"] = E


def bk(report):
    bid = f"iter31-bk-{uuid.uuid4().hex[:8]}"
    db.date_bookings.insert_one({"id": bid, "seed": True, "iter31": True, "from_id": a, "to_id": u, "status": "accepted",
                                 "coins": 10, "venue": "TEST bar", "scheduled_at": (T.now() - timedelta(hours=2)).isoformat(),
                                 "created_at": T.now().isoformat()})
    if report:
        requests.post(f"{B}/api/dates/report/{bid}", json=T.REP, headers=T.H(ta))
    return bid


out["bk_open"] = bk(True)
out["bk_plain"] = bk(False)
for c, i in (("dates", A), ("dates", D), ("dates", E), ("date_bookings", out["bk_open"]), ("date_bookings", out["bk_plain"])):
    db[c].update_one({"id": i}, {"$set": {"iter31ui": True}, "$unset": {"iter31": ""}})
print(json.dumps(out))
