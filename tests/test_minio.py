"""Integration tests for MinIO setup: bucket, roles, and permissions."""

import io

import pytest
from botocore.exceptions import ClientError

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
        # Recorder has no GetObject/HeadObject — verify via ListObjects
        response = recorder_client.list_objects_v2(Bucket=bucket, Prefix=TEST_KEY)
        objects = response.get("Contents", [])
        assert len(objects) == 1
        assert objects[0]["Key"] == TEST_KEY
        assert objects[0]["Size"] == len(TEST_BODY)

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
            # Recorder has no GetObject/HeadObject — verify via ListObjects
            response = recorder_client.list_objects_v2(Bucket=bucket, Prefix=key)
            objects = response.get("Contents", [])
            assert len(objects) == 1
            assert objects[0]["Size"] == len(part_data) + len(b"final-part")
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

    def test_cannot_read(self, recorder_client, admin_client, bucket):
        admin_client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        with pytest.raises(ClientError) as exc_info:
            recorder_client.get_object(Bucket=bucket, Key=TEST_KEY)
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"


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
