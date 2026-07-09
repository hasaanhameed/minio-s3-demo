import boto3

# MinIO is running locally and speaks the same S3 API as AWS.
# These are the default credentials MinIO printed when it started.
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)

BUCKET = "demo-bucket"
FILE_NAME = "hello.txt"

# 1. STORE: create a bucket (skip if it already exists from the console demo)
existing_buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
if BUCKET not in existing_buckets:
    s3.create_bucket(Bucket=BUCKET)
    print(f"Created bucket: {BUCKET}")
else:
    print(f"Bucket already exists: {BUCKET}")

# 2. STORE: upload a file into the bucket
with open(FILE_NAME, "w") as f:
    f.write("Hello from MinIO! This proves upload/download works.\n")

s3.upload_file(FILE_NAME, BUCKET, FILE_NAME)
print(f"Uploaded {FILE_NAME} to bucket {BUCKET}")

# 3. ACCESS: list what's in the bucket
response = s3.list_objects_v2(Bucket=BUCKET)
print("Objects in bucket:")
for obj in response.get("Contents", []):
    print(f"  - {obj['Key']} ({obj['Size']} bytes)")

# 4. RETRIEVE: download the file back out
downloaded_name = "downloaded_hello.txt"
s3.download_file(BUCKET, FILE_NAME, downloaded_name)
print(f"Downloaded back as {downloaded_name}")

with open(downloaded_name) as f:
    print("Contents:", f.read())
