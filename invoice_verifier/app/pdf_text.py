import pymupdf


def extract_text_layer(path: str, min_chars: int = 50) -> list[str] | None:
    """Return text per page if the PDF has a real text layer, else None."""
    if not path.lower().endswith(".pdf"):
        return None
    doc = pymupdf.open(path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    if sum(len(p.strip()) for p in pages) < min_chars:
        return None          # scanned PDF, so OCR is needed
    return pages