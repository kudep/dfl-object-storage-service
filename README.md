# dfl-object-storage-service

S3-совместимое объектное хранилище (MinIO) для записи и хранения видео.

## Быстрый старт

### Разработка

```bash
# Docker volume, данные не на хосте, дефолтные credentials
./scripts/dev.sh up -d
```

### Деплой

```bash
# Создать и заполнить .env.deploy реальными credentials
cp .env.deploy.example .env.deploy

# Локальная папка ./data/minio, боевые credentials
./scripts/deploy.sh up -d
```

Скрипты принимают любые аргументы `docker compose`: `up -d`, `down`, `logs -f`, `ps` и т.д.

После запуска:
- **S3 API:** `http://localhost:9000`
- **Web-консоль:** `http://localhost:9001`

## Роли

| Роль | Возможности |
|------|-------------|
| **admin** | Полный доступ |
| **recorder** | Запись в бакет `videos` |
| **teacher** | Чтение из бакета `videos` |

## Тесты

```bash
# Требуется запущенный MinIO
./scripts/dev.sh up -d
./scripts/test.sh -v
```

## Документация

- [Гайд для клиентов](docs/client-guide.md) — подключение, SDK, примеры, multipart upload, STS
- [Бизнес-требования](docs/business_reqs.md)

## Структура

```
compose.yml            — базовая конфигурация MinIO + init
compose.dev.yml        — override для разработки (docker volume)
compose.deploy.yml     — override для деплоя (bind mount ./data/minio)
.env.dev               — переменные для разработки (в git)
.env.deploy.example    — шаблон переменных для деплоя (в git)
.env.deploy            — боевые credentials (в .gitignore)
pyproject.toml         — зависимости проекта (uv)
scripts/
  dev.sh               — запуск dev-окружения
  deploy.sh            — запуск deploy-окружения
  test.sh              — запуск тестов (credentials из .env.dev)
init/
  init-minio.sh        — создание бакета, пользователей, policies
tests/
  conftest.py          — фикстуры для интеграционных тестов
  test_minio.py        — тесты ролей и permissions
docs/
  client-guide.md      — гайд для клиентов
  business_reqs.md     — бизнес-требования
```
