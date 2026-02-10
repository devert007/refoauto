# Prompt для Claude Code: полный pipeline от парсинга до загрузки

Выполняй шаги СТРОГО по порядку. Каждый шаг — прочитай указанный файл и выполни ВСЕ инструкции в нём максимально строго. Не переходи к следующему шагу, пока текущий не завершён без ошибок.

---

## Шаг 1. Парсинг

Прочитай `docs/PROMPT_1_PARSE_DATA.md` и выполни все инструкции в нём.

Результат: 4 JSON файла в `data/output/` (categories, services, practitioners, service_practitioners).
Пройди чеклист в конце файла — все пункты должны быть выполнены.

---

## Шаг 2. Валидация

Прочитай `docs/PROMPT_2_VALIDATE_DATA.md` и выполни все инструкции в нём.

Результат: отчёт VALIDATION REPORT. Если FAIL — вернись к Шагу 1, исправь, повтори.

---

## Шаг 3. Тесты (СТОП если fail)

Запусти ВСЕ три локальных теста:

```bash
pytest tests/test_each_service.py -v
pytest tests/test_data_integrity.py -v
pytest tests/test_random_sample.py -v -s
```

Что проверяют:
- `test_each_service.py` — атомарные тесты КАЖДОГО сервиса: category, price, duration, branches, кол-во practitioners. Печатает описания из JSON и CSV.
- `test_data_integrity.py` — целостность JSON: unique IDs, FK, branches, нормализация имён, step5 dry-run.
- `test_random_sample.py` — случайная выборка 10-15% practitioners: service count, service names, branches vs CSV.

**Если хотя бы 1 тест FAIL → СТОП. Исправь данные. Перезапусти тесты. Не переходи дальше.**

---

## Шаг 4. Синхронизация ID

Прочитай `docs/PROMPT_3_SYNC_IDS.md` и выполни все инструкции в нём.

Результат: JSON файлы в `data/output/` обновлены — ID теперь соответствуют API.
Проверь `data/api/_sync_report.json` — matched > 0, нет элементов с ID=0.

---

## Шаг 5. Загрузка на API

Прочитай `docs/PROMPT_4_MANUAL_UPLOAD.md` и выполни все инструкции в нём.

Строго по порядку: step1 → step2 → step3 → step4 → step5.
Каждый шаг сначала dry-run, проверить вывод, потом --execute.

---

## Шаг 6. API тесты (СТОП если fail)

```bash
pytest tests/test_api_validation.py -v -s
pytest tests/test_content_stats.py -v -s
```

Что проверяют:
- `test_api_validation.py` — practitioner service counts, service name matching на API.
- `test_content_stats.py` — content-stats endpoint: duplicate_names=0, missing_duration=0, missing_price=0, empty_category=0, no_services=0.

**Если FAIL → исправь (API не поддерживает PATCH, только delete+recreate). Перезапусти.**

---

## Допустимые исключения (НЕ ошибки)

Эти issues ожидаемы и НЕ являются ошибками:

| Issue | Jumeirah | SZR | Причина |
|-------|----------|-----|---------|
| `no_practitioners` | 7 сервисов | 4 сервиса | В CSV нет Doctor name |
| `missing_description` | ~236 | ~248 | В CSV нет описаний |
| `too_many_services` >100 | 3 врача | 1 врач | Реально много сервисов |
| `too_many_services` >50 | +1 врач | +4 врача | Реально много сервисов |
| Cross-branch links в JSON | Локально | — | Фильтруются при upload |

## Doctor aliases (CSV → JSON)

В CSV другие написания имён. Учитывай при проверках:

| JSON | CSV |
|------|-----|
| Danielle April Stephen | + Danielle Stephen |
| Dr. Mohsen Soofian | Dr Mohsen |
| Dr. Karem Harb | + Dr Karem Harb, Dr Karem Harb (private area only) |
| Dr. Tatiana Kuznechenkova | Dr.Tatiana Kuznechenkova |
| Dr. Lyn Al Alamy AlHassany | Dr.Lyn Al Alamy AlHassany |
| Dr. Sarah Mohamed | Dr.Sarah Mohamed |
| Dr. Zainab Mohi | Dr Zainab Mohi |
| Dr. Sezgin Cagatay | Dr Sezgin Cagatay |
| Dr. Kinan Bonni | Dr Kinan Bonni |
| Dr. Nataliya Sanytska | + Dr Nataliya Sanytska |

## Если API сессия истекла (401)

```bash
rm config/.dg_session.json
python scripts/get_categories.py --categories
```
