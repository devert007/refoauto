# Milena - DialogGauge Data Pipeline

Pipeline для генерации и синхронизации данных (категории, сервисы, специалисты) из Google Sheets CSV в DialogGauge API для клиента Milena.

---

## Quick Start

### 1. Настройка location_id

Убедись, что в `clients_config.json` установлен правильный `location_id` для Milena:

```json
{
  "clients": {
    "milena": {
      "enabled": true,
      "locations": [
        {
          "location_id": 30,  // ← Установи правильный ID
          "name": "Main Location",
          "branch": "main"
        }
      ]
    }
  }
}
```

### 2. Генерация категорий из CSV

```bash
cd src/milena
python scripts/generate_categories.py
```

**Что делает:**
- Читает все CSV файлы из `data/input/*.csv`
- Извлекает уникальные категории из колонки "Категория"
- Переводит названия на английский
- Создает `data/output/categories.json`

**Опционально с OpenAI для лучшего перевода:**
```bash
OPENAI_API_KEY=sk-... python scripts/generate_categories.py
```

### 3. Синхронизация ID с API

```bash
python scripts/sync_with_api.py --categories-only
```

**Что делает:**
- Получает существующие категории из DialogGauge API
- Сопоставляет локальные категории с API
- Присваивает правильные ID (из API или новые)
- Обновляет `data/output/categories.json`

---

## Структура данных

### Входные данные

CSV файлы в `data/input/`:
- `Milena Services Description - Ботулинотерапия.csv`
- `Milena Services Description - Филлеры.csv`
- `Milena Services Description - Биоревитализация.csv`
- И т.д.

### Выходные данные

JSON файлы в `data/output/`:
- `categories.json` - Категории услуг
- `services.json` - Услуги (будет добавлено позже)
- `practitioners.json` - Специалисты (будет добавлено позже)
- `service_practitioners.json` - Связи услуги ↔ специалисты

### API кеш

JSON файлы в `data/api/`:
- `categories_api_response.json` - Ответ API для категорий
- `services_api_response.json` - Ответ API для услуг
- `_sync_report.json` - Отчет синхронизации

---

## Модели данных

Все модели определены в `models/pydantic_models.py`:

### ServiceCategory

```python
class ServiceCategory(BaseModel):
    id: int
    name_i18n: dict  # {"en": "Biorevitalization", "ru": "Биоревитализация"}
    sort_order: int
```

Пример:
```json
{
  "id": 1,
  "name_i18n": {
    "en": "Botulinum Therapy",
    "ru": "Ботулинотерапия"
  },
  "sort_order": 1
}
```

---

## Скрипты

### generate_categories.py

Генерирует `categories.json` из CSV файлов.

**Использование:**
```bash
cd src/milena
python scripts/generate_categories.py
```

**Опции:**
- Установи `OPENAI_API_KEY` для автоматического перевода на английский
- Без ключа используется простой словарь перевода

### sync_with_api.py

Синхронизирует ID с DialogGauge API.

**Использование:**
```bash
cd src/milena
python scripts/sync_with_api.py --categories-only
```

**Опции:**
- `--categories-only` - Синхронизировать только категории
- `--services-only` - Синхронизировать только услуги
- `--practitioners-only` - Синхронизировать только специалистов
- Без флагов - синхронизировать все

### get_categories.py

Получает данные из DialogGauge API.

**Использование:**
```bash
cd src/milena
python scripts/get_categories.py              # Категории
python scripts/get_categories.py --services   # Услуги
python scripts/get_categories.py --all        # Всё
```

---

## Логика синхронизации ID

1. **Получить данные из API:**
   - GET `/api/locations/{location_id}/categories`

2. **Найти max ID в API:**
   - `max_api_id = max(cat["id"] for cat in api_categories)`

3. **Для каждой локальной категории:**
   - Нормализовать название (lowercase, убрать знаки)
   - Искать совпадение в API по названию
   - Если найдено → использовать ID из API
   - Если не найдено → присвоить новый ID = `max_api_id + 1, +2, ...`

4. **Обновить и сохранить:**
   - Обновить `categories.json` с правильными ID
   - Сохранить отчет в `_sync_report.json`

---

## Примеры категорий

Из CSV файлов Milena:

| Русское название                | English Translation      |
| ------------------------------- | ------------------------ |
| Ботулинотерапия                 | Botulinum Therapy        |
| Контурная пластика (филлеры)   | Dermal Fillers           |
| Биоревитализация                | Biorevitalization        |
| Skin Boosters                   | Skin Boosters            |
| Биорепаранты                    | Bioremodelling           |
| Мезотерапия                     | Mesotherapy              |
| Тредлифтинг                     | Thread Lifting           |
| Стимуляторы коллагена           | Collagen Stimulators     |
| Липолитики                      | Lipolytics               |

---

## Частые проблемы

### "Location ID not configured"

**Решение:**
- Открой `clients_config.json`
- Установи правильный `location_id` для Milena
- Пример:
  ```json
  {
    "milena": {
      "locations": [
        {"location_id": 30, "name": "Main", "branch": "main"}
      ]
    }
  }
  ```

### "Session expired"

**Решение:**
- Скрипт автоматически откроет браузер
- Войди через Google OAuth
- Сессия сохранится в `config/.dg_session.json`

### "No CSV files found"

**Решение:**
- Убедись, что CSV файлы находятся в `src/milena/data/input/`
- Проверь имена файлов: `*.csv`

---

## См. также

- [SKILL.md](../../docs/SKILL.md) - Полная инструкция для Claude Code
- [clients_config.json](../../clients_config.json) - Конфигурация клиентов
- [models/pydantic_models.py](models/pydantic_models.py) - Модели данных
- [QUICK_START.md](../../QUICK_START.md) - Быстрый старт для всех клиентов

---

## Roadmap

- [x] Генерация категорий из CSV
- [x] Синхронизация ID с API
- [x] Автоматический перевод на английский (OpenAI)
- [ ] Генерация сервисов из CSV
- [ ] Генерация специалистов из CSV
- [ ] Загрузка в DialogGauge API
- [ ] Тесты валидации данных
