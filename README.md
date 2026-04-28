# Upwork Freelance Bot

Telegram-бот для фрилансеров на платформе Upwork с AI-генерацией откликов.

## Функции

- 📁 **Лента проектов** — получение актуальных проектов с Upwork
- 🔍 **Фильтры** — фильтрация по категориям, ключевым словам, бюджету
- 🤖 **AI-отклики** — генерация cover letters через GPT-4o
- 💎 **Подписки** — Free (5 генераций/день) и Pro (безлимит)
- 🔔 **Уведомления** — push о новых проектах
- 👥 **Реферальная система** — 7 дней Pro за приглашение

## Архитектура

```
┌─────────────────┐     ┌─────────────────┐
│  telegram-bot   │────▶│  api-gateway    │
│  (aiogram 3.x)  │     │  (FastAPI)      │
└─────────────────┘     └────────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ parser-service  │     │   ai-service    │     │ notification-   │
│ (Upwork API)    │     │  (OpenAI GPT)   │     │    service      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
            ┌─────────────┐           ┌─────────────┐
            │   Redis     │           │  PostgreSQL │
            └─────────────┘           └─────────────┘
```

### Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| telegram-bot | - | Обработка команд, FSM, inline-клавиатуры |
| api-gateway | 8000 | Единая точка входа, REST API |
| parser-service | 8001 | Парсинг Upwork, кэширование |
| ai-service | 8002 | Генерация cover letters |
| notification-service | - | Push-уведомления по расписанию |

## Установка

### 1. Клонирование

```bash
git clone https://github.com/your-repo/upwork-bot.git
cd upwork-bot
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
# Telegram
BOT_TOKEN=your_bot_token_from_@BotFather

# OpenAI
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/upwork_bot
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=upwork_bot

# Upwork API (опционально для OAuth)
UPWORK_CLIENT_ID=...
UPWORK_CLIENT_SECRET=...

# Payment (опционально)
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
```

### 3. Запуск

```bash
docker-compose up -d --build
```

### 4. Проверка

```bash
curl http://localhost:8000/health
```

## Разработка

### Структура проекта

```
upwork-bot/
├── docker-compose.yml
├── .env.example
├── README.md
├── shared/                 # Общие модули
│   ├── database.py        # SQLAlchemy setup
│   ├── models_db.py       # ORM модели
│   └── utils.py           # Утилиты
├── telegram-bot/          # Telegram бот
│   ├── app/
│   │   ├── handlers/      # Обработчики команд
│   │   ├── keyboard/      # Inline клавиатуры
│   │   ├── fsm/           # Машины состояний
│   │   └── middleware/    # Middleware
│   └── Dockerfile
├── api-gateway/           # REST API
│   ├── app/
│   │   └── routers/       # API endpoints
│   └── Dockerfile
├── parser-service/        # Парсинг Upwork
│   ├── app/
│   │   └── services/
│   │       ├── upwork.py  # API клиент
│   │       └── cache.py   # Кэширование
│   └── Dockerfile
├── ai-service/            # OpenAI интеграция
│   ├── app/
│   │   └── services/
│   │       └── openai_service.py
│   └── Dockerfile
├── notification-service/  # Уведомления
│   ├── app/
│   │   └── services/
│   │       └── notification.py
│   └── Dockerfile
└── tests/                 # Тесты
```

### Локальный запуск (без Docker)

```bash
# Установка зависимостей
pip install -r telegram-bot/requirements.txt

# Запуск Redis и PostgreSQL
docker-compose up -d redis db

# Запуск сервисов
uvicorn api-gateway.app.main:app --port 8000
python -m telegram-bot.app.main
python -m parser-service.app.main
python -m ai-service.app.main
python -m notification-service.app.main
```

### Тесты

```bash
pytest tests/
```

## API Endpoints

### Пользователи
- `POST /users/` — создать пользователя
- `GET /users/{telegram_id}` — получить пользователя
- `GET /users/status/{telegram_id}` — статус

### Проекты
- `GET /projects/{telegram_id}` — список проектов
- `GET /projects/{telegram_id}/project/{id}` — детали проекта

### Фильтры
- `GET /filters/{telegram_id}` — список фильтров
- `POST /filters/{telegram_id}` — создать фильтр
- `PUT /filters/{telegram_id}/{id}` — обновить
- `DELETE /filters/{telegram_id}/{id}` — удалить

### AI
- `POST /ai/{telegram_id}/generate` — генерация cover letter
- `GET /ai/{telegram_id}/prompt` — получить промпт
- `PUT /ai/{telegram_id}/prompt` — обновить промпт
- `POST /ai/{telegram_id}/import-style` — импорт стиля

### Подписка
- `GET /subscription/{telegram_id}/status` — статус подписки
- `POST /subscription/{telegram_id}/pay` — оплата
- `GET /subscription/{telegram_id}/referral` — реферальная программа

## Стек

- **Python 3.11+**
- **aiogram 3.x** — Telegram Bot
- **FastAPI** — REST API
- **SQLAlchemy 2.0** — ORM
- **PostgreSQL** — база данных
- **Redis** — кэш, сессии
- **APScheduler** — планировщик
- **OpenAI GPT-4o** — генерация текста
- **Docker Compose** — контейнеризация
- **pytest** — тесты

## Лицензия

MIT
