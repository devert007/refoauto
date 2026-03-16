# Quick Start Guide

## Для существующего клиента (Hortman)

```bash
# 1. Перейти в директорию
cd src/hortman

# 2. Запустить полный цикл
python scripts/process_data.py                  # Обработать CSV
python scripts/parse_practitioners_sheet.py     # Получить practitioners
python scripts/sync_with_api.py                 # Синхронизировать IDs
python scripts/fix_locations.py --analyze       # Проанализировать
python scripts/fix_locations.py --step1 --execute   # Загрузить данные

# 3. Вернуться в корень
cd ../..
```

## Для нового клиента (Milena)

### Первоначальная настройка

```bash
# 1. Отредактировать clients_config.json
nano clients_config.json

# Добавить/изменить:
{
  "milena": {
    "enabled": true,
    "locations": [
      {
        "location_id": 30,  // ← ВАШ location_id
        "name": "Main",
        "branch": "main"
      }
    ],
    "branch_to_location": {
      "main": 30
    }
  }
}

# 2. Установить активного клиента
echo "ACTIVE_CLIENT=milena" > .env

# 3. Добавить данные
# Положите CSV файл в src/milena/data/input/

# 4. Запустить обработку
cd src/milena
python scripts/process_data.py
python scripts/sync_with_api.py
```

## Переключение между клиентами

### Метод 1: Изменить .env (глобально)

```bash
# В файле .env
ACTIVE_CLIENT=hortman  # или milena
```

### Метод 2: Просто перейти в нужную директорию

```bash
cd src/hortman   # Работать с Hortman
cd src/milena    # Работать с Milena
```

## Основные команды

### Получить данные из API

```bash
cd src/{client}
python scripts/get_categories.py --all
```

### Обработать входные данные

```bash
cd src/{client}
python scripts/process_data.py
```

### Синхронизировать IDs

```bash
cd src/{client}
python scripts/sync_with_api.py
```

### Проанализировать состояние (multi-location)

```bash
cd src/{client}
python scripts/fix_locations.py --analyze
```

### Загрузить данные (multi-location)

```bash
cd src/{client}
python scripts/fix_locations.py --step1 --execute  # Categories
python scripts/fix_locations.py --step2 --execute  # Services
python scripts/fix_locations.py --step4 --execute  # Practitioners
python scripts/fix_locations.py --step5 --execute  # Links
```

## Проверка конфигурации

### Показать текущую конфигурацию

```bash
python src/config_manager.py
```

### Показать location_ids для клиента

```bash
python -c "from src.config_manager import get_client_config; print(get_client_config('milena').get_location_ids())"
```

## Структура файлов клиента

```
src/{client}/
├── scripts/
│   ├── get_categories.py         # Fetch from API
│   ├── process_data.py           # Process input → JSON
│   ├── sync_with_api.py          # Sync local IDs ↔ API IDs
│   └── fix_locations.py          # Multi-location upload
├── data/
│   ├── input/raw_data.csv        # ← Ваши входные данные
│   ├── output/
│   │   ├── categories.json       # ← Результаты обработки
│   │   ├── services.json
│   │   ├── practitioners.json
│   │   └── service_practitioners.json
│   └── api/                      # Кеш API ответов
└── config/
    ├── .dg_session.json          # Сессия DialogGauge
    └── credentials.json          # Google Sheets creds
```

## Частые проблемы

### "Module not found"
→ Запускайте из директории клиента: `cd src/{client}`

### "Location ID not configured"
→ Проверьте `clients_config.json`, установите `location_id`

### "Session expired"
→ Скрипт автоматически откроет браузер для повторной аутентификации

## Полезные ссылки

- [README.md](README.md) - Полная документация
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Гайд по миграции
- [clients_config.json](clients_config.json) - Конфигурация клиентов
- [src/config_manager.py](src/config_manager.py) - Config Manager API
