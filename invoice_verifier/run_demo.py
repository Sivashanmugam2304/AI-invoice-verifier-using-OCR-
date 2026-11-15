import json
import sys

from app.pipeline import process_invoice

path = sys.argv[1]
result = process_invoice(path)

print("\n==============================")
print("STATUS      :", result["status"])
print("RISK SCORE  :", result["risk_score"], "/ 100")
print("READ VIA    :", result["source"], f"(confidence {result['ocr_confidence']})")
print("PARSER      :", result["parser"])
print("==============================")
print("\nISSUES FOUND:")
if not result["issues"]:
    print("  none")
for i in result["issues"]:
    mark = "CRITICAL" if i["critical"] else f"+{i['points']}"
    print(f"  [{mark}] {i['message']}")
print("\nEXTRACTED DATA:")
print(json.dumps(result["extracted"], indent=2))