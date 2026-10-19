#!/usr/bin/env python3
"""
Backend smoke test for GiftsDates profile/VIP field changes.
TEST 1: Profile dick_girth field persistence
TEST 2: VIP breast_size as a LIST (multi-select)
"""
import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://giftsdate-saver.preview.emergentagent.com/api"

def log(msg):
    """Print timestamped log message."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_register():
    """Register a new user and return token."""
    log("Registering new test user...")
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    test_user = {
        "email": f"testuser_{timestamp}@example.com",
        "password": "SecurePass123!",
        "name": "Test User Profile VIP",
        "age": 28,
        "gender": "female",
        "interested_in": "male",
        "orientation": "straight",
        "city": "Los Angeles",
        "country": "USA",
        "bio": "Testing profile and VIP fields",
        "birth_year": 1996,
        "birth_month": 3,
        "birth_day": 20
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/register",
            json=test_user,
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return None, None
        
        data = response.json()
        
        if "token" not in data or "user" not in data:
            log(f"  ❌ FAILED: Missing token or user in response")
            return None, None
        
        token = data["token"]
        user = data["user"]
        
        log(f"  ✅ User registered: {user.get('email')}")
        log(f"  Token: {token[:20]}...")
        
        return token, test_user
        
    except Exception as e:
        log(f"  ❌ FAILED: {str(e)}")
        return None, None

def test_dick_girth_field(token):
    """
    TEST 1: Profile girth field (dick_girth)
    1. PATCH /api/auth/me with {"dick_girth": "Thick"} → expect 200
    2. GET /api/auth/me → confirm "dick_girth": "Thick" is returned
    """
    log("\n" + "="*60)
    log("TEST 1: Profile dick_girth field")
    log("="*60)
    
    try:
        # Step 1: PATCH with dick_girth = "Thick"
        log("Step 1: Setting dick_girth to 'Thick' via PATCH /api/auth/me...")
        response = requests.patch(
            f"{BACKEND_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"dick_girth": "Thick"},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
        
        data = response.json()
        if data.get("dick_girth") != "Thick":
            log(f"  ❌ FAILED: PATCH response dick_girth is '{data.get('dick_girth')}', expected 'Thick'")
            log(f"  Full response: {json.dumps(data, indent=2)}")
            return False
        log(f"  ✅ PATCH successful, dick_girth set to 'Thick'")
        
        # Step 2: GET to verify dick_girth = "Thick"
        log("Step 2: Verifying dick_girth is 'Thick' via GET /api/auth/me...")
        response = requests.get(
            f"{BACKEND_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
        
        data = response.json()
        if data.get("dick_girth") != "Thick":
            log(f"  ❌ FAILED: GET response dick_girth is '{data.get('dick_girth')}', expected 'Thick'")
            log(f"  Full response: {json.dumps(data, indent=2)}")
            return False
        log(f"  ✅ GET confirmed dick_girth is 'Thick'")
        
        log("\n✅ TEST 1 PASSED: dick_girth field persists correctly")
        return True
        
    except Exception as e:
        log(f"  ❌ FAILED: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return False

def test_vip_breast_size_list(token):
    """
    TEST 2: VIP breast_size is now a LIST (multi-select)
    1. PUT /api/vip/profile with breast_size: ["A", "C", "Natural"] → expect 200
    2. GET /api/auth/me and check vip.breast_size is ["A", "C", "Natural"]
    3. PUT with breast_size: [] → expect 200 and confirm it saves as []
    """
    log("\n" + "="*60)
    log("TEST 2: VIP breast_size as LIST")
    log("="*60)
    
    try:
        # Step 1: PUT VIP profile with breast_size as a list
        log("Step 1: Saving VIP profile with breast_size: ['A', 'C', 'Natural']...")
        
        # Minimal valid VIP profile body with breast_size as list
        vip_profile = {
            "services": ["Минет в презервативе", "Поцелуи с языком"],
            "services_note": "Test services",
            "price_hour": 100,
            "price_2h": 180,
            "price_3h": 250,
            "price_night": 500,
            "places": ["own", "your"],
            "client_wants": "Test client wants",
            "availability": [],
            "published": False,  # Not publishing, just saving
            "nickname": "TestVIP",
            "post_mode": "together",
            "age": 28,
            "city": "Los Angeles",
            "country": "USA",
            "gender": "female",
            "genders": ["female"],
            "bio": "Test VIP bio",
            "height": 170,
            "weight": 60,
            "eye_color": "Blue",
            "hair_color": "Blonde",
            "intimate_haircut": "Smooth",
            "breast_size": ["A", "C", "Natural"],  # LIST of strings
            "dick_size": "",
            "dick_girth": "",
            "show_on_main": True
        }
        
        response = requests.put(
            f"{BACKEND_URL}/vip/profile",
            headers={"Authorization": f"Bearer {token}"},
            json=vip_profile,
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
        
        data = response.json()
        if not data.get("saved"):
            log(f"  ❌ FAILED: VIP profile not saved")
            log(f"  Response: {json.dumps(data, indent=2)}")
            return False
        
        vip_data = data.get("vip", {})
        breast_size = vip_data.get("breast_size")
        
        if not isinstance(breast_size, list):
            log(f"  ❌ FAILED: breast_size is not a list, got type: {type(breast_size)}")
            log(f"  breast_size value: {breast_size}")
            return False
        
        if breast_size != ["A", "C", "Natural"]:
            log(f"  ❌ FAILED: breast_size is {breast_size}, expected ['A', 'C', 'Natural']")
            return False
        
        log(f"  ✅ PUT successful, breast_size saved as list: {breast_size}")
        
        # Step 2: GET /api/auth/me and verify vip.breast_size
        log("Step 2: Fetching profile via GET /api/auth/me to verify vip.breast_size...")
        response = requests.get(
            f"{BACKEND_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
        
        data = response.json()
        vip_data = data.get("vip", {})
        breast_size = vip_data.get("breast_size")
        
        if not isinstance(breast_size, list):
            log(f"  ❌ FAILED: breast_size is not a list in GET response, got type: {type(breast_size)}")
            log(f"  breast_size value: {breast_size}")
            return False
        
        if breast_size != ["A", "C", "Natural"]:
            log(f"  ❌ FAILED: GET response breast_size is {breast_size}, expected ['A', 'C', 'Natural']")
            return False
        
        log(f"  ✅ GET confirmed breast_size is a list: {breast_size}")
        
        # Step 3: PUT with empty list
        log("Step 3: Saving VIP profile with breast_size: [] (empty list)...")
        vip_profile["breast_size"] = []
        
        response = requests.put(
            f"{BACKEND_URL}/vip/profile",
            headers={"Authorization": f"Bearer {token}"},
            json=vip_profile,
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            log(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
        
        data = response.json()
        vip_data = data.get("vip", {})
        breast_size = vip_data.get("breast_size")
        
        if not isinstance(breast_size, list):
            log(f"  ❌ FAILED: breast_size is not a list, got type: {type(breast_size)}")
            log(f"  breast_size value: {breast_size}")
            return False
        
        if breast_size != []:
            log(f"  ❌ FAILED: breast_size is {breast_size}, expected []")
            return False
        
        log(f"  ✅ PUT successful, breast_size saved as empty list: {breast_size}")
        
        log("\n✅ TEST 2 PASSED: VIP breast_size correctly handles LIST values")
        return True
        
    except Exception as e:
        log(f"  ❌ FAILED: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return False

def main():
    """Run profile and VIP field tests."""
    log("=" * 60)
    log("GiftsDates Profile/VIP Field Changes Smoke Test")
    log("=" * 60)
    log(f"Backend URL: {BACKEND_URL}")
    log("")
    
    results = {
        "test_1_dick_girth": False,
        "test_2_vip_breast_size_list": False
    }
    
    # Register a new user
    token, test_user = test_register()
    
    if not token:
        log("\n❌ Registration failed, cannot proceed with tests")
        print_summary(results)
        return 1
    
    log("")
    
    # TEST 1: dick_girth field
    results["test_1_dick_girth"] = test_dick_girth_field(token)
    
    # TEST 2: VIP breast_size as list
    results["test_2_vip_breast_size_list"] = test_vip_breast_size_list(token)
    
    # Print summary
    print_summary(results)
    
    # Return exit code
    return 0 if all(results.values()) else 1

def print_summary(results):
    """Print test summary."""
    log("\n" + "=" * 60)
    log("TEST SUMMARY")
    log("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        display_name = test_name.replace("_", " ").replace("test ", "TEST ").upper()
        log(f"{display_name}: {status}")
    
    log("")
    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    log(f"Total: {passed_count}/{total_count} tests passed")
    log("=" * 60)

if __name__ == "__main__":
    sys.exit(main())
