# Prompt 3: Синхронизация ID с DialogGauge API

## Задача

Запустить скрипты синхронизации, которые:
1. Получают данные из DialogGauge API (categories, services, practitioners)
2. Сравнивают по имени с локальными JSON файлами
3. Присваивают правильные API ID (или новые ID для новых элементов)
4. Обновляют все ссылки (category_id, service_id, practitioner_id)

---

## ПРЕДУСЛОВИЯ

Перед запуском убедись:
- [ ] `data/output/categories.json` существует и заполнен (результат Prompt 1)
- [ ] `data/output/services.json` существует и заполнен
- [ ] `data/output/practitioners.json` существует и заполнен
- [ ] `data/output/service_practitioners.json` существует и заполнен
- [ ] Валидация пройдена (Prompt 2)
- [ ] Сессия авторизации актуальна (`config/.dg_session.json`)

---

## Порядок выполнения

### Шаг 1: Запустить sync_with_api.py

```bash
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"
python scripts/sync_with_api.py
```

**Что делает скрипт:**

1. **GET** categories, services, practitioners из API (Location 17)
2. Для каждого локального элемента:
   - Нормализует имя (`name_i18n.en` → lowercase, trim, remove special chars)
   - Ищет совпадение в API по нормализованному имени
   - **Если нашёл** → присваивает API ID
   - **Если не нашёл** → присваивает новый ID = `max_api_id + 1`
3. Обновляет `category_id` в services.json (local → API ID)
4. Обновляет `service_id` и `practitioner_id` в service_practitioners.json
5. Сохраняет обновлённые JSON файлы
6. Генерирует отчёт: `data/api/_sync_report.json`

**Флаги (если нужно синхронизировать по отдельности):**
```bash
python scripts/sync_with_api.py --categories-only
python scripts/sync_with_api.py --services-only
python scripts/sync_with_api.py --practitioners-only
```

### Шаг 2: Проверить отчёт

Прочитай `data/api/_sync_report.json` и проверь:

```json
{
  "categories": {
    "total_local": 35,
    "total_api": 35,
    "matched": 35,
    "new": 0
  },
  "services": {
    "total_local": 373,
    "total_api": 240,
    "matched": 240,
    "new": 133
  },
  "practitioners": {
    "total_local": 26,
    "total_api": 20,
    "matched": 20,
    "new": 6
  }
}
```

**На что обратить внимание:**
- `matched` — элементы, найденные в API по имени (получили API ID)
- `new` — элементы, которых нет в API (получили новые ID, нужно будет создать в API)
- Если `matched` = 0, а `total_api` > 0 — **проблема с нормализацией имён!**

### Шаг 3: Проверить обновлённые JSON файлы

После sync файлы в `data/output/` обновлены. Проверь:

- [ ] `categories.json` — ID стали API ID (трёхзначные числа типа 328, 329...)
- [ ] `services.json` — ID стали API ID, `category_id` обновлён на API category ID
- [ ] `practitioners.json` — ID стали API ID
- [ ] `service_practitioners.json` — `service_id` и `practitioner_id` обновлены

**Пример до/после:**
```
ДО sync:  service.category_id = 17 (local)  →  category "MESOTHERAPY" (local id=17)
ПОСЛЕ:    service.category_id = 328 (API)   →  category "MESOTHERAPY" (api id=328)
```

### Шаг 4: Дополнительно — получить текущие данные из API

Если нужно просмотреть что сейчас есть в API:

```bash
# Получить категории
python scripts/get_categories.py --categories

# Получить сервисы
python scripts/get_categories.py --services

# Получить practitioners
python scripts/get_categories.py --practitioners

# Всё сразу
python scripts/get_categories.py --all
```

Результаты сохраняются в `data/api/`:
- `data/api/categories_api_response.json`
- `data/api/services_api_response.json`
- `data/api/practitioners_api_response.json`

---

## Логика сопоставления

### Нормализация имени (для сравнения)

```python
def normalize_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)      # множественные пробелы → один
    name = re.sub(r'[^\w\s]', '', name)    # убрать спецсимволы
    return name
```

Примеры:
- `"BOTOX "` == `"botox"` == `"Botox!"`
- `"MesoTherapy - Face"` == `"mesotherapy  face"` == `"mesotherapy - face"`

### Зависимости между сущностями

```
Categories  →  синхронизируются ПЕРВЫМИ
    │
    │ category_id (обновляется в services)
    ▼
Services  →  синхронизируются ВТОРЫМИ
    │
    │ service_id (обновляется в service_practitioners)
    ▼
Practitioners  →  синхронизируются ТРЕТЬИМИ
    │
    │ practitioner_id (обновляется в service_practitioners)
    ▼
service_practitioners  →  обновляются АВТОМАТИЧЕСКИ (через id_mapping)
```

---

## Авторизация

- Сессия хранится в `config/.dg_session.json`
- Cookie: `dg_session`
- Срок действия: 7 дней
- При истечении — скрипт автоматически откроет браузер Playwright для Google OAuth
- Если Playwright не установлен: `pip install playwright && python -m playwright install chromium`

### Если 401 (Unauthorized):
```bash
# Удалить старую сессию
rm config/.dg_session.json
# Запустить заново — откроется браузер для входа
python scripts/sync_with_api.py
```

---

## Troubleshooting

### "No local categories/services/practitioners"
Файлы в `data/output/` пустые или отсутствуют. Сначала выполни Prompt 1 (парсинг).

### matched = 0, но total_api > 0
Проблема с нормализацией имён. Проверь:
1. Открой `data/api/categories_api_response.json` (или services/practitioners)
2. Сравни `name_i18n.en` с локальными файлами
3. Возможно различия в пробелах, регистре, спецсимволах

### Ошибка при импорте get_categories
Скрипт `sync_with_api.py` импортирует из `get_categories.py`. Запускай из корня проекта:
```bash
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"
python scripts/sync_with_api.py
```
Или добавь `scripts/` в PYTHONPATH.

---

## Чеклист после выполнения

- [ ] `python scripts/sync_with_api.py` выполнен без ошибок
- [ ] `data/api/_sync_report.json` создан и содержит статистику
- [ ] Кол-во `matched` категорий разумное (большинство должны совпасть)
- [ ] `data/output/categories.json` — ID обновлены на API ID
- [ ] `data/output/services.json` — ID и category_id обновлены
- [ ] `data/output/practitioners.json` — ID обновлены
- [ ] `data/output/service_practitioners.json` — service_id и practitioner_id обновлены
- [ ] Нет элементов с ID = 0 (это значит ошибка маппинга)
