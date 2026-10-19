#!/usr/bin/env python3
"""
Backend test for video call functionality
Tests all scenarios from the review request
"""
import requests
import time
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import os

# Load environment variables
BACKEND_URL = "https://gifts-dates.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

# Connect to MongoDB
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def register_user(email, password, name, gender, age, interested_in, city, country):
    """Register a new user"""
    resp = requests.post(f"{BACKEND_URL}/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
        "gender": gender,
        "age": age,
        "interested_in": interested_in,
        "city": city,
        "country": country
    })
    if resp.status_code != 200:
        log(f"❌ Registration failed for {email}: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    log(f"✅ Registered user: {email}")
    return {"token": data["token"], "user_id": data["user"]["id"], "email": email}

def setup_user_for_videocall(user_id, coins=500, online=True, video_enabled=True):
    """Setup user in database for video call testing"""
    update = {
        "coins": coins,
        "video_calls_enabled": video_enabled
    }
    if online:
        update["last_seen"] = datetime.now(timezone.utc).isoformat()
    else:
        # Set last_seen to 1 hour ago for offline test
        update["last_seen"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    
    db.users.update_one({"id": user_id}, {"$set": update})
    log(f"✅ Setup user {user_id}: coins={coins}, online={online}, video_enabled={video_enabled}")

def cleanup_test_users(emails):
    """Clean up test users from database"""
    for email in emails:
        db.users.delete_many({"email": email})
        db.new_users_list.delete_many({"email": email})
    log(f"✅ Cleaned up {len(emails)} test users")

def run_tests():
    """Run all video call tests"""
    test_emails = []
    all_passed = True
    
    try:
        # Create test users
        timestamp = int(time.time())
        caller_email = f"test_caller_{timestamp}@example.com"
        callee_email = f"test_callee_{timestamp}@example.com"
        third_user_email = f"test_third_{timestamp}@example.com"
        
        test_emails = [caller_email, callee_email, third_user_email]
        
        log("\n=== SETUP: Creating test users ===")
        caller = register_user(caller_email, "Password123!", "Alice Caller", "female", 28, "male", "New York", "USA")
        callee = register_user(callee_email, "Password123!", "Bob Callee", "male", 30, "female", "Los Angeles", "USA")
        third_user = register_user(third_user_email, "Password123!", "Charlie Third", "male", 25, "female", "Chicago", "USA")
        
        if not caller or not callee or not third_user:
            log("❌ Failed to create test users")
            return False
        
        # Setup users for video calls
        setup_user_for_videocall(caller["user_id"], coins=500, online=True, video_enabled=True)
        setup_user_for_videocall(callee["user_id"], coins=0, online=True, video_enabled=True)
        setup_user_for_videocall(third_user["user_id"], coins=100, online=True, video_enabled=True)
        
        # Set default video_rate in settings
        db.settings.update_one({}, {"$set": {"video_rate": 10}}, upsert=True)
        
        log("\n=== TEST 1: Start call (minutes=2) -> status 'ringing', cost=20, caller coins NOT reduced ===")
        resp = requests.post(f"{BACKEND_URL}/videocalls/start", 
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": callee["user_id"], "minutes": 2})
        if resp.status_code != 200:
            log(f"❌ Start call failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            call_data = resp.json()
            call_id = call_data["id"]
            if call_data["status"] != "ringing":
                log(f"❌ Expected status 'ringing', got '{call_data['status']}'")
                all_passed = False
            elif call_data["cost"] != 20:
                log(f"❌ Expected cost 20, got {call_data['cost']}")
                all_passed = False
            else:
                # Check caller coins NOT reduced yet
                caller_db = db.users.find_one({"id": caller["user_id"]})
                if caller_db["coins"] != 500:
                    log(f"❌ Caller coins should still be 500, got {caller_db['coins']}")
                    all_passed = False
                else:
                    log(f"✅ Call started: id={call_id}, status=ringing, cost=20, caller coins=500 (not reduced)")
        
        log("\n=== TEST 2: Callee GET incoming lists it; caller's incoming is empty; third user 404 ===")
        # Callee incoming
        resp = requests.get(f"{BACKEND_URL}/videocalls/incoming",
                           headers={"Authorization": f"Bearer {callee['token']}"})
        if resp.status_code != 200:
            log(f"❌ Callee incoming failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            incoming = resp.json()
            if len(incoming) != 1 or incoming[0]["id"] != call_id:
                log(f"❌ Callee should see 1 incoming call, got {len(incoming)}")
                all_passed = False
            else:
                log(f"✅ Callee sees incoming call: {call_id}")
        
        # Caller incoming (should be empty)
        resp = requests.get(f"{BACKEND_URL}/videocalls/incoming",
                           headers={"Authorization": f"Bearer {caller['token']}"})
        if resp.status_code != 200:
            log(f"❌ Caller incoming failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            incoming = resp.json()
            if len(incoming) != 0:
                log(f"❌ Caller should see 0 incoming calls, got {len(incoming)}")
                all_passed = False
            else:
                log(f"✅ Caller incoming is empty")
        
        # Third user GET call (should be 404)
        resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id}",
                           headers={"Authorization": f"Bearer {third_user['token']}"})
        if resp.status_code != 404:
            log(f"❌ Third user should get 404, got {resp.status_code}")
            all_passed = False
        else:
            log(f"✅ Third user gets 404 for call")
        
        log("\n=== TEST 3: Caller tries accept -> 403; Callee accept -> 200, status 'active', coins reduced ===")
        # Caller tries to accept (should fail)
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/accept",
                            headers={"Authorization": f"Bearer {caller['token']}"})
        if resp.status_code != 403:
            log(f"❌ Caller accept should return 403, got {resp.status_code}")
            all_passed = False
        else:
            log(f"✅ Caller cannot accept (403)")
        
        # Callee accepts
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/accept",
                            headers={"Authorization": f"Bearer {callee['token']}"})
        if resp.status_code != 200:
            log(f"❌ Callee accept failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            call_data = resp.json()
            if call_data["status"] != "active":
                log(f"❌ Expected status 'active', got '{call_data['status']}'")
                all_passed = False
            else:
                # Check caller coins reduced by 20
                caller_db = db.users.find_one({"id": caller["user_id"]})
                caller_total = caller_db.get("coins", 0) + caller_db.get("withdrawable", 0)
                if caller_total != 480:  # 500 - 20
                    log(f"❌ Caller total should be 480, got {caller_total}")
                    all_passed = False
                else:
                    # Check callee withdrawable increased by 20
                    callee_db = db.users.find_one({"id": callee["user_id"]})
                    if callee_db.get("withdrawable", 0) != 20:
                        log(f"❌ Callee withdrawable should be 20, got {callee_db.get('withdrawable', 0)}")
                        all_passed = False
                    else:
                        # Check transaction exists
                        txn = db.transactions.find_one({"id": call_id, "type": "videocall"})
                        if not txn:
                            log(f"❌ Transaction not found for call {call_id}")
                            all_passed = False
                        else:
                            log(f"✅ Call accepted: status=active, caller charged 20, callee +20 withdrawable, transaction created")
        
        log("\n=== TEST 4: Signals - offer/answer/ice with timestamps ===")
        # Caller posts offer
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/signal",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"type": "offer", "data": {"type": "offer", "sdp": "x"}})
        if resp.status_code != 200:
            log(f"❌ Caller signal offer failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            log(f"✅ Caller posted offer signal")
        
        # Callee gets signals
        resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id}/signals?after=0",
                           headers={"Authorization": f"Bearer {callee['token']}"})
        if resp.status_code != 200:
            log(f"❌ Callee get signals failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            signals_data = resp.json()
            if len(signals_data["signals"]) != 1:
                log(f"❌ Callee should see 1 signal, got {len(signals_data['signals'])}")
                all_passed = False
            elif signals_data["signals"][0]["type"] != "offer":
                log(f"❌ Expected signal type 'offer', got '{signals_data['signals'][0]['type']}'")
                all_passed = False
            elif "ts" not in signals_data["signals"][0]:
                log(f"❌ Signal should have 'ts' field")
                all_passed = False
            else:
                last_ts = signals_data["signals"][0]["ts"]
                log(f"✅ Callee received offer signal with ts={last_ts}")
        
        # Caller gets signals (should be empty)
        resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id}/signals?after=0",
                           headers={"Authorization": f"Bearer {caller['token']}"})
        if resp.status_code != 200:
            log(f"❌ Caller get signals failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            signals_data = resp.json()
            if len(signals_data["signals"]) != 0:
                log(f"❌ Caller should see 0 signals, got {len(signals_data['signals'])}")
                all_passed = False
            else:
                log(f"✅ Caller signals empty (correct)")
        
        # Callee posts answer and ice
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/signal",
                            headers={"Authorization": f"Bearer {callee['token']}"},
                            json={"type": "answer", "data": {"type": "answer", "sdp": "y"}})
        if resp.status_code != 200:
            log(f"❌ Callee signal answer failed: {resp.status_code} {resp.text}")
            all_passed = False
        
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/signal",
                            headers={"Authorization": f"Bearer {callee['token']}"},
                            json={"type": "ice", "data": {"candidate": "ice-candidate"}})
        if resp.status_code != 200:
            log(f"❌ Callee signal ice failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            log(f"✅ Callee posted answer and ice signals")
        
        # Caller receives both in ts order
        resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id}/signals?after=0",
                           headers={"Authorization": f"Bearer {caller['token']}"})
        if resp.status_code != 200:
            log(f"❌ Caller get signals failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            signals_data = resp.json()
            if len(signals_data["signals"]) != 2:
                log(f"❌ Caller should see 2 signals, got {len(signals_data['signals'])}")
                all_passed = False
            elif signals_data["signals"][0]["type"] != "answer" or signals_data["signals"][1]["type"] != "ice":
                log(f"❌ Expected signals in order: answer, ice")
                all_passed = False
            elif signals_data["signals"][0]["ts"] >= signals_data["signals"][1]["ts"]:
                log(f"❌ Signals should be in ts order")
                all_passed = False
            else:
                last_ts = signals_data["signals"][1]["ts"]
                log(f"✅ Caller received answer and ice signals in ts order")
                
                # GET with after=last_ts should return empty
                resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id}/signals?after={last_ts}",
                                   headers={"Authorization": f"Bearer {caller['token']}"})
                if resp.status_code != 200:
                    log(f"❌ Caller get signals with after failed: {resp.status_code} {resp.text}")
                    all_passed = False
                else:
                    signals_data = resp.json()
                    if len(signals_data["signals"]) != 0:
                        log(f"❌ Signals with after={last_ts} should be empty, got {len(signals_data['signals'])}")
                        all_passed = False
                    else:
                        log(f"✅ GET signals with after={last_ts} returns empty")
        
        # Bad signal type -> 400
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/signal",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"type": "invalid", "data": {}})
        if resp.status_code != 400:
            log(f"❌ Bad signal type should return 400, got {resp.status_code}")
            all_passed = False
        else:
            log(f"✅ Bad signal type returns 400")
        
        log("\n=== TEST 5: End call -> status 'ended', signals return status 'ended', posting signal -> 409 ===")
        # Caller ends call
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/end",
                            headers={"Authorization": f"Bearer {caller['token']}"})
        if resp.status_code != 200:
            log(f"❌ End call failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            log(f"✅ Call ended")
        
        # Callee gets signals -> status 'ended'
        resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id}/signals?after=0",
                           headers={"Authorization": f"Bearer {callee['token']}"})
        if resp.status_code != 200:
            log(f"❌ Callee get signals failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            signals_data = resp.json()
            if signals_data["status"] != "ended":
                log(f"❌ Expected status 'ended', got '{signals_data['status']}'")
                all_passed = False
            else:
                log(f"✅ Callee signals show status 'ended'")
        
        # Posting signal now -> 409
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/signal",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"type": "offer", "data": {}})
        if resp.status_code != 409:
            log(f"❌ Posting signal to ended call should return 409, got {resp.status_code}")
            all_passed = False
        else:
            log(f"✅ Posting signal to ended call returns 409")
        
        # Accept again -> 409
        resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id}/accept",
                            headers={"Authorization": f"Bearer {callee['token']}"})
        if resp.status_code != 409:
            log(f"❌ Accepting ended call should return 409, got {resp.status_code}")
            all_passed = False
        else:
            log(f"✅ Accepting ended call returns 409")
        
        log("\n=== TEST 6: Decline - callee decline -> status 'declined', caller NOT charged ===")
        # Start new call
        resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": callee["user_id"], "minutes": 2})
        if resp.status_code != 200:
            log(f"❌ Start call failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            call_id_2 = resp.json()["id"]
            log(f"✅ Started new call: {call_id_2}")
            
            # Get caller coins before decline
            caller_db = db.users.find_one({"id": caller["user_id"]})
            caller_coins_before = caller_db.get("coins", 0) + caller_db.get("withdrawable", 0)
            
            # Callee declines
            resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id_2}/decline",
                                headers={"Authorization": f"Bearer {callee['token']}"})
            if resp.status_code != 200:
                log(f"❌ Decline call failed: {resp.status_code} {resp.text}")
                all_passed = False
            else:
                # Check status is 'declined'
                call_doc = db.calls.find_one({"id": call_id_2})
                if call_doc["status"] != "declined":
                    log(f"❌ Expected status 'declined', got '{call_doc['status']}'")
                    all_passed = False
                else:
                    # Check caller NOT charged
                    caller_db = db.users.find_one({"id": caller["user_id"]})
                    caller_coins_after = caller_db.get("coins", 0) + caller_db.get("withdrawable", 0)
                    if caller_coins_before != caller_coins_after:
                        log(f"❌ Caller should not be charged on decline, coins changed from {caller_coins_before} to {caller_coins_after}")
                        all_passed = False
                    else:
                        log(f"✅ Callee declined: status='declined', caller NOT charged")
        
        log("\n=== TEST 6b: Cancel - caller calls decline on ringing call -> 'cancelled' ===")
        # Start new call
        resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": callee["user_id"], "minutes": 2})
        if resp.status_code != 200:
            log(f"❌ Start call failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            call_id_3 = resp.json()["id"]
            log(f"✅ Started new call: {call_id_3}")
            
            # Caller cancels (calls decline)
            resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id_3}/decline",
                                headers={"Authorization": f"Bearer {caller['token']}"})
            if resp.status_code != 200:
                log(f"❌ Cancel call failed: {resp.status_code} {resp.text}")
                all_passed = False
            else:
                # Check status is 'cancelled'
                call_doc = db.calls.find_one({"id": call_id_3})
                if call_doc["status"] != "cancelled":
                    log(f"❌ Expected status 'cancelled', got '{call_doc['status']}'")
                    all_passed = False
                else:
                    log(f"✅ Caller cancelled: status='cancelled'")
        
        log("\n=== TEST 7: Missed - created_at 40s ago -> 'missed', accept -> 409 ===")
        # Start new call
        resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": callee["user_id"], "minutes": 2})
        if resp.status_code != 200:
            log(f"❌ Start call failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            call_id_4 = resp.json()["id"]
            log(f"✅ Started new call: {call_id_4}")
            
            # Set created_at to 40s ago
            old_time = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
            db.calls.update_one({"id": call_id_4}, {"$set": {"created_at": old_time}})
            log(f"✅ Set created_at to 40s ago")
            
            # GET call -> should be 'missed'
            resp = requests.get(f"{BACKEND_URL}/videocalls/{call_id_4}",
                               headers={"Authorization": f"Bearer {callee['token']}"})
            if resp.status_code != 200:
                log(f"❌ Get call failed: {resp.status_code} {resp.text}")
                all_passed = False
            else:
                call_data = resp.json()
                if call_data["status"] != "missed":
                    log(f"❌ Expected status 'missed', got '{call_data['status']}'")
                    all_passed = False
                else:
                    log(f"✅ Call status is 'missed'")
                    
                    # Try to accept -> 409
                    resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id_4}/accept",
                                        headers={"Authorization": f"Bearer {callee['token']}"})
                    if resp.status_code != 409:
                        log(f"❌ Accepting missed call should return 409, got {resp.status_code}")
                        all_passed = False
                    else:
                        log(f"✅ Accepting missed call returns 409")
        
        log("\n=== TEST 8: Errors - offline, disabled, insufficient coins, call self ===")
        # Create offline user
        offline_email = f"test_offline_{timestamp}@example.com"
        test_emails.append(offline_email)
        offline_user = register_user(offline_email, "Password123!", "Offline User", "female", 25, "male", "Boston", "USA")
        if offline_user:
            setup_user_for_videocall(offline_user["user_id"], coins=100, online=False, video_enabled=True)
            
            # Try to call offline user -> 403 USER_OFFLINE
            resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                                headers={"Authorization": f"Bearer {caller['token']}"},
                                json={"target_id": offline_user["user_id"], "minutes": 2})
            if resp.status_code != 403 or "USER_OFFLINE" not in resp.text:
                log(f"❌ Calling offline user should return 403 USER_OFFLINE, got {resp.status_code} {resp.text}")
                all_passed = False
            else:
                log(f"✅ Calling offline user returns 403 USER_OFFLINE")
        
        # Create user with video_calls_enabled=False
        disabled_email = f"test_disabled_{timestamp}@example.com"
        test_emails.append(disabled_email)
        disabled_user = register_user(disabled_email, "Password123!", "Disabled User", "male", 27, "female", "Seattle", "USA")
        if disabled_user:
            setup_user_for_videocall(disabled_user["user_id"], coins=100, online=True, video_enabled=False)
            
            # Try to call user with video disabled -> 403 VIDEO_CALLS_DISABLED
            resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                                headers={"Authorization": f"Bearer {caller['token']}"},
                                json={"target_id": disabled_user["user_id"], "minutes": 2})
            if resp.status_code != 403 or "VIDEO_CALLS_DISABLED" not in resp.text:
                log(f"❌ Calling user with video disabled should return 403 VIDEO_CALLS_DISABLED, got {resp.status_code} {resp.text}")
                all_passed = False
            else:
                log(f"✅ Calling user with video disabled returns 403 VIDEO_CALLS_DISABLED")
        
        # Caller with 0 coins -> 400
        db.users.update_one({"id": caller["user_id"]}, {"$set": {"coins": 0, "withdrawable": 0}})
        resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": callee["user_id"], "minutes": 2})
        if resp.status_code != 400:
            log(f"❌ Calling with 0 coins should return 400, got {resp.status_code}")
            all_passed = False
        else:
            log(f"✅ Calling with 0 coins returns 400")
        
        # Restore caller coins for next test
        db.users.update_one({"id": caller["user_id"]}, {"$set": {"coins": 500, "withdrawable": 0}})
        
        # Call self -> 400
        resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": caller["user_id"], "minutes": 2})
        if resp.status_code != 400 or "CANNOT_CALL_SELF" not in resp.text:
            log(f"❌ Calling self should return 400 CANNOT_CALL_SELF, got {resp.status_code} {resp.text}")
            all_passed = False
        else:
            log(f"✅ Calling self returns 400 CANNOT_CALL_SELF")
        
        log("\n=== TEST 9: Insufficient at accept - caller coins 0 at accept -> 400 CALLER_INSUFFICIENT_COINS, status 'failed' ===")
        # Start new call
        resp = requests.post(f"{BACKEND_URL}/videocalls/start",
                            headers={"Authorization": f"Bearer {caller['token']}"},
                            json={"target_id": callee["user_id"], "minutes": 2})
        if resp.status_code != 200:
            log(f"❌ Start call failed: {resp.status_code} {resp.text}")
            all_passed = False
        else:
            call_id_5 = resp.json()["id"]
            log(f"✅ Started new call: {call_id_5}")
            
            # Set caller coins to 0
            db.users.update_one({"id": caller["user_id"]}, {"$set": {"coins": 0, "withdrawable": 0}})
            log(f"✅ Set caller coins to 0")
            
            # Callee tries to accept -> 400 CALLER_INSUFFICIENT_COINS
            resp = requests.post(f"{BACKEND_URL}/videocalls/{call_id_5}/accept",
                                headers={"Authorization": f"Bearer {callee['token']}"})
            if resp.status_code != 400 or "CALLER_INSUFFICIENT_COINS" not in resp.text:
                log(f"❌ Accept with insufficient caller coins should return 400 CALLER_INSUFFICIENT_COINS, got {resp.status_code} {resp.text}")
                all_passed = False
            else:
                # Check call status is 'failed'
                call_doc = db.calls.find_one({"id": call_id_5})
                if call_doc["status"] != "failed":
                    log(f"❌ Expected status 'failed', got '{call_doc['status']}'")
                    all_passed = False
                elif call_doc.get("reason") != "CALLER_INSUFFICIENT_COINS":
                    log(f"❌ Expected reason 'CALLER_INSUFFICIENT_COINS', got '{call_doc.get('reason')}'")
                    all_passed = False
                else:
                    log(f"✅ Accept with insufficient caller coins returns 400 CALLER_INSUFFICIENT_COINS, call status='failed'")
        
        log("\n=== CLEANUP ===")
        cleanup_test_users(test_emails)
        
        return all_passed
        
    except Exception as e:
        log(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        # Cleanup on error
        if test_emails:
            cleanup_test_users(test_emails)
        return False

if __name__ == "__main__":
    log("=== Starting Video Call Backend Tests ===")
    success = run_tests()
    if success:
        log("\n✅ ALL TESTS PASSED")
    else:
        log("\n❌ SOME TESTS FAILED")
    exit(0 if success else 1)
