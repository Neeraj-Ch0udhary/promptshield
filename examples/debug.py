import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guard_output.checker import OutputGuard

guard = OutputGuard()

source_docs = [
    "Refunds are processed within 5-7 business days.",
    "Premium members get priority refunds within 2 days.",
    "You need your order number to request a refund.",
]

tests = [
    "Refunds are processed within 5-7 business days.",
    "Premium members get refunds within 2 business days.",
    "Refunds happen instantly within 10 minutes.",
]

print("--- Output Guard Debug ---\n")
for response in tests:
    result = guard.check(response, source_docs)
    print(f"Response: {response}")
    for d in result["details"]:
        print(f"  entailment={d['max_entailment']}  contradiction={d['max_contradiction']}  flagged={d['flagged']}")
    print(f"  → consistent={result['consistent']}\n")