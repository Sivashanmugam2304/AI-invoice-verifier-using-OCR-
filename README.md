# AI Invoice Verification for Dealers

A system that reads a dealer's invoice (JPG, PNG or PDF), extracts the data with a local AI model, checks it with rules and an anomaly model, stores the result, and gives a verdict: **Verified**, **Review** or **Flagged**.

Everything runs locally. No invoice data is sent to an external service.

## How it works

```
Dealer uploads invoice (JPG / PNG / PDF)
        |
        v
Read the invoice
  - PDF with a text layer: read the text directly (exact, no OCR errors)
  - Scan or photo: OpenCV preprocessing + PaddleOCR
        |
        v
Local Qwen (via Ollama) + Python parser
  - turns raw text into structured fields (JSON)
        |
        v
Python verification + ML model
  - rule checks, risk scoring, anomaly detection
        |
        v
Database (SQLite by default, PostgreSQL optional)
  - stores invoice history and results
        |
        v
Verified / Review / Flagged
```

## Features

- Accepts JPG, PNG and PDF invoices
- Uses the PDF text layer when it exists, and falls back to OCR for scans
- Image cleanup before OCR: resize, deskew, table-line removal
- Field extraction with a local Qwen model (no cloud API)
- Regex fallback if Ollama is not running
- 14 verification checks (listed below) with a risk score from 0 to 100
- Duplicate invoice detection
- Isolation Forest anomaly detection on invoice amounts
- Web dashboard with upload, result popup, counters and invoice history
- REST API (FastAPI) with automatic docs

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Image processing | OpenCV |
| PDF handling | PyMuPDF |
| OCR | PaddleOCR |
| Invoice understanding | Qwen 2.5 (3b or 7b) through Ollama |
| Verification | Python rules + scikit-learn (Isolation Forest) |
| Database | SQLite (default), PostgreSQL (optional) via SQLAlchemy |
| API | FastAPI + Uvicorn |
| Frontend | Single-page HTML/CSS/JavaScript dashboard |

## Project structure

```
invoice_verifier/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app and routes
│   ├── pipeline.py      # runs the full flow for one invoice
│   ├── preprocess.py    # OpenCV: load, resize, deskew, remove table lines
│   ├── ocr.py           # PaddleOCR
│   ├── pdf_text.py      # reads the PDF text layer
│   ├── parser.py        # Qwen extraction + regex fallback
│   ├── verify.py        # rule checks and anomaly model
│   ├── decision.py      # Verified / Review / Flagged
│   └── db.py            # database models and queries
├── static/
│   └── dashboard.html   # the dashboard
├── data/
│   ├── samples/         # test invoices
│   └── uploads/         # uploaded files
├── make_samples.py      # creates 3 demo invoices
├── run_demo.py          # runs one invoice from the terminal
├── requirements.txt
└── README.md
```

## Setup (Windows)

### 1. Requirements

- Python 3.12 (3.9 to 3.12 work with PaddleOCR)
- [Ollama](https://ollama.com) installed
- About 8 GB of free RAM (16 GB recommended for the 7b model)

### 2. Install the project

```powershell
cd invoice_verifier
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run this first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 3. Download the Qwen model

```powershell
ollama pull qwen2.5:3b
```

The default model in `app/parser.py` is set through the `OLLAMA_MODEL` variable. To use another model:

```powershell
$env:OLLAMA_MODEL="qwen2.5:7b"
```

### 4. Create the demo invoices (optional)

```powershell
python make_samples.py
```

This creates three PDFs in `data/samples/`:

| File | Purpose | Expected result |
|---|---|---|
| `sample_good.pdf` | Correct invoice | Verified |
| `sample_bad_math.pdf` | Grand total does not match taxable + tax | Review |
| `sample_future.pdf` | Invoice date in the future | Flagged |

## Run

### Dashboard (recommended)

Make sure Ollama is running (the llama icon near the clock, or `ollama serve`), then:

```powershell
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/** in your browser.

1. Click the upload box and choose an invoice.
2. Wait for the result popup (text-layer PDFs take seconds; scans can take 1 to 3 minutes).
3. Click any row in the history table to reopen its result.
4. Use **Clear history** to reset the database.

The first request after starting Ollama is slow because the model has to load into memory.

### Terminal

```powershell
python run_demo.py data\samples\sample_good.pdf
```

Prints the status, risk score, issues found and the extracted data.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard |
| POST | `/verify` | Upload an invoice (form field `file`) and get the result |
| GET | `/invoices` | List saved invoices |
| GET | `/invoices/{id}` | Full result of one saved invoice |
| DELETE | `/invoices` | Clear all saved invoices |
| GET | `/docs` | Interactive API documentation |

## Verification checks

Each issue adds points to a risk score (capped at 100).

| Check | Points |
|---|---|
| Missing invoice number | 25 |
| Missing invoice date | 15 |
| Missing dealer name | 15 |
| Missing grand total | 25 |
| Dealer GSTIN missing | 15 |
| Dealer GSTIN has an invalid format | 25 |
| Buyer GSTIN has an invalid format | 10 |
| Invoice date unreadable | 15 |
| Invoice date more than a year old | 10 |
| Quantity x rate does not match line amount | 10 per line (max 30) |
| Item amounts do not add up to the taxable total | 25 |
| Taxable + tax does not equal the grand total | 35 |
| OCR confidence below 0.80 | 15 |
| Qwen not used (regex fallback) | 10 |
| Amount is unusual compared with past invoices (ML) | 20 |
| **Invoice date in the future (critical)** | **40** |
| **Duplicate invoice (critical)** | **60** |

### Decision

| Result | Rule |
|---|---|
| **Verified** | Risk score below 15 |
| **Review** | Risk score 15 to 49 |
| **Flagged** | Risk score 50 or more, or any critical issue |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5:3b` | Which Qwen model to use |
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Where Ollama is running |
| `DATABASE_URL` | `sqlite:///invoices.db` | Database connection |
| `MAX_PAGES` | `5` | Maximum pages OCR'd per document |

### Using PostgreSQL

The default database is a local SQLite file so the project runs without setup. To use PostgreSQL, create a database and set:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/invoices"
```

The tables are created automatically on startup. No code changes are needed.

## Known limitations

- **Scan quality matters.** Low-resolution or dense scanned tables can cause OCR digit errors. The math checks catch most of these and send the invoice to Review or Flagged instead of passing it as valid.
- **Page position matters.** If a file contains only a middle page of a long invoice (no header), fields such as date and dealer are missing and the invoice is flagged.
- **The anomaly model needs history.** The Isolation Forest check only activates once 10 or more invoices are stored.
- **Small Qwen models can make mistakes.** The 3b model is fast but less accurate than 7b. All extracted numbers are re-checked by the rules.
- **GSTIN checks are format-only.** The system validates the GSTIN pattern, not whether it exists in the government registry.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Activate the environment: `.venv\Scripts\Activate.ps1` |
| `Parser: regex_fallback` | Ollama is not running or the model is not downloaded. Run `ollama list` and `ollama pull qwen2.5:3b` |
| First upload is very slow | Normal: Qwen is loading into memory. Later uploads are faster |
| OCR crash mentioning oneDNN / MKLDNN | Already handled with `enable_mkldnn=False` in `app/ocr.py` |
| Dashboard shows 404 | Check that `static/dashboard.html` exists |
| Same sample shows as duplicate | Click **Clear history** on the dashboard |

## Possible next steps

- Train a supervised model on labelled real invoices
- Validate GSTINs against the official portal
- Add user login and per-dealer history
- Table-structure recognition for dense scanned invoices
- Export of results to Excel or PDF
