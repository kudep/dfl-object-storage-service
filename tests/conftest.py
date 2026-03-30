import os

import boto3
import pytest


ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
BUCKET = os.getenv("MINIO_BUCKET", "videos")

ADMIN_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
ADMIN_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

RECORDER_ACCESS_KEY = os.getenv("RECORDER_ACCESS_KEY", "recorder")
RECORDER_SECRET_KEY = os.getenv("RECORDER_SECRET_KEY", "recorder-secret")

TEACHER_ACCESS_KEY = os.getenv("TEACHER_ACCESS_KEY", "teacher")
TEACHER_SECRET_KEY = os.getenv("TEACHER_SECRET_KEY", "teacher-secret")


def _make_client(access_key: str, secret_key: str, session_token: str = None) -> boto3.client:
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name="us-east-1",
    )


def _make_sts_client(access_key: str, secret_key: str):
    return boto3.client(
        "sts",
        endpoint_url=ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
    )


def assume_role_with_policy(access_key: str, secret_key: str, policy: str, duration: int = 900):
    """Call STS AssumeRole and return temporary S3 client."""
    sts = _make_sts_client(access_key, secret_key)
    response = sts.assume_role(
        RoleArn="arn:aws:iam::0:role/unused",  # MinIO ignores this but requires it
        RoleSessionName="test-session",
        Policy=policy,
        DurationSeconds=duration,
    )
    creds = response["Credentials"]
    return _make_client(creds["AccessKeyId"], creds["SecretAccessKey"], creds["SessionToken"])


@pytest.fixture()
def admin_client():
    return _make_client(ADMIN_ACCESS_KEY, ADMIN_SECRET_KEY)


@pytest.fixture()
def recorder_client():
    return _make_client(RECORDER_ACCESS_KEY, RECORDER_SECRET_KEY)


@pytest.fixture()
def teacher_client():
    return _make_client(TEACHER_ACCESS_KEY, TEACHER_SECRET_KEY)


@pytest.fixture()
def bucket():
    return BUCKET


@pytest.fixture(autouse=True)
def _cleanup(admin_client, bucket):
    """Remove test objects after each test."""
    yield
    # response = admin_client.list_objects_v2(Bucket=bucket, Prefix="test/")
    # for obj in response.get("Contents", []):
    #     admin_client.delete_object(Bucket=bucket, Key=obj["Key"])
