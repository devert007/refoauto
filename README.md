# DialogGauge API Automation - Multi-Client

Автоматизация работы с DialogGauge API для нескольких клиентов (Hortman, Milena, и др.).

## 🎯 Быстрый старт

### 1. Установка

```bash
pip install requests playwright
python -m playwright install chromium
```

### 2. Настройка клиента

Отредактируйте `clients_config.json` - укажите `location_id` для ваших филиалов:

```json
{
  "clients": {
    "hortman": {
      "enabled": true,
      "locations": [
        {"location_id": 28, "name": "Jumeirah", "branch": "jumeirah"},
        {"location_id": 29, "name": "SZR", "branch": "szr"}
      ]
    },
    "milena": {
      "enabled": false,
      "locations": [
        {"location_id": null, "name": "Main", "branch": "main"}
      ]
    }
  },
  "active_client": "hortman"
}
```

### 3. Запуск (для активного клиента)

```bash
# Перейти в директорию клиента
cd src/hortman  # или src/milena

# Запустить обработку
python scripts/process_data.py
python scripts/sync_with_api.py
python scripts/fix_locations.py --analyze
```

## 📁 Структура проекта

```
refoauto/
├── clients_config.json          # ← Конфигурация всех клиентов
├── .env                         # ← Активный клиент (ACTIVE_CLIENT=hortman)
├── .env.example                 # Пример настроек
├── run.py                       # Универсальный запускалка (WIP)
│
├── src/
│   ├── config_manager.py        # Менеджер конфигураций
│   │
│   ├── hortman/                 # ← Клиент #1: Hortman Clinics
│   │   ├── scripts/             # Скрипты обработки и API sync
│   │   ├── models/              # Модели данных
│   │   ├── tests/               # Тесты
│   │   ├── data/
│   │   │   ├── input/           # Входные данные (CSV, etc.)
│   │   │   ├── output/          # Обработанные JSON файлы
│   │   │   └── api/             # Кеш API ответов
│   │   ├── config/              # Конфиги (credentials, session)
│   │   └── docs/                # Документация клиента
│   │
│   └── milena/                  # ← Клиент #2: Milena (шаблон)
│       ├── scripts/
│       ├── models/
│       ├── tests/
│       ├── data/
│       ├── config/
│       ├── docs/
│       └── README.md            # Инструкции для Milena
│
└── README.md                    # ← Вы здесь
```

## 🔄 Workflow: Полный цикл обработки данных

### Для Hortman (2 филиала: Jumeirah + SZR)

```bash
cd src/hortman

# Step 1: Получить данные
python scripts/process_data.py                  # Categories + Services из CSV
python scripts/parse_practitioners_sheet.py     # Practitioners из Google Sheets

# Step 2: Синхронизировать ID с API
python scripts/sync_with_api.py

# Step 3: Проанализировать текущее состояние
python scripts/fix_locations.py --analyze

# Step 4: Загрузить данные (по шагам, с --execute для выполнения)
python scripts/fix_locations.py --step1 --execute   # Categories → оба locations
python scripts/fix_locations.py --step2 --execute   # Services → по branches
python scripts/fix_locations.py --step4 --execute   # Practitioners → по branches
python scripts/fix_locations.py --step5 --execute   # Service-practitioner links
```

### Для нового клиента (Milena)

```bash
cd src/milena

# Step 1: Настроить location_id в clients_config.json
# Step 2: Добавить данные в data/input/
# Step 3: Запустить обработку
python scripts/process_data.py
python scripts/sync_with_api.py
```

## ⚙️ Настройка нового клиента

### Шаг 1: Добавить конфигурацию

В `clients_config.json`:

```json
"milena": {
  "enabled": true,
  "display_name": "Milena Clinics",
  "base_path": "src/milena",
  "locations": [
    {
      "location_id": 30,           // ← Ваш location_id из DialogGauge
      "name": "Main Location",
      "branch": "main",
      "description": "Main branch"
    }
  ],
  "branch_to_location": {
    "main": 30
  }
}
```

### Шаг 2: Скопировать скрипты

```bash
cp -r src/hortman/scripts/* src/milena/scripts/
cp -r src/hortman/models/* src/milena/models/
```

### Шаг 3: Подготовить данные

Добавьте CSV или другие данные в `src/milena/data/input/`

### Шаг 4: Запустить

```bash
cd src/milena
python scripts/process_data.py
python scripts/sync_with_api.py
```

## 🌍 Location IDs и Branches

Каждый клиент может иметь несколько локаций (филиалов).

### Пример: Hortman (2 локации)

| Location ID | Название | Branch     | Описание         |
| ----------- | -------- | ---------- | ---------------- |
| 28          | Jumeirah | `jumeirah` | Jumeirah branch  |
| 29          | SZR      | `szr`      | Sheikh Zayed Rd. |

### Правила распределения по branches

Для **Services** и **Practitioners**:

- `branches: ["jumeirah"]` → только Location 28
- `branches: ["szr"]` → только Location 29
- `branches: ["jumeirah", "szr"]` → оба locations
- `branches: []` (пусто, только practitioners) → оба locations

Для **Categories**:

- Не имеют branches → одинаковые для всех locations

## 🔧 Config Manager API

Используйте `config_manager.py` для доступа к конфигурации из Python:

```python
from src.config_manager import get_client_config

# Получить конфиг активного клиента
config = get_client_config()

# Или конкретного клиента
config = get_client_config("milena")

# Использовать пути
print(config.data_dir)        # → .../src/milena/data
print(config.scripts_dir)     # → .../src/milena/scripts
print(config.config_dir)      # → .../src/milena/config

# Получить location IDs
location_ids = config.get_location_ids()  # → [30]

# Маппинг branch → location_id
location = config.get_location_by_branch("main")  # → 30
```

## 🚀 Основные скрипты

### `process_data.py`

Обрабатывает входные данные (CSV) и создает JSON файлы.

```bash
python scripts/process_data.py
```

Создает:

- `data/output/categories.json`
- `data/output/services.json`
- `data/output/service_practitioners.json`

### `sync_with_api.py`

Синхронизирует локальные ID с API ID.

```bash
python scripts/sync_with_api.py
python scripts/sync_with_api.py --categories-only
python scripts/sync_with_api.py --services-only
```

### `get_categories.py`

Загружает данные из API (библиотека + CLI).

```bash
python scripts/get_categories.py --all
python scripts/get_categories.py --services
```

### `fix_locations.py`

Распределяет данные по локациям (для multi-location клиентов).

```bash
python scripts/fix_locations.py --analyze
python scripts/fix_locations.py --step1 --execute
```

## 🔐 Конфигурационные файлы

### `clients_config.json`

Основная конфигурация всех клиентов с location_ids.

### `.env`

Переменные окружения:

```env
ACTIVE_CLIENT=hortman
DG_SESSION=your_session_cookie  # Опционально
```

### `src/{client}/config/`

Клиент-специфичные конфиги:

- `.dg_session.json` - кеш сессии DialogGauge
- `credentials.json` - Google Sheets credentials
- `sheets_token.json` - Google Sheets token

## 🔄 Переключение между клиентами

### Способ 1: Через .env файл

```bash
# В файле .env
ACTIVE_CLIENT=milena
```

### Способ 2: Через environment variable

```bash
ACTIVE_CLIENT=milena python run.py get_categories
```

### Способ 3: Явное указание (WIP)

```bash
python run.py milena get_categories --all
```

### Способ 4: Просто перейти в директорию

```bash
cd src/milena
python scripts/get_categories.py --all
```

## 📚 API Reference

- **Base URL:** `https://dialoggauge.yma.health/api`
- **Auth:** Cookie `dg_session` (автоматически через Playwright OAuth)

### Endpoints

| Метод  | Endpoint                                        | Описание                        |
| ------ | ----------------------------------------------- | ------------------------------- |
| GET    | `/locations/{id}/categories`                    | Список категорий                |
| POST   | `/locations/{id}/categories`                    | Создать категорию               |
| GET    | `/locations/{id}/services`                      | Список сервисов                 |
| POST   | `/locations/{id}/services`                      | Создать сервис                  |
| GET    | `/locations/{id}/practitioners`                 | Список practitioners            |
| POST   | `/locations/{id}/practitioners`                 | Создать practitioner            |
| POST   | `/locations/{id}/practitioners/{id}/services`   | Привязать сервис к practitioner |

Параметры:

- `?flat=true` - плоский список категорий
- `?include_archived=true` - включая архивные

## 🐛 Troubleshooting

### "Script not found" или "Module not found"

Убедитесь, что запускаете скрипт из директории клиента:

```bash
cd src/hortman  # или src/milena
python scripts/your_script.py
```

### Location ID не настроен

Проверьте `clients_config.json` - убедитесь, что `location_id` указан для вашего клиента.

### Ошибка импорта модулей

Запускайте скрипты из директории клиента или добавьте project root в PYTHONPATH:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Session expired

Скрипт автоматически обновит сессию через Playwright. При первом запуске откроется браузер для Google OAuth.

## 📖 Дополнительная документация

- **Hortman-specific:** [src/hortman/docs/](src/hortman/docs/)
- **Milena setup:** [src/milena/README.md](src/milena/README.md)
- **Config Manager:** См. комментарии в [src/config_manager.py](src/config_manager.py)

## 🎯 Миграция со старой структуры

Старая структура (всё в корне) автоматически перемещена в `src/hortman/`.

Если у вас есть старые ссылки:

- `scripts/` → `src/hortman/scripts/`
- `data/` → `src/hortman/data/`
- `config/` → `src/hortman/config/`

## 📝 TODO / Roadmap

- [ ] Полная интеграция config_manager во все скрипты
- [ ] Автоматическое создание структуры для нового клиента
- [ ] CLI tool для управления клиентами (`python cli.py add-client milena`)
- [ ] Unified тестирование для всех клиентов
- [ ] Docker контейнер для isolated запуска

## 📄 License

Internal use only.
