# RefoAuto - DialogGauge Data Processing

Автоматизация обработки данных услуг для DialogGauge API.

## Структура проекта

```
refoauto/
├── scripts/              # Python скрипты
│   ├── get_categories.py # Получение категорий из API
│   ├── sync_with_api.py  # Синхронизация с API
│   ├── assign_ids.py     # Присвоение уникальных ID
│   ├── process_data.py   # Обработка CSV → JSON
│   └── auth_oauth.py     # OAuth авторизация (экспериментально)
│
├── data/
│   ├── output/           # Выходные JSON файлы
│   │   ├── categories.json
│   │   ├── practitioners.json
│   │   ├── services.json
│   │   └── service_practitioners.json
│   ├── api/              # Данные из API
│   │   ├── categories_api_response.json
│   │   └── _sync_report.json
│   └── input/            # Входные данные
│       └── raw_data.csv
│
├── config/               # Конфигурация
│   ├── credentials.json  # Google API credentials
│   └── .dg_session.json  # Сессия DialogGauge
│
├── docs/                 # Документация
│   └── PROMPT_FOR_CLAUDE_CODE.md
│
├── models/               # Python модели
│   ├── models.py
│   └── pydantic_models.py
│
└── .playwright_profile/  # Профиль браузера (для авто-логина)
```

## Установка

```bash
pip install requests playwright
python -m playwright install chromium
```

## Использование

### 1. Получить данные из API

```bash
# Только категории
python scripts/get_categories.py

# Только сервисы
python scripts/get_categories.py --services

# Всё (категории + сервисы + practitioners)
python scripts/get_categories.py --all
```

При первом запуске откроется браузер для входа через Google.
После логина сессия сохраняется и последующие запуски автоматические.

### 2. Обработать CSV данные

```bash
python scripts/process_data.py
```

Читает `data/input/raw_data.csv` и создаёт JSON файлы в `data/output/`.

### 3. Присвоить уникальные ID

```bash
python scripts/assign_ids.py
```

### 4. Синхронизировать с API

```bash
# Синхронизировать категории и сервисы
python scripts/sync_with_api.py

# Только категории
python scripts/sync_with_api.py --categories-only

# Только сервисы  
python scripts/sync_with_api.py --services-only
```

Сравнивает локальные данные с API и:
- Использует существующие ID для совпадающих элементов
- Присваивает новые ID для новых элементов
- Обновляет все ссылки (`category_id`, `service_id`)

## Полный пайплайн

```bash
# 1. Положить CSV в data/input/raw_data.csv
# 2. Запустить:
python scripts/process_data.py
python scripts/assign_ids.py
python scripts/sync_with_api.py

# 3. Результат в data/output/
```

## Переменные окружения

- `DG_SESSION` - токен сессии DialogGauge (опционально, иначе через браузер)

## API

- Base URL: `https://dialoggauge.yma.health/api`
- Location ID: `10`
- Auth: Cookie `dg_session` (Google OAuth)







1.python3 scripts/get_categories.py --categories
2. python3 scripts/upload_categories.py
3. python3 scripts/upload_categories.py --execute