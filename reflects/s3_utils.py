import boto3
import os
from fastapi import UploadFile
from uuid import uuid4

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET = os.getenv("AWS_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

def upload_to_s3(file: UploadFile, prefix=""):
    ext = os.path.splitext(file.filename)[1]
    filename = f"{prefix}_{uuid4().hex}{ext}"
    s3.upload_fileobj(
        file.file,
        AWS_BUCKET,
        filename,
        ExtraArgs={"ACL": "public-read", "ContentType": file.content_type}
    )
    return f"https://{AWS_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
