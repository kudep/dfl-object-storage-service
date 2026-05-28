# Гайд для клиентов MinIO

## 1. Обзор

Сервис предоставляет S3-совместимое объектное хранилище (MinIO) для записи и хранения видео.

Клиенты взаимодействуют с MinIO напрямую через стандартный S3 API, используя любой S3-совместимый SDK.

---

## 2. Подключение

### Параметры доступа

| Параметр | Значение |
|----------|----------|
| Endpoint | `http://<host>:9000` |
| Region | `us-east-1` (значение по умолчанию, можно не указывать) |
| Bucket | `videos` |

Credentials (access key / secret key) выдаются администратором.

### Роли

| Роль | Возможности |
|------|-------------|
| **recorder** | Запись объектов, multipart upload, листинг, проверка существования (HEAD) |
| **teacher** | Чтение объектов, листинг |
| **admin** | Полный доступ (root credentials) |

---

## 3. Рекомендуемая структура ключей

```
videos/
  {session_id}/
    {stream_id}/
      segment_000001.ts
      segment_000002.ts
      ...
```

- `session_id` — идентификатор сессии записи (например, UUID или timestamp)
- `stream_id` — идентификатор потока/камеры
- Сегменты именуются с zero-padded номером для правильной сортировки

Пример: `videos/2026-03-30_lecture-101/cam-01/segment_000001.ts`

> Соблюдение этой структуры — ответственность клиента.

---

## 4. Примеры использования

### 4.1 Python (boto3)

#### Установка

```bash
pip install boto3
```

#### Подключение

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://<host>:9000",
    aws_access_key_id="<access_key>",
    aws_secret_access_key="<secret_key>",
)
```

#### Загрузка файла (recorder)

```python
s3.upload_file("local_video.ts", "videos", "session-1/cam-01/segment_000001.ts")
```

#### Загрузка из потока (recorder)

```python
s3.put_object(
    Bucket="videos",
    Key="session-1/cam-01/segment_000001.ts",
    Body=video_bytes,
)
```

#### Проверка существования перед загрузкой (recorder)

```python
from botocore.exceptions import ClientError

def already_uploaded(key: str) -> bool:
    try:
        s3.head_object(Bucket="videos", Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise

key = "session-1/cam-01/segment_000001.ts"
if not already_uploaded(key):
    s3.upload_file("local_video.ts", "videos", key)
```

> `head_object` возвращает только метаданные (размер, ETag), без скачивания тела — это дёшево и удобно для идемпотентной дозагрузки сегментов после сбоя.

#### Multipart upload для больших файлов (recorder)

```python
from boto3.s3.transfer import TransferConfig

config = TransferConfig(
    multipart_threshold=8 * 1024 * 1024,   # 8 MB — порог для переключения на multipart
    multipart_chunksize=8 * 1024 * 1024,    # 8 MB — размер части
    max_concurrency=4,                       # параллельные загрузки частей
)

s3.upload_file(
    "large_video.mp4",
    "videos",
    "session-1/cam-01/full_recording.mp4",
    Config=config,
)
```

#### Скачивание файла (teacher)

```python
s3.download_file("videos", "session-1/cam-01/segment_000001.ts", "local_copy.ts")
```

#### Получение presigned URL для просмотра (teacher)

```python
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": "videos", "Key": "session-1/cam-01/segment_000001.ts"},
    ExpiresIn=3600,  # 1 час
)
print(url)
```

#### Листинг объектов

```python
response = s3.list_objects_v2(Bucket="videos", Prefix="session-1/cam-01/")
for obj in response.get("Contents", []):
    print(obj["Key"], obj["Size"])
```

---

### 4.2 JavaScript / TypeScript (aws-sdk v3)

#### Установка

```bash
npm install @aws-sdk/client-s3 @aws-sdk/lib-storage
```

#### Подключение

```typescript
import { S3Client } from "@aws-sdk/client-s3";

const s3 = new S3Client({
  endpoint: "http://<host>:9000",
  region: "us-east-1",
  credentials: {
    accessKeyId: "<access_key>",
    secretAccessKey: "<secret_key>",
  },
  forcePathStyle: true,
});
```

#### Загрузка (recorder)

```typescript
import { PutObjectCommand } from "@aws-sdk/client-s3";

await s3.send(new PutObjectCommand({
  Bucket: "videos",
  Key: "session-1/cam-01/segment_000001.ts",
  Body: videoBuffer,
}));
```

#### Multipart upload для больших файлов (recorder)

```typescript
import { Upload } from "@aws-sdk/lib-storage";
import { createReadStream } from "fs";

const upload = new Upload({
  client: s3,
  params: {
    Bucket: "videos",
    Key: "session-1/cam-01/full_recording.mp4",
    Body: createReadStream("large_video.mp4"),
  },
  partSize: 8 * 1024 * 1024, // 8 MB
  queueSize: 4,              // параллельные части
});

upload.on("httpUploadProgress", (progress) => {
  console.log(`Uploaded: ${progress.loaded} / ${progress.total}`);
});

await upload.done();
```

#### Скачивание (teacher)

```typescript
import { GetObjectCommand } from "@aws-sdk/client-s3";

const response = await s3.send(new GetObjectCommand({
  Bucket: "videos",
  Key: "session-1/cam-01/segment_000001.ts",
}));

// response.Body — ReadableStream
```

---

### 4.3 Go (minio-go)

#### Установка

```bash
go get github.com/minio/minio-go/v7
```

#### Подключение и загрузка (recorder)

```go
package main

import (
    "context"
    "log"

    "github.com/minio/minio-go/v7"
    "github.com/minio/minio-go/v7/pkg/credentials"
)

func main() {
    client, err := minio.New("<host>:9000", &minio.Options{
        Creds:  credentials.NewStaticV4("<access_key>", "<secret_key>", ""),
        Secure: false,
    })
    if err != nil {
        log.Fatal(err)
    }

    _, err = client.FPutObject(
        context.Background(),
        "videos",
        "session-1/cam-01/segment_000001.ts",
        "local_video.ts",
        minio.PutObjectOptions{ContentType: "video/mp2t"},
    )
    if err != nil {
        log.Fatal(err)
    }
}
```

---

## 5. Multipart Upload — важные детали

При загрузке видео крупными файлами (>5 MB) используйте multipart upload.

### Рекомендуемые параметры

| Параметр | Рекомендация |
|----------|-------------|
| Порог multipart | 8 MB |
| Размер части | 8–16 MB |
| Параллельность | 2–4 потока |
| Максимум частей | 10 000 (ограничение S3 API) |

### Обработка ошибок

- При сбое во время multipart upload **обязательно вызывайте AbortMultipartUpload**, чтобы не копились незавершённые загрузки
- Реализуйте retry с exponential backoff для каждой части отдельно
- Большинство S3 SDK делают это автоматически, но убедитесь, что abort вызывается при критических ошибках

### Пример retry-логики (Python)

```python
from botocore.config import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://<host>:9000",
    aws_access_key_id="<access_key>",
    aws_secret_access_key="<secret_key>",
    config=Config(
        retries={"max_attempts": 5, "mode": "adaptive"},
        max_pool_connections=10,
    ),
)
```

---

## 6. STS (Security Token Service)

Если вашему сервису нужно выдавать **временные credentials** клиентам (например, ограничить запись определённым prefix), вы можете использовать MinIO STS.

### Как это работает

1. Ваш сервис (token service) имеет credentials с правом `sts:AssumeRole`
2. Клиент запрашивает у вашего сервиса временный доступ
3. Ваш сервис вызывает MinIO STS `AssumeRole` с inline policy, ограничивающей scope
4. Клиент получает временные `AccessKey + SecretKey + SessionToken` (живут от 15 мин до 12 часов)
5. Клиент работает с MinIO напрямую, используя временные credentials

### Пример: выдача scoped-токена (Python)

```python
import json
from minio import Minio
from minio.credentials import AssumeRoleProvider

def get_scoped_credentials(session_id: str, duration_seconds: int = 3600):
    """Выдать временные credentials с доступом только к конкретной сессии."""

    policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:AbortMultipartUpload",
            ],
            "Resource": [f"arn:aws:s3:::videos/{session_id}/*"],
        }],
    })

    provider = AssumeRoleProvider(
        sts_endpoint="http://<host>:9000",
        access_key="<recorder_access_key>",
        secret_key="<recorder_secret_key>",
        duration_seconds=duration_seconds,
        policy=policy,
    )

    creds = provider.retrieve()
    return {
        "access_key": creds.access_key,
        "secret_key": creds.secret_key,
        "session_token": creds.session_token,
    }
```

### Использование временных credentials клиентом

```python
temp = get_scoped_credentials("session-1")

s3 = boto3.client(
    "s3",
    endpoint_url="http://<host>:9000",
    aws_access_key_id=temp["access_key"],
    aws_secret_access_key=temp["secret_key"],
    aws_session_token=temp["session_token"],
)

# Работает — prefix совпадает
s3.put_object(Bucket="videos", Key="session-1/cam-01/seg.ts", Body=data)

# 403 Forbidden — другая сессия
s3.put_object(Bucket="videos", Key="session-2/cam-01/seg.ts", Body=data)
```

> Реализация token service — ответственность клиента. MinIO предоставляет STS API, ваш сервис его оркестрирует.

---

## 7. Рекомендации

### Общие

- Используйте TLS в production (настраивается на стороне MinIO)
- Не храните credentials в коде — используйте переменные окружения или secrets manager
- Логируйте ошибки загрузки на своей стороне

### Для recorder

- Нарезайте видео на сегменты (5–30 секунд), загружайте каждый отдельно — это снижает потери при сбое
- Используйте multipart upload для сегментов >8 MB
- Реализуйте локальный буфер: если MinIO недоступен, копите сегменты локально и загружайте при восстановлении связи
- Всегда завершайте или отменяйте multipart uploads — незавершённые загрузки занимают место
- Перед загрузкой сегмента проверяйте его существование через `head_object` — это делает дозагрузку после сбоя идемпотентной (не перезаписывает уже загруженное)

### Для teacher

- Используйте presigned URL для отдачи видео в браузер без проксирования через свой сервер
- Presigned URL можно генерировать с временем жизни (рекомендуется 1–4 часа)
- Для листинга больших объёмов используйте пагинацию (`list_objects_v2` с `ContinuationToken`)

---

## 8. Ограничения

| Ограничение | Значение |
|-------------|----------|
| Максимальный размер объекта | 5 TB |
| Максимальный размер PUT (без multipart) | 5 GB |
| Минимальный размер части multipart | 5 MB (кроме последней) |
| Максимум частей в multipart | 10 000 |
| Максимальная длина ключа | 1024 байт |
