import sys
import cv2
from app.preprocess import load_images, preprocess
from app.ocr import run_ocr, lines_to_text

path = sys.argv[1]
max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1

images = load_images(path)
print(f"PDF/image has {len(images)} page(s); testing first {max_pages}")

for i, img in enumerate(images[:max_pages], start=1):
    print(f"\nImage size: {img.shape[1]} x {img.shape[0]} px")
    proc = preprocess(img)
    cv2.imwrite(f"data/uploads/debug_page_{i}.png", proc)
    lines = run_ocr(proc)
    avg = sum(l["score"] for l in lines) / max(len(lines), 1)
    print(f"\n===== page {i} | {len(lines)} pieces | avg confidence {avg:.2f} =====")
    print(lines_to_text(lines))