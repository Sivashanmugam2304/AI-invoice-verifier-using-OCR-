import re
from datetime import date, datetime

import numpy as np
from sklearn.ensemble import IsolationForest

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
TOLERANCE = 1.0   # rupees; allows for round-off


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None


def verify_rules(data: dict, ocr_conf: float, source: str, parser_used: str,
                 is_duplicate: bool, history_totals: list[float]) -> list[dict]:
    """Returns a list of issues: {code, message, points, critical}."""
    issues = []

    def add(code, message, points, critical=False):
        issues.append({"code": code, "message": message,
                       "points": points, "critical": critical})

    # 1. Required fields
    for field, pts in [("invoice_number", 25), ("invoice_date", 15),
                       ("dealer_name", 15), ("grand_total", 25)]:
        if not data.get(field):
            add(f"missing_{field}", f"Missing {field.replace('_', ' ')}", pts)

    # 2. GSTIN format
    dg = data.get("dealer_gstin")
    if not dg:
        add("missing_dealer_gstin", "Dealer GSTIN not found", 15)
    elif not GSTIN_RE.match(dg.strip().upper()):
        add("bad_dealer_gstin", f"Dealer GSTIN '{dg}' has an invalid format", 25)
    bg = data.get("buyer_gstin")
    if bg and not GSTIN_RE.match(bg.strip().upper()):
        add("bad_buyer_gstin", f"Buyer GSTIN '{bg}' has an invalid format", 10)

    # 3. Date sanity
    d = _parse_date(data.get("invoice_date"))
    if data.get("invoice_date") and d is None:
        add("bad_date", f"Invoice date '{data['invoice_date']}' is not readable", 15)
    elif d:
        if d > date.today():
            add("future_date", f"Invoice date {d} is in the future", 40, critical=True)
        elif (date.today() - d).days > 365:
            add("old_date", f"Invoice date {d} is more than a year old", 10)

    # 4. Line item math: quantity x rate = amount
    bad_lines = 0
    for i, it in enumerate(data.get("items") or [], start=1):
        q, r, a = it.get("quantity"), it.get("rate"), it.get("amount")
        if None not in (q, r, a):
            if abs(q * r - a) > max(TOLERANCE, 0.01 * abs(a)):
                bad_lines += 1
    if bad_lines:
        add("line_math", f"{bad_lines} line item(s): quantity x rate does not match amount",
            min(10 * bad_lines, 30))

    # 5. Items add up to taxable total
    items_sum = sum(it["amount"] for it in data.get("items") or []
                    if it.get("amount") is not None)
    taxable = data.get("taxable_total")
    if taxable is not None and items_sum and abs(items_sum - taxable) > max(TOLERANCE, 0.01 * taxable):
        add("items_vs_taxable",
            f"Item amounts add up to {items_sum:.2f} but taxable total is {taxable:.2f}", 25)

    # 6. Taxable + tax = grand total
    tax, grand = data.get("tax_total"), data.get("grand_total")
    if None not in (taxable, tax, grand):
        if abs(taxable + tax - grand) > TOLERANCE:
            add("total_math",
                f"Taxable {taxable:.2f} + tax {tax:.2f} = {taxable + tax:.2f}, "
                f"but grand total is {grand:.2f}", 35)

    # 7. Duplicate invoice
    if is_duplicate:
        add("duplicate", "An invoice with this number from this dealer already exists",
            60, critical=True)

    # 8. OCR quality / parser quality
    if source == "ocr" and ocr_conf < 0.80:
        add("low_ocr_conf", f"OCR confidence is low ({ocr_conf:.2f})", 15)
    if parser_used != "qwen":
        add("parser_fallback", "Qwen was not used; fields extracted with basic rules", 10)

    # 9. ML anomaly check on invoice amount (needs history)
    if grand is not None and len(history_totals) >= 10:
        model = IsolationForest(contamination=0.05, random_state=42)
        model.fit(np.array(history_totals).reshape(-1, 1))
        if model.predict([[grand]])[0] == -1:
            add("amount_anomaly",
                f"Invoice amount {grand:.2f} is unusual compared with past invoices", 20)

    return issues