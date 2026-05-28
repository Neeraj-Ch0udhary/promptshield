"""
PromptShield API Keys — Full Test
Run: python test_api_keys.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_keys import APIKeyManager

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def test(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"  {status} — {name}" + (f" ({detail})" if detail else ""))

print("\n🔑  PromptShield API Keys — Running Tests\n")

manager = APIKeyManager()

# ── Test 1: Key creation ─────────────────────────────────────────────────────
print("── 1. Key Creation ─────────────────────────────────")
key1 = manager.create_key("acme_corp", "Acme Corporation", plan="pro", monthly_limit=5000)
test("Key generated", key1.startswith("ps_live_"), f"{key1[:16]}...")
test("Key length is sufficient", len(key1) > 40)

key2 = manager.create_key("beta_startup", "Beta Startup", plan="free", monthly_limit=100)
test("Second customer key generated", key2.startswith("ps_live_"))
test("Keys are unique", key1 != key2)

# ── Test 2: Validation ───────────────────────────────────────────────────────
print("\n── 2. Key Validation ───────────────────────────────")
customer = manager.validate_key(key1)
test("Valid key returns customer", customer is not None)
test("Customer ID correct", customer["customer_id"] == "acme_corp")
test("Plan correct", customer["plan"] == "pro")
test("Monthly limit correct", customer["monthly_limit"] == 5000)

invalid = manager.validate_key("ps_live_fakekeyabcdefghijklmnopqrstuvwxyz123")
test("Fake key rejected", invalid is None)

bad_format = manager.validate_key("not_a_key_at_all")
test("Bad format rejected", bad_format is None)

empty = manager.validate_key("")
test("Empty key rejected", empty is None)

# ── Test 3: Usage tracking ───────────────────────────────────────────────────
print("\n── 3. Usage Tracking ───────────────────────────────")
before = manager.get_usage("acme_corp")
initial_calls = before["calls_this_month"]

manager.validate_key(key1)
manager.validate_key(key1)

after = manager.get_usage("acme_corp")
test("Call count increments on validation",
     after["calls_this_month"] == initial_calls + 2,
     f"count={after['calls_this_month']}")
test("last_used_at updated", after["last_used_at"] is not None)

# ── Test 4: Rate limiting ────────────────────────────────────────────────────
print("\n── 4. Rate Limiting ────────────────────────────────")
key3 = manager.create_key("tiny_co", "Tiny Co", plan="free", monthly_limit=2)

r1 = manager.validate_key(key3)
r2 = manager.validate_key(key3)
r3 = manager.validate_key(key3)  # Should be blocked — over limit

test("First call allowed", r1 is not None)
test("Second call allowed", r2 is not None)
test("Third call blocked — over monthly limit", r3 is None)

# ── Test 5: Key revocation ───────────────────────────────────────────────────
print("\n── 5. Key Revocation ───────────────────────────────")
key4 = manager.create_key("revoke_me", "Revoke Test", plan="free")
before_revoke = manager.validate_key(key4)
test("Key valid before revocation", before_revoke is not None)

manager.revoke_key("revoke_me")
after_revoke = manager.validate_key(key4)
test("Key invalid after revocation", after_revoke is None)

# ── Test 6: Customer isolation ───────────────────────────────────────────────
print("\n── 6. Multi-tenant Isolation ───────────────────────")
c1 = manager.get_usage("acme_corp")
c2 = manager.get_usage("beta_startup")
test("acme_corp usage tracked separately", c1["customer_id"] == "acme_corp")
test("beta_startup usage tracked separately", c2["customer_id"] == "beta_startup")
test("Customers don't share call counts", c1["calls_this_month"] != c2["calls_this_month"])

# ── Test 7: List all customers ───────────────────────────────────────────────
print("\n── 7. Admin: List Customers ────────────────────────")
all_customers = manager.list_customers()
ids = [c["customer_id"] for c in all_customers]
test("All customers listed", "acme_corp" in ids and "beta_startup" in ids)
test("Raw key NOT exposed in list", all("key_hash" not in c for c in all_customers))

# ── Final Report ─────────────────────────────────────────────────────────────
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total = len(results)

print(f"\n{'─'*50}")
print(f"  Results: {passed}/{total} passed", end="")
if failed == 0:
    print(" 🎉 All tests passed! API Keys working correctly.")
else:
    print(f"\n  {failed} test(s) failed — check errors above.")
print(f"{'─'*50}\n")