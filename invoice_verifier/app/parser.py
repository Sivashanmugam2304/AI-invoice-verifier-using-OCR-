import json
import os
import re

import requests

from app.cancel import Cancelled

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

PROMPT = """You are an invoice data extractor. Read the OCR text of an Indian GST invoice and return ONLY a JSON object with exactly these keys:

{
  "invoice_number": string or null,
  "invoice_date": "YYYY-MM-DD" or null,
  "dealer_name": string or null,
  "dealer_gstin": string or null,
  "buyer_name": string or null,
  "buyer_gstin": string or null,
  "items": [
    {"description": string, "hsn": string or null, "quantity": number or null,
     "rate": number or null, "amount": number or null}
  ],
  "taxable_total": number or null,
  "tax_total": number or null,
  "grand_total": number or null
}

Rules:
- Numbers must be plain numbers (no commas, no currency symbols).
- Copy numbers exactly as they appear. Do NOT correct or calculate them.
- If a value is missing or unreadable, use null. Never guess.
- Output JSON only, no explanation.

OCR TEXT:
"""

GSTIN_RE = r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"


def _to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.\-]", "", str(v))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _normalize(data: dict) -> dict:
    out = {
        "invoice_number": data.get("invoice_number"),
        "invoice_date": data.get("invoice_date"),
        "dealer_name": data.get("dealer_name"),
        "dealer_gstin": data.get("dealer_gstin"),
        "buyer_name": data.get("buyer_name"),
        "buyer_gstin": data.get("buyer_gstin"),
        "taxable_total": _to_float(data.get("taxable_total")),
        "tax_total": _to_float(data.get("tax_total")),
        "grand_total": _to_float(data.get("grand_total")),
        "items": [],
    }
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        out["items"].append({
            "description": it.get("description"),
            "hsn": it.get("hsn"),
            "quantity": _to_float(it.get("quantity")),
            "rate": _to_float(it.get("rate")),
            "amount": _to_float(it.get("amount")),
        })
    return out


def _parse_with_qwen(text: str, should_cancel=None) -> dict:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": PROMPT + text[:12000]}],
            "stream": True,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 8192},
        },
        timeout=300,
        stream=True,
    )
    try:
        resp.raise_for_status()
        parts = []
        for line in resp.iter_lines():
            if should_cancel and should_cancel():
                raise Cancelled()
            if not line:
                continue
            chunk = json.loads(line)
            parts.append(chunk.get("message", {}).get("content", ""))
            if chunk.get("done"):
                break
    finally:
        resp.close()          # closing the connection makes Ollama stop generating
    return json.loads("".join(parts))


def _parse_with_regex(text: str) -> dict:
    """Fallback when Qwen/Ollama is not available. Less complete, but works."""
    def find(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    gstins = re.findall(GSTIN_RE, text)
    amounts = [_to_float(a) for a in re.findall(r"\d[\d,]*\.\d{2}", text)]
    amounts = [a for a in amounts if a is not None]

    return {
        "invoice_number": find(r"Invoice\s*No\.?\s*[:\-]?\s*([A-Z0-9/\-]{3,})"),
        "invoice_date": find(r"(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})"),
        "dealer_name": None,
        "dealer_gstin": gstins[0] if gstins else None,
        "buyer_name": None,
        "buyer_gstin": gstins[1] if len(gstins) > 1 else None,
        "items": [],
        "taxable_total": None,
        "tax_total": None,
        "grand_total": max(amounts) if amounts else None,
    }


def parse_invoice(text: str, should_cancel=None) -> tuple[dict, str]:
    """Returns (structured_data, parser_used)."""
    try:
        return _normalize(_parse_with_qwen(text, should_cancel)), "qwen"
    except Cancelled:
        raise
    except Exception as e:
        detail = ""
        resp = getattr(e, "response", None)
        if resp is not None:
            detail = resp.text[:300]
        print(f"[parser] Qwen failed: {type(e).__name__}: {e} {detail}")
        print(f"[parser] Using model '{OLLAMA_MODEL}'. Using regex fallback.")
        return _normalize(_parse_with_regex(text)), "regex_fallback"