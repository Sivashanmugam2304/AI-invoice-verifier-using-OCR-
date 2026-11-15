import cv2
import numpy as np
import pymupdf


def load_images(path: str) -> list[np.ndarray]:
    """Load a JPG/PNG/PDF and return a list of BGR images (one per page)."""
    if path.lower().endswith(".pdf"):
        images = []
        doc = pymupdf.open(path)
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = np.frombuffer(pix.samples, dtype=np.uint8)
            img = img.reshape(pix.height, pix.width, pix.n)
            code = cv2.COLOR_RGBA2BGR if pix.n == 4 else cv2.COLOR_RGB2BGR
            images.append(cv2.cvtColor(img, code))
        doc.close()
        return images

    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return [img]


def _deskew(gray: np.ndarray) -> np.ndarray:
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle > 45:
        angle -= 90
    if abs(angle) < 0.5 or abs(angle) > 15:
        return gray
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def remove_table_lines(gray: np.ndarray) -> np.ndarray:
    """Erase long horizontal/vertical table borders so OCR doesn't read them as text."""
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 15, 10)
    h, w = bw.shape
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 40, 40), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 60, 40)))
    hlines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk)
    vlines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vk)
    lines = cv2.dilate(cv2.bitwise_or(hlines, vlines),
                       np.ones((3, 3), np.uint8), iterations=1)
    cleaned = gray.copy()
    cleaned[lines > 0] = 255
    return cleaned


def preprocess(img: np.ndarray) -> np.ndarray:
    """Resize, grayscale, deskew, remove table lines. Returns BGR image."""
    h, w = img.shape[:2]
    if w < 3000:
        scale = 3000 / w
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    elif w > 4000:
        scale = 4000 / w
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = _deskew(gray)
    gray = remove_table_lines(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)