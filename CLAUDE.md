# RefoAuto - DialogGauge Data Pipeline

Мульти-клиентский проект для генерации JSON из Google Sheets и синхронизации с DialogGauge API.

## Структура проекта

```
refoauto/
├── CLAUDE.md                    # ← Этот файл (общий контекст)
├── clients_config.json          # Конфигурация всех клиентов (locations, branches)
├── run.py                       # Универсальный запуск скриптов: python run.py [client] script
├── src/
│   ├── config_manager.py        # Менеджер конфигурации клиентов
│   ├── hortman/                 # Клиент: Hortman Clinics
│   │   └── CLAUDE.md            # Контекст для hortman
│   └── milena/                  # Клиент: Milena
│       └── CLAUDE.md            # Контекст для milena
└── .env                         # ACTIVE_CLIENT=hortman|milena
```

## Как работает проект

Каждый клиент — это папка в `src/{client_name}/` со стандартной структурой:
- `config/` — credentials, сессии
- `data/input/` — исходные данные (CSV, JSON из Google Sheets)
- `data/output/` — сгенерированные JSON (categories, services, practitioners, service_practitioners)
- `data/api/` — кеш ответов API, отчеты синхронизации
- `scripts/` — скрипты обработки и загрузки
- `models/` — Pydantic модели данных
- `tests/` — тесты (pytest)
- `docs/` — промпты и документация

## Pipeline (одинаковый для всех клиентов)

1. **Парсинг** — Google Sheets CSV → 4 JSON файла (categories, services, practitioners, service_practitioners)
2. **Валидация** — проверка структуры, FK, spot-check с Google Sheets
3. **Sync IDs** — синхронизация локальных ID с DialogGauge API
4. **Загрузка** — POST данных в API (categories → services → practitioners → links)
5. **Тесты** — API validation, content-stats

## Запуск скриптов

```bash
python run.py hortman get_categories --all
python run.py milena sync_with_api --categories-only
```

## Важные правила

- Промпт для каждого клиента находится в `src/{client}/docs/PROMPT.md`
- Credentials НЕ коммитить (config/*.json в .gitignore)
- Перед загрузкой ВСЕГДА запускать тесты
- fix_locations.py по умолчанию dry-run, нужен `--execute` для реального выполнения
