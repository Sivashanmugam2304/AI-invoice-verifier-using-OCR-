import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_use_mkldnn"] = "0"

import numpy as np
from paddleocr import PaddleOCR

_ocr = None


def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
            text_det_unclip_ratio=2.5,
            text_det_limit_type="max",
            text_det_limit_side_len=4000,
        )
    return _ocr


def run_ocr(img: np.ndarray) -> list[dict]:
    result = _get_ocr().predict(img)
    lines = []
    for res in result:
        for text, score, poly in zip(res["rec_texts"], res["rec_scores"], res["rec_polys"]):
            if text.strip():
                lines.append({"text": text, "score": float(score),
                              "box": np.array(poly).tolist()})
    lines.sort(key=lambda l: (l["box"][0][1], l["box"][0][0]))
    return lines


def lines_to_text(lines: list[dict], y_tol: int = 15) -> str:
    rows, current, last_y = [], [], None
    for l in lines:
        y = l["box"][0][1]
        if last_y is not None and abs(y - last_y) > y_tol:
            rows.append(current)
            current = []
        current.append(l)
        last_y = y
    if current:
        rows.append(current)
    return "\n".join(
        "  ".join(p["text"] for p in sorted(r, key=lambda p: p["box"][0][0]))
        for r in rows
    )