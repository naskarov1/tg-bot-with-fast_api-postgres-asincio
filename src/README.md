# Telegram Bot with PostgreSQL

Телеграм-бот для управления расписанием занятий, напоминаниями и домашними заданиями. Данные сохраняются в PostgreSQL, а уведомления отправляются по расписанию через APScheduler.

## Возможности

- Добавление занятий в расписание
- Добавление домашних заданий к конкретному занятию
- Настройка напоминаний за определённое количество минут
- Просмотр списка занятий
- Telegram UI через кнопки и FSM-состояния
- Запуск через Docker Compose

## Структура проекта

```text
.
├── src/
│   ├── bot/
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── states.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── scheduler.py
│   └── __init__.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── .env
```

## Требования

- Docker
- Docker Compose
- Python 3.12 (если запускать локально без контейнера)

## Настройка окружения

Скопируйте пример файла:

```bash
cp .env.example .env
```

После этого отредактируйте `.env`:

```env
BOT_TOKEN=123456:ABCDEF
DATABASE_URL=postgresql+asyncpg://app:app_password@db:5432/schedule_db
```

Если вы запускаете проект локально на хосте, можно использовать:

```env
BOT_TOKEN=123456:ABCDEF
DATABASE_URL=postgresql+asyncpg://app:app_password@localhost:5432/schedule_db
```

## Локальный запуск

1. Установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Запустите бота:

```bash
python -m src.main
```

## Запуск через Docker Compose

```bash
docker compose up --build
```

Для завершения:

```bash
docker compose down
```

Если нужно удалить том с данными PostgreSQL:

```bash
docker compose down -v
```

## Основные переменные окружения

- `BOT_TOKEN` — токен Telegram-бота
- `DATABASE_URL` — строка подключения к PostgreSQL для SQLAlchemy AsyncEngine

## Примечание

При запуске в контейнере `DATABASE_URL` должен указывать на имя сервиса `db`, то есть:

```env
DATABASE_URL=postgresql+asyncpg://app:app_password@db:5432/schedule_db
```

Это важно, потому что внутри Docker-переносной сети сервис PostgreSQL доступен по имени контейнера, а не `localhost`.
