"""
Approach 1: upload-first, deterministic naming, batch processing.

For each row in the CSV:
  1. Upload the profile picture to MinIO, named after the user's ID.
  2. Only after that succeeds, queue the row for a DB insert.

Rows are processed in parallel batches (not one at a time) for speed.
Successful rows are bulk-inserted into Postgres per batch. Any row whose
image upload fails is logged to failed_rows.csv instead of stopping the
whole run - it can be retried later by re-running the import against just
that file.
"""

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import psycopg2

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "data" / "people.csv"
IMAGES_DIR = BASE_DIR / "sample_images"
FAILED_ROWS_PATH = BASE_DIR / "failed_rows.csv"

BUCKET = "profile-pictures"
BATCH_SIZE = 50
UPLOAD_WORKERS = 10

MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"

PG_CONFIG = dict(
    host="localhost",
    port=5434,  # mapped from the container's 5432; see db/docker-compose.yml
    dbname="bulk_import_demo",
    user="postgres",
    password="demopassword",
)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def ensure_bucket(s3):
    existing = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    if BUCKET not in existing:
        s3.create_bucket(Bucket=BUCKET)
        print(f"Created bucket: {BUCKET}")


def upload_one(s3, row):
    """Uploads a single row's image. Returns (row, image_url) on success,
    or (row, None) on failure - never raises, so one bad row can't crash
    the batch."""
    user_id = row["user_id"]
    photo_filename = row["photo_filename"]
    local_path = IMAGES_DIR / photo_filename
    s3_key = f"user_{user_id}.jpg"

    try:
        s3.upload_file(str(local_path), BUCKET, s3_key)
        image_url = f"{MINIO_ENDPOINT}/{BUCKET}/{s3_key}"
        print(f"  uploaded  user_id={user_id:<6} name={row['name']:<20} -> {s3_key}")
        return row, image_url
    except Exception as e:
        print(f"  FAILED   user_id={user_id:<6} name={row['name']:<20} -> {e}")
        return row, None


def insert_batch(conn, successful_rows):
    if not successful_rows:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO users (user_id, name, age, contact, image_url)
            VALUES (%(user_id)s, %(name)s, %(age)s, %(contact)s, %(image_url)s)
            ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                contact = EXCLUDED.contact,
                image_url = EXCLUDED.image_url
            """,
            successful_rows,
        )
    conn.commit()


def process_batch(s3, conn, batch, failed_writer):
    successful_rows = []

    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as executor:
        futures = [executor.submit(upload_one, s3, row) for row in batch]
        for future in as_completed(futures):
            row, image_url = future.result()
            if image_url:
                successful_rows.append(
                    {
                        "user_id": row["user_id"],
                        "name": row["name"],
                        "age": row["age"],
                        "contact": row["contact"],
                        "image_url": image_url,
                    }
                )
            else:
                failed_writer.writerow(row)

    insert_batch(conn, successful_rows)
    if successful_rows:
        ids = ", ".join(r["user_id"] for r in successful_rows)
        print(f"  inserted into DB: user_id in [{ids}]")

    return len(successful_rows), len(batch) - len(successful_rows)


def main():
    s3 = get_s3_client()
    ensure_bucket(s3)
    conn = psycopg2.connect(**PG_CONFIG)

    total_success = 0
    total_failed = 0

    with open(CSV_PATH, newline="") as csv_file, open(
        FAILED_ROWS_PATH, "w", newline=""
    ) as failed_file:
        reader = csv.DictReader(csv_file)
        failed_writer = csv.DictWriter(failed_file, fieldnames=reader.fieldnames)
        failed_writer.writeheader()

        batch = []
        for row in reader:
            batch.append(row)
            if len(batch) == BATCH_SIZE:
                success, failed = process_batch(s3, conn, batch, failed_writer)
                total_success += success
                total_failed += failed
                print(f"Batch done: {success} succeeded, {failed} failed")
                batch = []

        if batch:
            success, failed = process_batch(s3, conn, batch, failed_writer)
            total_success += success
            total_failed += failed
            print(f"Final batch done: {success} succeeded, {failed} failed")

    conn.close()

    print()
    print(f"Import complete: {total_success} succeeded, {total_failed} failed")
    if total_failed:
        print(f"Failed rows logged to: {FAILED_ROWS_PATH}")
    else:
        FAILED_ROWS_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
