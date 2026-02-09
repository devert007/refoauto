# Prompt 2: Валидация распарсенных данных (Spot-Check)

## Задача

После парсинга данных (Prompt 1) нужно **провести выборочную проверку** — взять ~10% записей из каждого JSON файла, заново зайти в Google Sheets и убедиться, что данные распарсены корректно.

---

## Источники для сверки

### Лист Services:
```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=12440639#gid=12440639
```

### Лист Practitioners:
```
https://docs.google.com/spreadsheets/d/1ZXYPl573sgfdRYDJj1RzPDJLPpyKpGY6vgr4NsgJSlk/edit?gid=881293577#gid=881293577
```

---

## Порядок валидации

### Шаг 1: Загрузить текущие JSON файлы

Прочитать все 4 файла:
```
data/output/categories.json
data/output/services.json
data/output/practitioners.json
data/output/service_practitioners.json
```

### Шаг 2: Структурная валидация (без обращения к Google Sheets)

Проверить **до** обращения к таблице:

#### categories.json:
- [ ] Все `id` уникальны
- [ ] Все `name_i18n.en` заполнены и уникальны
- [ ] `sort_order` последовательный
- [ ] Нет пустых имён

#### services.json:
- [ ] Все `id` уникальны
- [ ] Все `category_id` существуют в categories.json
- [ ] `name_i18n.en` заполнено для каждого сервиса
- [ ] `branches` содержит только допустимые значения: "jumeirah", "szr"
- [ ] `duration_minutes` — целое число или null
- [ ] `price_min` / `price_max` — число или null
- [ ] **НЕТ поля `practitioners`** внутри объектов сервисов

#### practitioners.json:
- [ ] Все `id` уникальны
- [ ] `name` и `name_i18n.en` совпадают
- [ ] `sex` только "male" или "female"
- [ ] `years_of_experience` — целое число или null
- [ ] `treat_children` — boolean
- [ ] `treat_children_age` — строка или null; если `treat_children` = false, то `treat_children_age` = null
- [ ] `branches` содержит только: "jumeirah", "szr", или пустой массив
- [ ] Все поля присутствуют (id, name, name_i18n, speciality, sex, languages, description_i18n, years_of_experience, primary_qualifications, secondary_qualifications, additional_qualifications, treat_children, treat_children_age, branches, is_visible_to_ai, source)

#### service_practitioners.json:
- [ ] Все `service_id` существуют в services.json
- [ ] Все `practitioner_id` существуют в practitioners.json
- [ ] Нет дублирующихся пар (service_id, practitioner_id)

---

### Шаг 3: Выборочная проверка по Google Sheets (~10%)

Открыть Google Sheets и **вручную сверить** случайно выбранные записи.

#### 3.1 Categories (проверить 3-5 категорий)

Выбрать случайные категории из `categories.json`, найти их в Google Sheets:
- [ ] Имя категории совпадает
- [ ] Нет пропущенных категорий (все уникальные категории из таблицы есть в JSON)
- [ ] Нет лишних категорий (нет категорий, которых нет в таблице)

**Пример проверки:**
```
JSON:  {"id": 5, "name_i18n": {"en": "BOTOX"}}
Sheets: Колонка Category → строка с "BOTOX" ✓
```

#### 3.2 Services (проверить 30-40 сервисов, ~10%)

Выбрать случайные сервисы из **разных категорий и branches**. Для каждого проверить:
- [ ] `name_i18n.en` совпадает с 1-й строкой ячейки Service Name
- [ ] `description_i18n.en` совпадает с остальными строками (если многострочная ячейка)
- [ ] `category_id` указывает на правильную категорию
- [ ] `duration_minutes` правильно распарсен
- [ ] `price_min` / `price_max` правильно распарсены
- [ ] `price_note_i18n` содержит "Price excludes VAT" если в Price был "+ VAT"
- [ ] `branches` правильно распарсены из колонки "Available In Branches"

**Обрати особое внимание:**
- Сервисы с многострочным Service Name (проверить разделение name/description)
- Сервисы с ценой "0" или пустой (должно быть null)
- Сервисы с duration "Individual" (должно быть null)
- Сервисы с разными branches (jumeirah only, szr only, both)

#### 3.3 Practitioners (проверить 3-5 врачей, ~10-15%)

Выбрать случайных practitioners, открыть лист Practitioners (gid=881293577):
- [ ] `name` правильный, пробелы исправлены
- [ ] `speciality` совпадает
- [ ] `sex` правильно приведён к lowercase
- [ ] `languages` правильно распарсены из слипшейся строки
- [ ] `description_i18n.en` совпадает с колонкой Description English
- [ ] `description_i18n.ru` совпадает с колонкой Description Russian (если есть)
- [ ] `years_of_experience` правильно извлечено число
- [ ] `primary_qualifications` совпадает
- [ ] `treat_children` / `treat_children_age` правильно распарсены
- [ ] `branches` правильно замаплены (Jumeirah 3 → jumeirah, Sheikh Zayed → szr)

**Обрати особое внимание:**
- Врачи со слипшимися языками (типа "ENGLISHRUSSIANUKRAINIAN")
- Врачи с "Dr.Name" (без пробела) — должно стать "Dr. Name"
- Врачи, работающие на обоих branch (два переноса строки в ячейке Branch)
- Поле treat_children: "No" → false, "13+" → true + age="13+"

#### 3.4 Service-Practitioners (проверить 10-15 связей) (ОСОБОЕ ВНИМАНИЕ)

Выбрать случайные сервисы из Google Sheets, посмотреть колонку "Doctor name":
- [ ] Все врачи из ячейки представлены как отдельные связи в service_practitioners.json
- [ ] `practitioner_id` указывает на правильного врача
- [ ] Нет пропущенных врачей (если в ячейке 3 врача — должно быть 3 записи)
- [ ] Имена правильно сопоставлены (с учётом исправления пробелов)

---

### Шаг 4: Подсчёт общих чисел

Сравнить итоговые цифры с Google Sheets:
- [ ] Количество уникальных категорий в JSON = количество уникальных значений в колонке Category
- [ ] Количество сервисов в JSON = количество строк с данными в листе Services
- [ ] Количество practitioners в JSON = количество строк с данными в листе Practitioners
- [ ] Количество связей service_practitioners разумное (каждый сервис × его врачи)

---

## Формат отчёта

После проверки выведи отчёт в формате:

```
═══════════════════════════════════════════════
  VALIDATION REPORT
═══════════════════════════════════════════════

STRUCTURAL CHECKS:
  categories.json:            ✓ PASS (35 categories, all IDs unique)
  services.json:              ✓ PASS (373 services, all category_ids valid)
  practitioners.json:         ✓ PASS (26 practitioners, all fields present)
  service_practitioners.json: ✓ PASS (1005 links, no orphans)

SPOT-CHECK vs GOOGLE SHEETS:
  Categories (5/35 checked):  ✓ ALL MATCH
  Services (40/373 checked):  ✓ 39 MATCH, 1 MISMATCH
    - ID 45: duration should be 90, got 60
  Practitioners (4/26 checked): ✓ ALL MATCH
  SP Links (15 checked):      ✓ ALL MATCH

COUNTS COMPARISON:
  Categories:  JSON=35,  Sheets=35  ✓
  Services:    JSON=373, Sheets=373 ✓
  Practitioners: JSON=26, Sheets=26 ✓

OVERALL: ✓ PASS / ✗ FAIL (with details)
═══════════════════════════════════════════════
```

---

## Что делать при обнаружении ошибок

Если найдены расхождения:

1. **Зафиксировать** — записать конкретный ID, поле, ожидаемое и фактическое значение
2. **Определить причину** — ошибка парсинга или ошибка в исходных данных
3. **Исправить JSON** — обновить конкретные записи в файлах
4. **НЕ перезапускать** весь парсинг, если ошибка точечная — исправить только конкретные записи
5. **Перезапустить** парсинг, если ошибка системная (неправильная логика парсинга)

---

## Что НЕ нужно проверять

- Не проверяй API ID (они будут присвоены позже, на шаге Sync)
- Не проверяй `sort_order` (может отличаться от порядка в таблице)
- Не проверяй `is_visible_to_ai` и `source` (это дефолтные значения)
