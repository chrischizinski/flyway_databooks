import pytesseract
from PIL import Image
import os

def ocr_toc_pages(start_page, end_page, image_dir="data/images"):
    pages_text = []
    for page_num in range(start_page, end_page + 1):
        filename = f"page_{str(page_num).zfill(3)}.png"
        filepath = os.path.join(image_dir, filename)
        if not os.path.exists(filepath):
            print(f"⚠️ Missing: {filename}")
            continue
        image = Image.open(filepath)
        text = pytesseract.image_to_string(image)
        pages_text.append(text)
        print(f"📄 OCR on TOC page: {filename}")
    return "\n".join(pages_text)