import os
import boto3
from botocore.exceptions import ClientError

#   $env:SCOPED_ACCESS_KEY = "..."
#   $env:SCOPED_SECRET_KEY = "..."
ACCESS_KEY = os.environ["SCOPED_ACCESS_KEY"]
SECRET_KEY = os.environ["SCOPED_SECRET_KEY"]

READ_ONLY_BUCKET = "demo-bucket2"  # bucket this key IS allowed to read
OTHER_BUCKET = "demo-bucket"       # bucket this key was never granted access to

s3 = boto3.client(
    "s3",
    endpoint_url="http://localhost:9000",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

# This should WORK - the key's policy allows GetObject/ListBucket on this bucket
print(f"Trying to READ from {READ_ONLY_BUCKET} (should succeed)...")
try:
    response = s3.list_objects_v2(Bucket=READ_ONLY_BUCKET)
    for obj in response.get("Contents", []):
        print(f"  OK - found: {obj['Key']}")
except ClientError as e:
    print(f"  FAILED: {e}")

# This should FAIL - the policy never grants PutObject
print(f"\nTrying to WRITE to {READ_ONLY_BUCKET} (should be denied)...")
try:
    s3.put_object(Bucket=READ_ONLY_BUCKET, Key="not-allowed.txt", Body=b"test")
    print("  Uh oh - this succeeded, policy isn't restricting writes")
except ClientError as e:
    print(f"  DENIED as expected: {e.response['Error']['Code']}")

# This should also FAIL - the key's policy only names demo-bucket2
print(f"\nTrying to access {OTHER_BUCKET} (should be denied, key is scoped to {READ_ONLY_BUCKET} only)...")
try:
    s3.list_objects_v2(Bucket=OTHER_BUCKET)
    print(f"  Uh oh - this succeeded, key isn't scoped to {READ_ONLY_BUCKET} only")
except ClientError as e:
    print(f"  DENIED as expected: {e.response['Error']['Code']}")
