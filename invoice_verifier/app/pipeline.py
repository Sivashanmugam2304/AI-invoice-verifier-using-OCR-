import os
import threading
import time
from datetime import datetime

from app import cancel
from app.db import get_history_totals, init_db, invoice_exists, save_invoice
from app.decision import decide
from app.ocr import lines_to_text, run_ocr
from app.parser import parse_invoice
from app.pdf_text import extract_text_layer
from app.preprocess import load_images, preprocess
from app.verify import verify_rules

MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))
_run_lock = threading.Lock()      # one invoice at a time


def extract_text(path: str, job_id=None) -> tuple[str, float, str]:
    """Returns (text, confidence, source). Uses the PDF text layer if it exists."""
    layer = extract_text_layer(path)
    if layer is not None:
        return "\n".join(layer), 1.0, "text_layer"

    texts, scores = [], []
    for img in load_images(path)[:MAX_PAGES]:
        cancel.check(job_id)
        lines = run_ocr(preprocess(img))
        cancel.check(job_id)
        texts.append(lines_to_text(lines))
        scores += [l["score"] for l in lines]
    conf = sum(scores) / len(scores) if scores else 0.0
    return "\n--- page ---\n".join(texts), conf, "ocr"


def process_invoice(path: str, save: bool = True, job_id: str | None = None) -> dict:
    init_db()
    cancel.register(job_id)
    try:
        with _run_lock:
            cancel.check(job_id)
            started = datetime.utcnow()
            t0 = time.perf_counter()

            text, conf, source = extract_text(path, job_id)
            cancel.check(job_id)

            data, parser_used = parse_invoice(text, lambda: cancel.is_cancelled(job_id))
            cancel.check(job_id)

            duplicate = invoice_exists(data.get("invoice_number"),
                                       data.get("dealer_gstin"), data.get("dealer_name"))
            issues = verify_rules(data, conf, source, parser_used, duplicate,
                                  get_history_totals())
            status, score = decide(issues)

            finished = datetime.utcnow()
            duration = round(time.perf_counter() - t0, 1)
            cancel.check(job_id)

            record_id = None
            if save:
                record_id = save_invoice(os.path.basename(path), data, status, score, conf,
                                         issues, started, finished, duration)

            return {
                "id": record_id,
                "status": status,
                "risk_score": score,
                "source": source,
                "ocr_confidence": round(conf, 3),
                "parser": parser_used,
                "issues": issues,
                "extracted": data,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "duration_seconds": duration,
            }
    finally:
        cancel.cleanup(job_id)