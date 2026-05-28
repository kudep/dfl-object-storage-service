"""Integration tests for MinIO setup: bucket, roles, and permissions."""

import json

import pytest
from botocore.exceptions import ClientError

from conftest import (
    assume_role_with_policy,
    ADMIN_ACCESS_KEY,
    ADMIN_SECRET_KEY,
    RECORDER_ACCESS_KEY,
    RECORDER_SECRET_KEY,
    TEACHER_ACCESS_KEY,
    TEACHER_SECRET_KEY,
)

TEST_KEY = "test/session-1/cam-01/segment_000001.ts"
TEST_BODY = b"fake-video-segment-data-for-testing"


# ─── Bucket ──────────────────────────────────────────────────────────

class TestBucketExists:
    def test_bucket_is_accessible(self, admin_client, bucket):
        response = admin_client.head_bucket(Bucket=bucket)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200


# ─── Recorder ────────────────────────────────────────────────────────

class TestRecorder:
    def test_put_object(self, recorder_client, bucket):
        recorder_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        head = recorder_client.head_object(Bucket=bucket, Key=TEST_KEY)
        assert head["ContentLength"] == len(TEST_BODY)

    def test_multipart_upload(self, recorder_client, bucket):
        key = "test/session-1/cam-01/multipart.ts"
        # 5 MB minimum part size (except last part)
        part_data = b"x" * (5 * 1024 * 1024)

        mpu = recorder_client.create_multipart_upload(Bucket=bucket, Key=key)
        upload_id = mpu["UploadId"]

        try:
            part1 = recorder_client.upload_part(
                Bucket=bucket, Key=key, UploadId=upload_id, PartNumber=1, Body=part_data,
            )
            part2 = recorder_client.upload_part(
                Bucket=bucket, Key=key, UploadId=upload_id, PartNumber=2, Body=b"final-part",
            )
            recorder_client.complete_multipart_upload(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={
                    "Parts": [
                        {"PartNumber": 1, "ETag": part1["ETag"]},
                        {"PartNumber": 2, "ETag": part2["ETag"]},
                    ]
                },
            )
            head = recorder_client.head_object(Bucket=bucket, Key=key)
            assert head["ContentLength"] == len(part_data) + len(b"final-part")
        except Exception:
            recorder_client.abort_multipart_upload(
                Bucket=bucket, Key=key, UploadId=upload_id,
            )
            raise

    def test_list_objects(self, recorder_client, bucket):
        recorder_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        response = recorder_client.list_objects_v2(Bucket=bucket, Prefix="test/session-1/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert TEST_KEY in keys

    def test_cannot_delete(self, recorder_client, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        with pytest.raises(ClientError) as exc_info:
            recorder_client.delete_object(Bucket=bucket, Key=TEST_KEY)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_head_object_existence_check(self, recorder_client, admin_client, bucket):
        # Recorder can HEAD to check existence before uploading a segment.
        with pytest.raises(ClientError) as exc_info:
            recorder_client.head_object(Bucket=bucket, Key="test/__missing__/never.ts")
        assert exc_info.value.response["Error"]["Code"] == "404"

        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        head = recorder_client.head_object(Bucket=bucket, Key=TEST_KEY)
        assert head["ContentLength"] == len(TEST_BODY)


# ─── Teacher ─────────────────────────────────────────────────────────

class TestTeacher:
    def test_read_object(self, teacher_client, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        response = teacher_client.get_object(Bucket=bucket, Key=TEST_KEY)
        data = response["Body"].read()
        assert data == TEST_BODY

    def test_list_objects(self, teacher_client, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        response = teacher_client.list_objects_v2(Bucket=bucket, Prefix="test/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert TEST_KEY in keys

    def test_cannot_upload(self, teacher_client, bucket):
        with pytest.raises(ClientError) as exc_info:
            teacher_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_cannot_delete(self, teacher_client, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        with pytest.raises(ClientError) as exc_info:
            teacher_client.delete_object(Bucket=bucket, Key=TEST_KEY)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


# ─── Admin ───────────────────────────────────────────────────────────

class TestAdmin:
    def test_upload(self, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        head = admin_client.head_object(Bucket=bucket, Key=TEST_KEY)
        assert head["ContentLength"] == len(TEST_BODY)

    def test_read(self, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        response = admin_client.get_object(Bucket=bucket, Key=TEST_KEY)
        assert response["Body"].read() == TEST_BODY

    def test_delete(self, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        admin_client.delete_object(Bucket=bucket, Key=TEST_KEY)
        with pytest.raises(ClientError) as exc_info:
            admin_client.head_object(Bucket=bucket, Key=TEST_KEY)
        assert exc_info.value.response["Error"]["Code"] == "404"

    def test_list(self, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        response = admin_client.list_objects_v2(Bucket=bucket, Prefix="test/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert TEST_KEY in keys


# ─── STS: Temporary Credentials ─────────────────────────────────────

def _scoped_write_policy(bucket: str, prefix: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:PutObject", "s3:AbortMultipartUpload"],
                "Resource": [f"arn:aws:s3:::{bucket}/{prefix}/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{bucket}"],
                "Condition": {"StringLike": {"s3:prefix": [f"{prefix}/*"]}},
            },
        ],
    })


def _scoped_read_policy(bucket: str, prefix: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/{prefix}/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{bucket}"],
                "Condition": {"StringLike": {"s3:prefix": [f"{prefix}/*"]}},
            },
        ],
    })


class TestSTSRecorderScoped:
    """Recorder получает временные credentials, ограниченные одной сессией."""

    def test_can_write_to_allowed_prefix(self, bucket):
        policy = _scoped_write_policy(bucket, "test/session-allowed")
        client = assume_role_with_policy(RECORDER_ACCESS_KEY, RECORDER_SECRET_KEY, policy)

        key = "test/session-allowed/cam-01/segment_000001.ts"
        client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        response = client.list_objects_v2(Bucket=bucket, Prefix="test/session-allowed/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert key in keys

    def test_cannot_write_to_other_prefix(self, bucket):
        policy = _scoped_write_policy(bucket, "test/session-allowed")
        client = assume_role_with_policy(RECORDER_ACCESS_KEY, RECORDER_SECRET_KEY, policy)

        with pytest.raises(ClientError) as exc_info:
            client.put_object(
                Bucket=bucket, Key="test/session-other/cam-01/seg.ts", Body=TEST_BODY,
            )
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_cannot_read(self, admin_client, bucket):
        key = "test/session-allowed/cam-01/segment_000001.ts"
        admin_client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        policy = _scoped_write_policy(bucket, "test/session-allowed")
        client = assume_role_with_policy(RECORDER_ACCESS_KEY, RECORDER_SECRET_KEY, policy)

        with pytest.raises(ClientError) as exc_info:
            client.get_object(Bucket=bucket, Key=key)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_cannot_delete(self, admin_client, bucket):
        key = "test/session-allowed/cam-01/segment_000001.ts"
        admin_client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        policy = _scoped_write_policy(bucket, "test/session-allowed")
        client = assume_role_with_policy(RECORDER_ACCESS_KEY, RECORDER_SECRET_KEY, policy)

        with pytest.raises(ClientError) as exc_info:
            client.delete_object(Bucket=bucket, Key=key)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


class TestSTSTeacherScoped:
    """Teacher получает временные credentials, ограниченные одной сессией."""

    def test_can_read_allowed_prefix(self, admin_client, bucket):
        key = "test/session-visible/cam-01/segment_000001.ts"
        admin_client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        policy = _scoped_read_policy(bucket, "test/session-visible")
        client = assume_role_with_policy(TEACHER_ACCESS_KEY, TEACHER_SECRET_KEY, policy)

        response = client.get_object(Bucket=bucket, Key=key)
        assert response["Body"].read() == TEST_BODY

    def test_can_list_allowed_prefix(self, admin_client, bucket):
        key = "test/session-visible/cam-01/segment_000001.ts"
        admin_client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        policy = _scoped_read_policy(bucket, "test/session-visible")
        client = assume_role_with_policy(TEACHER_ACCESS_KEY, TEACHER_SECRET_KEY, policy)

        response = client.list_objects_v2(Bucket=bucket, Prefix="test/session-visible/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert key in keys

    def test_cannot_read_other_prefix(self, admin_client, bucket):
        key = "test/session-hidden/cam-01/segment_000001.ts"
        admin_client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        policy = _scoped_read_policy(bucket, "test/session-visible")
        client = assume_role_with_policy(TEACHER_ACCESS_KEY, TEACHER_SECRET_KEY, policy)

        with pytest.raises(ClientError) as exc_info:
            client.get_object(Bucket=bucket, Key=key)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"

    def test_cannot_write(self, bucket):
        policy = _scoped_read_policy(bucket, "test/session-visible")
        client = assume_role_with_policy(TEACHER_ACCESS_KEY, TEACHER_SECRET_KEY, policy)

        with pytest.raises(ClientError) as exc_info:
            client.put_object(
                Bucket=bucket, Key="test/session-visible/cam-01/seg.ts", Body=TEST_BODY,
            )
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


class TestSTSAdminScoped:
    """Admin получает временные credentials с полным доступом к prefix."""

    def test_full_access_to_scoped_prefix(self, bucket):
        policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["s3:*"],
                "Resource": [
                    f"arn:aws:s3:::{bucket}/test/admin-session/*",
                ],
            }, {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{bucket}"],
                "Condition": {"StringLike": {"s3:prefix": ["test/admin-session/*"]}},
            }],
        })
        client = assume_role_with_policy(ADMIN_ACCESS_KEY, ADMIN_SECRET_KEY, policy)

        key = "test/admin-session/cam-01/seg.ts"

        # write
        client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        # read
        response = client.get_object(Bucket=bucket, Key=key)
        assert response["Body"].read() == TEST_BODY

        # list
        response = client.list_objects_v2(Bucket=bucket, Prefix="test/admin-session/")
        keys = [obj["Key"] for obj in response.get("Contents", [])]
        assert key in keys

        # delete
        client.delete_object(Bucket=bucket, Key=key)

    def test_cannot_access_other_prefix(self, admin_client, bucket):
        key = "test/other-session/cam-01/seg.ts"
        admin_client.put_object(Bucket=bucket, Key=key, Body=TEST_BODY)

        policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["s3:*"],
                "Resource": [f"arn:aws:s3:::{bucket}/test/admin-session/*"],
            }],
        })
        client = assume_role_with_policy(ADMIN_ACCESS_KEY, ADMIN_SECRET_KEY, policy)

        with pytest.raises(ClientError) as exc_info:
            client.get_object(Bucket=bucket, Key=key)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
