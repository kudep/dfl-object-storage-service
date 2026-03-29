# dfl-object-storage-service

S3-совместимое объектное хранилище (MinIO) для записи и хранения видео.

## Быстрый старт

```bash
# Скопировать и настроить переменные окружения
cp .env.example .env

# Поднять MinIO + автоматическая инициализация (бакет, пользователи, policies)
docker compose up -d
```

После запуска:
- **S3 API:** `http://localhost:9000`
- **Web-консоль:** `http://localhost:9001` (логин: значения из `.env`)

## Роли

| Роль | Credentials (по умолчанию) | Возможности |
|------|---------------------------|-------------|
| **admin** | `minioadmin` / `minioadmin` | Полный доступ |
| **recorder** | `recorder` / `recorder-secret-change-me` | Запись в бакет `videos` |
| **teacher** | `teacher` / `teacher-secret-change-me` | Чтение из бакета `videos` |

## Тесты

```bash
# Требуется запущенный MinIO (docker compose up -d)
uv run --group test pytest tests/ -v
```

## Документация

- [Гайд для клиентов](docs/client-guide.md) — подключение, SDK, примеры, multipart upload, STS
- [Бизнес-требования](docs/business_reqs.md)

## Структура

```
docker-compose.yml     — MinIO server + init контейнер
.env.example           — шаблон переменных окружения
pyproject.toml         — зависимости проекта (uv)
init/
  init-minio.sh        — создание бакета, пользователей, policies
tests/
  conftest.py          — фикстуры для интеграционных тестов
  test_minio.py        — тесты ролей и permissions
docs/
  client-guide.md      — гайд для клиентов
  business_reqs.md     — бизнес-требования
```
