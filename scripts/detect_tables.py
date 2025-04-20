import cv2
import os
from pathlib import Path

# === CONFIG ===
IMAGE_DIR = Path("data/images")
OUTPUT_DIR = Path("data/tables_raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def detect_tables_in_image(image_path, min_area=10000):
    print(f"🔍 Processing: {image_path.name}")
    img = cv2.imread(str(image_path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Thresholding to detect lines
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    
    # Dilation to join nearby lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 2))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    count = 0
    for i, contour in enumerate(contours):
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h

        if area > min_area:
            count += 1
            table_crop = img[y:y+h, x:x+w]
            output_path = OUTPUT_DIR / f"{image_path.stem}_table_{count}.png"
            cv2.imwrite(str(output_path), table_crop)
            print(f"🖼️ Saved: {output_path.name}")

def process_all_images():
    for image_path in sorted(IMAGE_DIR.glob("*.png")):
        detect_tables_in_image(image_path)

if __name__ == "__main__":
    process_all_images()