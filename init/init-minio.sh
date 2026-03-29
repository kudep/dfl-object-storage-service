#!/bin/sh
set -e

echo "=== Configuring MinIO ==="

# Set alias for local MinIO
mc alias set local http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

# Create bucket if not exists
if ! mc ls local/"${MINIO_BUCKET}" > /dev/null 2>&1; then
  mc mb local/"${MINIO_BUCKET}"
  echo "Bucket '${MINIO_BUCKET}' created"
else
  echo "Bucket '${MINIO_BUCKET}' already exists"
fi

# Generate policies with actual bucket name
cat > /tmp/recorder.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": ["arn:aws:s3:::${MINIO_BUCKET}/*"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:ListBucketMultipartUploads"
      ],
      "Resource": ["arn:aws:s3:::${MINIO_BUCKET}"]
    }
  ]
}
EOF

cat > /tmp/teacher.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::${MINIO_BUCKET}/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::${MINIO_BUCKET}"]
    }
  ]
}
EOF

# Create policies
mc admin policy create local recorder /tmp/recorder.json
echo "Policy 'recorder' created"

mc admin policy create local teacher /tmp/teacher.json
echo "Policy 'teacher' created"

# Create recorder user
mc admin user add local "${RECORDER_ACCESS_KEY}" "${RECORDER_SECRET_KEY}"
mc admin policy attach local recorder --user "${RECORDER_ACCESS_KEY}"
echo "User 'recorder' created and policy attached"

# Create teacher user
mc admin user add local "${TEACHER_ACCESS_KEY}" "${TEACHER_SECRET_KEY}"
mc admin policy attach local teacher --user "${TEACHER_ACCESS_KEY}"
echo "User 'teacher' created and policy attached"

echo "=== MinIO configuration complete ==="
