import sys
from app.pdf_text import extract_text_layer

pages = extract_text_layer(sys.argv[1])
if pages is None:
    print("No text layer found: this PDF is a scan or photo, so OCR is needed.")
else:
    print(f"Text layer found, {len(pages)} page(s).")
    print(pages[0][:3000])