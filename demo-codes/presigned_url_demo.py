import boto3

# demo-bucket is still fully private - no anonymous access rule was added to
# it. A presigned URL grants temporary access to one object in it, without
# making the whole bucket public and without sharing root credentials.
s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin",
)

BUCKET = "demo-bucket"
FILE_NAME = "data.txt"
EXPIRES_IN_SECONDS = 60

url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": BUCKET, "Key": FILE_NAME},
    ExpiresIn=EXPIRES_IN_SECONDS,
)

print(f"Presigned URL (valid for {EXPIRES_IN_SECONDS} seconds):")
print(url)
print()
print("Open this URL in a browser now - it should download/show the file.")
print(f"Wait {EXPIRES_IN_SECONDS} seconds and reload it - it should fail with AccessDenied/expired.")
