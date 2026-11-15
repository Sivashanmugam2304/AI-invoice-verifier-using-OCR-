import os
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import cancel
from app.db import clear_invoices, get_invoice, init_db, list_invoices
from app.pipeline import process_invoice

app = FastAPI(title="AI Invoice Verification")
UPLOAD_DIR = os.path.join("data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED = (".jpg", ".jpeg", ".png", ".pdf")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(os.path.join("static", "dashboard.html"))


@app.post("/verify")
def verify(file: UploadFile = File(...), job_id: str | None = None):
    if not file.filename.lower().endswith(ALLOWED):
        raise HTTPException(400, "Upload a JPG, PNG or PDF file")
    path = os.path.join(UPLOAD_DIR, os.path.basename(file.filename))
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        return process_invoice(path, job_id=job_id)
    except cancel.Cancelled:
        try:
            os.remove(path)
        except OSError:
            pass
        raise HTTPException(409, "Cancelled")


@app.post("/cancel/{job_id}")
def cancel_job(job_id: str):
    cancel.request_cancel(job_id)
    return {"cancelling": True}


@app.get("/invoices")
def invoices():
    return list_invoices()


@app.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: int):
    row = get_invoice(invoice_id)
    if row is None:
        raise HTTPException(404, "Invoice not found")
    return row


@app.delete("/invoices")
def delete_all():
    clear_invoices()
    return {"deleted": True}