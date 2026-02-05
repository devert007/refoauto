# Руководство по загрузке данных в DialogGauge API

## Структура проекта

```
refoauto/
├── config/
│   └── .dg_session.json       # Сессия авторизации (автоматически обновляется)
├── data/
│   ├── input/
│   │   └── raw_data.csv       # Исходные данные
│   ├── output/                # Локальные JSON (подготовлены к загрузке)
│   │   ├── categories.json
│   │   ├── services.json
│   │   ├── practitioners.json
│   │   └── service_practitioners.json
│   └── api/                   # Ответы от API (для сравнения)
│       ├── categories_api_response.json
│       └── services_api_response.json
├── scripts/
│   ├── get_categories.py      # API функции (GET/POST)
│   ├── upload_categories.py   # Загрузка категорий
│   ├── upload_services.py     # Загрузка сервисов
│   └── sync_with_api.py       # Синхронизация ID
└── docs/
    └── UPLOAD_GUIDE.md        # Это руководство
```

---

## Настройка

### Location ID
Текущий `LOCATION_ID = 17` (настраивается в `scripts/get_categories.py`)

### Авторизация
Сессия хранится в `config/.dg_session.json`. Если истечёт — скрипт автоматически откроет браузер для входа через Google.

---

## Порядок загрузки данных

### 1. КАТЕГОРИИ

```bash
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"

# Шаг 1: Проверка (что будет создано)
python3 scripts/upload_categories.py

# Шаг 2: Загрузка (если всё ОК)
python3 scripts/upload_categories.py --execute
```

**Что делает:**
- Получает категории из API
- Сравнивает с локальными (по имени)
- Создаёт только новые

---

### 2. СЕРВИСЫ

**ВАЖНО:** Сначала загрузите ВСЕ категории! Сервисы привязаны к категориям.

```bash
# Шаг 1: Проверка (что будет создано)
python3 scripts/upload_services.py

# Шаг 2: Загрузка (если всё ОК)
python3 scripts/upload_services.py --execute

# Или загрузить только первые N сервисов (для теста)
python3 scripts/upload_services.py --execute --limit=5
```

**Что делает:**
- Получает категории и сервисы из API
- Строит маппинг категорий (local_id → api_id) по имени
- Сравнивает сервисы с API (по имени)
- Создаёт только новые сервисы с правильным category_id

**Предупреждения:**
- Покажет сервисы без категории (если категория не найдена в API)
- Такие сервисы создадутся БЕЗ категории

---

## Вспомогательные команды

### Получить данные из API (только GET)

```bash
# Категории
python3 scripts/get_categories.py --categories

# Сервисы
python3 scripts/get_categories.py --services

# Practitioners
python3 scripts/get_categories.py --practitioners

# Всё сразу
python3 scripts/get_categories.py --all
```

Результаты сохраняются в `data/api/`

### Создать одну тестовую категорию

```bash
python3 scripts/get_categories.py --create-test --location=17 --name="Test Category"
```

---

## Логика сравнения

| Локальный элемент | API | Результат |
|------------------|-----|-----------|
| Есть по имени | Есть | ✓ Пропускается |
| Есть по имени | Нет | + Создаётся |

**Нормализация имён:**
- Приводится к нижнему регистру
- Убираются лишние пробелы
- Убираются спецсимволы

Пример: `"BOTOX "` и `"botox"` → считаются одинаковыми

---

## Связь между сущностями

```
Categories (категории)
    ↓ category_id
Services (услуги)
    ↓ service_id
ServicePractitioners (связь услуга-врач)
    ↑ practitioner_id
Practitioners (врачи)
```

**Порядок загрузки:**
1. Categories (нет зависимостей)
2. Services (зависят от Categories)
3. Practitioners (нет зависимостей)
4. ServicePractitioners (зависят от Services и Practitioners)

---

## API Endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/locations/{id}/categories` | Список категорий |
| POST | `/api/locations/{id}/categories` | Создать категорию |
| GET | `/api/locations/{id}/services` | Список сервисов |
| POST | `/api/locations/{id}/services` | Создать сервис |
| GET | `/api/locations/{id}/practitioners` | Список врачей |
| POST | `/api/locations/{id}/practitioners` | Создать врача |

---

## Troubleshooting

### Ошибка 401 (Unauthorized)
Сессия истекла. Скрипт автоматически попробует обновить. Если не получится — удалите `config/.dg_session.json` и запустите снова.

### Ошибка 422 (Validation Error)
Проверьте формат данных. API ожидает:
- `name`: `{"en": "Name"}` (объект, не строка)
- `location_id`: число

### Категория не найдена для сервиса
Сначала загрузите категории! Или проверьте, что имя категории совпадает.
