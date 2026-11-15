import json
import os
from datetime import datetime

from sqlalchemy import (DateTime, Float, String, Text, create_engine, delete,
                        inspect, select, text)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Default: SQLite file (no install needed).
# For PostgreSQL set:  DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/invoices
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///invoices.db")
engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dealer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dealer_gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grand_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[int] = mapped_column(default=0)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # finish time
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
    # Add the new columns to an existing database, so nothing has to be deleted
    existing = {c["name"] for c in inspect(engine).get_columns("invoices")}
    with engine.begin() as conn:
        if "started_at" not in existing:
            conn.execute(text("ALTER TABLE invoices ADD COLUMN started_at TIMESTAMP"))
        if "duration_seconds" not in existing:
            conn.execute(text("ALTER TABLE invoices ADD COLUMN duration_seconds FLOAT"))


def invoice_exists(invoice_number: str | None, dealer_gstin: str | None,
                   dealer_name: str | None) -> bool:
    if not invoice_number:
        return False
    with Session(engine) as s:
        q = select(Invoice.id).where(Invoice.invoice_number == invoice_number)
        if dealer_gstin:
            q = q.where(Invoice.dealer_gstin == dealer_gstin)
        elif dealer_name:
            q = q.where(Invoice.dealer_name == dealer_name)
        return s.execute(q.limit(1)).first() is not None


def get_history_totals() -> list[float]:
    with Session(engine) as s:
        rows = s.execute(select(Invoice.grand_total)
                         .where(Invoice.grand_total.is_not(None))).all()
        return [r[0] for r in rows]


def save_invoice(filename: str, data: dict, status: str, score: int,
                 ocr_conf: float, issues: list[dict],
                 started_at: datetime | None = None,
                 finished_at: datetime | None = None,
                 duration: float | None = None) -> int:
    with Session(engine) as s:
        row = Invoice(
            filename=filename,
            invoice_number=data.get("invoice_number"),
            invoice_date=data.get("invoice_date"),
            dealer_name=data.get("dealer_name"),
            dealer_gstin=data.get("dealer_gstin"),
            grand_total=data.get("grand_total"),
            status=status,
            risk_score=score,
            ocr_confidence=ocr_conf,
            issues_json=json.dumps(issues),
            extracted_json=json.dumps(data),
            created_at=finished_at or datetime.utcnow(),
            started_at=started_at,
            duration_seconds=duration,
        )
        s.add(row)
        s.commit()
        return row.id


def list_invoices(limit: int = 50) -> list[dict]:
    with Session(engine) as s:
        rows = s.execute(select(Invoice).order_by(Invoice.id.desc()).limit(limit)).scalars()
        return [{
            "id": r.id, "filename": r.filename, "invoice_number": r.invoice_number,
            "dealer_name": r.dealer_name, "grand_total": r.grand_total,
            "status": r.status, "risk_score": r.risk_score,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.created_at.isoformat(),
            "duration_seconds": r.duration_seconds,
        } for r in rows]


def get_invoice(invoice_id: int) -> dict | None:
    with Session(engine) as s:
        r = s.get(Invoice, invoice_id)
        if r is None:
            return None
        return {
            "id": r.id, "filename": r.filename, "status": r.status,
            "risk_score": r.risk_score, "ocr_confidence": r.ocr_confidence,
            "issues": json.loads(r.issues_json),
            "extracted": json.loads(r.extracted_json),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.created_at.isoformat(),
            "duration_seconds": r.duration_seconds,
        }


def clear_invoices() -> None:
    with Session(engine) as s:
        s.execute(delete(Invoice))
        s.commit()