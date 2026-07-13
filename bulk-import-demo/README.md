# Bulk Import Demo (Approach 1: Upload-First, Deterministic Naming)

Demonstrates one of the approaches discussed for reliably bulk-importing
large volumes of user data into a system where structured metadata lives in
a relational database, and each user's profile picture lives in an
S3-compatible bucket (MinIO), linked via a URL stored in the database.

## Problem

We need to bulk-import a large number of user records (potentially hundreds
of thousands). Each record has structured metadata (name, age, contact)
that belongs in a relational database, plus a profile picture that belongs
in an S3-compatible bucket — with the database storing a URL pointing to
that image.

Processing this manually, one record at a time, isn't practical at scale.
The core challenge: the database write and the S3 upload are two separate
operations, not one transaction. If one succeeds and the other fails, the
two systems can fall out of sync.

## Approach implemented here: upload-first, deterministic naming

For each record:

1. Upload the profile picture to MinIO first, named predictably (e.g.
   `user_12345.jpg`) so retries are safe (they simply overwrite, no
   duplicates or orphaned files from retries).
2. Only after the upload succeeds, insert the record into Postgres with
   the resulting image URL — this guarantees no database row ever points
   to a missing image.

Records are processed in parallel batches (not one at a time) to avoid an
impractically slow sequential run, and any row that fails is logged
separately instead of stopping the whole import, so it can be retried later
without re-running everything.

## How the code works (`bulk_import.py`)

In plain terms, here's the full flow from start to finish:

1. **Set things up.** Connect to MinIO, make sure the `profile-pictures`
   bucket exists (create it if not), and connect to Postgres.

2. **Read the CSV in chunks of 50, not all at once.** Instead of loading
   every one of the (potentially hundreds of thousands of) rows into memory
   and processing them one by one, the script collects 50 rows, processes
   that batch fully, then moves to the next 50. This keeps memory usage low
   and lets progress happen in manageable, tracked chunks.

3. **Within each batch of 50, upload all the photos at the same time**
   (up to 10 at once), instead of one after another. Uploading is mostly
   just "waiting on the network," so doing several at once is much faster
   than waiting for each one individually.

4. **For each photo, try the upload and never let one bad photo break
   everything.** If a specific upload fails (missing file, network issue,
   etc.), that one row is set aside and logged - the rest of the batch
   keeps going normally.

5. **Only after all 50 uploads in the batch are done, write the successful
   ones to the database - all at once, in a single batch insert**, not 50
   separate ones. This is both faster and enforces the core rule: a
   database record is only ever created once we know its photo actually
   made it into the bucket.

6. **Repeat for every batch, printing progress as it goes**, so you can see
   uploads and inserts happening live in the terminal.

7. **At the end, report totals.** If everything succeeded, there's nothing
   left over. If some rows failed, they're saved in `failed_rows.csv` so
   they can be retried later - without needing to reprocess everything that
   already worked.

## Components

- `generate_sample_data.py` — one-time script that creates fake demo data:
  a CSV of people (`data/people.csv`) and a matching placeholder image per
  person (`sample_images/`). Uses Pillow; not part of the actual import
  logic.
- `db/docker-compose.yml` + `db/schema.sql` — spins up Postgres (with the
  `users` table auto-created on first start) and pgAdmin for visualizing
  the data.
- `bulk_import.py` — the actual Approach 1 implementation: reads the CSV in
  batches, uploads images to MinIO in parallel, and bulk-inserts successful
  rows into Postgres, logging failures separately.

## Setup

1. Start MinIO (same server as the main repo's demo):

   ```powershell
   cd C:\minio
   .\minio.exe server C:\minio\data --console-address ":9001"
   ```

2. Start Postgres + pgAdmin:

   ```bash
   cd bulk-import-demo/db
   docker compose up -d
   ```

   This automatically creates the `users` table from `schema.sql` on first
   run — no manual step needed.

3. Generate the fake dataset:

   ```bash
   python bulk-import-demo/generate_sample_data.py
   ```

   Produces 300 fake records:
   ![Generated CSV sample](screenshots/01-generated-csv-sample.png)

4. Confirm the database is reachable and the table exists. Two ways to
   view it:
   - **pgAdmin web** (bundled in the compose stack): `http://localhost:5050`,
     login `admin@example.com` / `demopassword`, register a server with
     host `postgres`, port `5432` (internal Docker network port).
   - **pgAdmin Desktop** (or any external client): host `localhost`, port
     `5434` (the host-mapped port from `docker-compose.yml`), db
     `bulk_import_demo`, user `postgres`, password `demopassword`.

   Either way, at this point the `users` table exists but is empty:
   ![Initial DB state, users table empty](screenshots/02-initial-db-state-pgadmin.png)

   The MinIO bucket doesn't exist yet either - it gets created
   automatically by `bulk_import.py` on first run:
   ![MinIO, no buckets yet](screenshots/03-minio-before-empty.png)

## Running the import

```bash
python bulk-import-demo/bulk_import.py
```

The script logs each upload and each batch's DB insert as it happens:
![Terminal output during the import](screenshots/05-terminal-output.png)

## Result

All 300 profile pictures land in the `profile-pictures` bucket:
![MinIO, 300 objects uploaded](screenshots/04-minio-after-300-objects.png)

And all 300 records are in Postgres, each with an `image_url` pointing at
its corresponding MinIO object:
![Postgres, 300 rows with image_url set](screenshots/06-pgadmin-final-300-rows.png)

If any row's upload fails, it's written to `failed_rows.csv` instead of
stopping the run, and can be retried later by re-running the import against
just that file. Re-running against already-imported rows is also safe -
the `INSERT ... ON CONFLICT DO UPDATE` in `bulk_import.py` means reruns
update existing rows instead of creating duplicates.
