"""Seed UI data for iteration 30 report-window testing (seed:true, iter30ui:true). Prints ids."""
import os, sys, json
sys.path.insert(0, "/app/backend/tests")
from datetime import timedelta
import requests, pymongo
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import test_report_no_auto_cancel as T

db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
for c in ("dates", "date_bookings", "vip_sched"): db[c].delete_many({"iter30ui": True})
a = db.users.find_one({"email": T.ADMIN[0]})["id"]; u = db.users.find_one({"email": T.USER[0]})["id"]
ta, tu = T._login(*T.ADMIN), T._login(*T.USER)
B = T.BASE_URL
out = {}
A = T.seed_invite(db, a, u); requests.post(f"{B}/api/invites/{A}/report", json=T.REP, headers=T.H(ta)); out["inv_open"] = A
C = T.seed_invite(db, a, u); requests.post(f"{B}/api/invites/{C}/report", json=T.REP, headers=T.H(ta))
db.dates.update_one({"id": C}, {"$set": {"report.reply_deadline": (T.now() - timedelta(minutes=5)).isoformat()}}); out["inv_closed"] = C
E = T.seed_invite(db, a, u); out["inv_unreported"] = E
K = T.seed_booking(db, a, u); requests.post(f"{B}/api/dates/report/{K}", json=T.REP, headers=T.H(ta)); out["bk_open"] = K
V = T.seed_vip(db, a, u); requests.post(f"{B}/api/vip/schedule/bookings/{V}/no-show", data={"note": "TEST_ VIP did not come at all"}, headers=T.H(ta)); out["vip_open"] = V
for c, i in (("dates", A), ("dates", C), ("dates", E), ("date_bookings", K), ("vip_sched", V)):
    db[c].update_one({"id": i}, {"$set": {"iter30ui": True}, "$unset": {"iter30": ""}})
print(json.dumps(out))
