# Инструкция: Ручная загрузка данных в DialogGauge API

> **Этот файл НЕ для Claude Code** — это инструкция для ручного запуска скриптов.
> Выполняй шаги последовательно. Каждый шаг безопасен — по умолчанию dry-run (ничего не меняет).

---

## Предварительные требования

1. Данные распарсены (Prompt 1) и валидированы (Prompt 2)
2. ID синхронизированы с API (Prompt 3)
3. Сессия авторизации актуальна

**Проверить сессию:**

```bash
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"
python scripts/get_categories.py --categories
```

Если 401 — сессия истекла, скрипт автоматически откроет браузер.

---

## Locations (филиалы)

| Location ID | Название                | Branch в данных |
| ----------- | ----------------------- | --------------- |
| 17          | Jumeirah                | `jumeirah`      |
| 18          | SZR (Sheikh Zayed Road) | `szr` / `szr`   |

**Правила:**

- `branches: ["jumeirah"]` → только Location 17
- `branches: ["szr"]` → только Location 18
- `branches: ["jumeirah", "szr"]` → оба locations
- Categories — одинаковые для обоих locations

---

## Полный цикл загрузки

### Шаг 0: Анализ текущего состояния

```bash
python scripts/fix_locations.py --analyze
```

Покажет:

- Сколько данных сейчас на каждом location
- Сколько должно быть
- Какие действия нужны

**Это safe — ничего не меняет, только читает.**

---

### Шаг 1: Загрузка Categories на Location 18 (SZR)

> На Location 17 (Jumeirah) категории уже есть. Нужно создать те же на Location 18.

```bash
# 1. Dry-run: посмотреть что будет создано
python scripts/fix_locations.py --step1

# 2. Если всё ОК — выполнить
python scripts/fix_locations.py --step1 --execute
```

**Результат:** 35 категорий создаются на Location 18.
**Безопасность:** Идемпотентно — если категории уже есть, дубли НЕ создаются.

---

### Шаг 2: Загрузка Services на Location 18 (SZR)

> Создаёт на Location 18 сервисы с branches=["szr"] и branches=["jumeirah","szr"].

```bash
# 1. Dry-run
python scripts/fix_locations.py --step2

# 2. Выполнить
python scripts/fix_locations.py --step2 --execute
```

**Результат:** ~249 сервисов создаются на Location 18.
**Безопасность:** Проверяет по (name + category) — дубли НЕ создаются.

**ВАЖНО:** Шаг 1 (категории) ОБЯЗАТЕЛЕН перед шагом 2, иначе сервисы создадутся без категории!

---

### Шаг 3: Удаление лишних Services с Location 17

> Удаляет сервисы с branches=["szr"] с Location 17 (Jumeirah), где их быть не должно.

```bash
# 1. Dry-run: посмотреть что будет удалено
python scripts/fix_locations.py --step3

# 2. Выполнить
python scripts/fix_locations.py --step3 --execute
```

**Результат:** ~133 szr-only сервиса удаляются с Location 17.
**Безопасность:** Матчинг по (name + category) — удалит только правильные.

---

### Шаг 4: Загрузка Practitioners на оба locations

> Создаёт practitioners на правильных locations (по их branches).

```bash
# 1. Dry-run
python scripts/fix_locations.py --step4

# 2. Выполнить
python scripts/fix_locations.py --step4 --execute
```

**Результат:**

- Location 17 (Jumeirah): ~20 practitioners (jumeirah-only + both/empty)
- Location 18 (SZR): ~21 practitioner (szr-only + both/empty)

**API поля (важно знать):**

- `speciality` → `{"en": "..."}` (i18n объект, не строка!)
- Три поля qualifications объединяются в одно `qualifications_i18n`
- `treats_children` (с "s"!) вместо `treat_children`

---

### Шаг 5: Привязка Service-Practitioner связей

> Связывает сервисы с practitioners на обоих locations.

```bash
# 1. Dry-run
python scripts/fix_locations.py --step5

# 2. Выполнить
python scripts/fix_locations.py --step5 --execute
```

**Результат:** Создаёт связи service↔practitioner через `POST /locations/{loc}/practitioners/{id}/services`.
**Безопасность:** Проверяет existing links, дубли НЕ создаются.

---

### Шаг 6: Финальная проверка

```bash
python scripts/fix_locations.py --analyze
```

Сравни текущее состояние API с ожидаемым. Все цифры должны совпадать.

---

## Альтернативные скрипты (для одного location)

Если нужно загрузить только на Location 17:

### Категории:

```bash
# Dry-run
python scripts/upload_categories.py

# Выполнить
python scripts/upload_categories.py --execute
```

### Сервисы:

```bash
# Dry-run
python scripts/upload_services.py

# Выполнить
python scripts/upload_services.py --execute

# Только первые N (для теста)
python scripts/upload_services.py --execute --limit=5
```

---

## Вспомогательные команды

### Получить данные из API (только чтение):

```bash
python scripts/get_categories.py --categories     # Категории
python scripts/get_categories.py --services        # Сервисы
python scripts/get_categories.py --practitioners   # Practitioners
python scripts/get_categories.py --all             # Всё сразу
```

Результаты: `data/api/categories_api_response.json`, `data/api/services_api_response.json`, `data/api/practitioners_api_response.json`

### Создать одну тестовую категорию:

```bash
python scripts/get_categories.py --create-test --location=17 --name="Test Category"
```

---

## Порядок зависимостей

```
1. Categories    ← нет зависимостей (загружать ПЕРВЫМИ)
   ↓
2. Services      ← зависят от Categories (category_id)
   ↓
3. Practitioners ← нет зависимостей (можно параллельно с Services)
   ↓
4. Service-Practitioner links ← зависят от Services И Practitioners
```

**НИКОГДА не запускай шаг 4/5, если шаги 1-3 не завершены!**

---

## Troubleshooting

### Ошибка 401 (Unauthorized)

```bash
rm config/.dg_session.json
python scripts/get_categories.py --categories  # откроется браузер для входа
```

### Ошибка 422 (Validation Error)

Проверь формат данных:

- `name` должен быть `{"en": "Name"}`, а не строка `"Name"`
- `location_id` обязателен в body POST запроса

### Сервис создался без категории

Категория не найдена в API. Причины:

1. Категория не была загружена (шаг 1 пропущен)
2. Имя отличается (проверь пробелы, спецсимволы)

### Дубликаты в API

Скрипты идемпотентны — повторный запуск дубли НЕ создаёт. Но если дубли всё же появились:

- Удалить вручную через UI DialogGauge
- Или через API: `DELETE /locations/{loc}/services/{id}`

### Practitioners: "speciality must be object"

API ожидает `speciality: {"en": "..."}`, не plain string. Скрипт `fix_locations.py` уже обрабатывает это правильно.

---

## Краткая шпаргалка (быстрый полный цикл)

```bash
cd "/media/devert007/Windows 10 Compact/Users/devert/Desktop/работа YMA health/refoauto"

# Анализ
python scripts/fix_locations.py --analyze

# Загрузка (строго по порядку!)
python scripts/fix_locations.py --step1 --execute     # Categories → Location 18
python scripts/fix_locations.py --step2 --execute     # Services → Location 18
python scripts/fix_locations.py --step3 --execute     # Delete wrong services from Loc 17
python scripts/fix_locations.py --step4 --execute     # Practitioners → both locations
python scripts/fix_locations.py --step5 --execute     # Service-practitioner links
python scripts/fix_locations.py --step6 --execute     # Set price_type=fixed for all services

# Финальная проверка
python scripts/fix_locations.py --analyze
```
