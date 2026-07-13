"""
One-time script to generate fake demo data:
- data/people.csv: user_id, name, age, contact, photo_filename
- sample_images/: a placeholder .jpg for each user_id

This data is only for demonstrating the bulk import (Approach 1). The
actual import logic (bulk_import.py) never touches Pillow or this script.
"""

import csv
import random
from pathlib import Path

from PIL import Image, ImageDraw

NUM_RECORDS = 300

BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "sample_images"
CSV_PATH = BASE_DIR / "data" / "people.csv"

FIRST_NAMES = ["Ali", "Sara", "Omar", "Ayesha", "Bilal", "Hina", "Zain", "Mariam", "Usman", "Fatima"]
LAST_NAMES = ["Khan", "Ahmed", "Malik", "Raza", "Iqbal", "Farooq", "Siddiqui", "Hashmi"]


def make_placeholder_image(user_id: int, path: Path) -> None:
    color = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
    img = Image.new("RGB", (200, 200), color=color)
    draw = ImageDraw.Draw(img)
    draw.text((70, 90), f"#{user_id}", fill=(255, 255, 255))
    img.save(path, "JPEG")


def main():
    IMAGES_DIR.mkdir(exist_ok=True)
    CSV_PATH.parent.mkdir(exist_ok=True)

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "name", "age", "contact", "photo_filename"])

        for user_id in range(1, NUM_RECORDS + 1):
            name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            age = random.randint(18, 65)
            contact = f"+92-3{random.randint(10,99)}-{random.randint(1000000,9999999)}"
            photo_filename = f"user_{user_id}.jpg"

            make_placeholder_image(user_id, IMAGES_DIR / photo_filename)
            writer.writerow([user_id, name, age, contact, photo_filename])

    print(f"Generated {NUM_RECORDS} records:")
    print(f"  CSV: {CSV_PATH}")
    print(f"  Images: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
