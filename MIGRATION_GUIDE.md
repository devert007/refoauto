# Migration Guide: Old Structure → Multi-Client Structure

## Что изменилось

### Старая структура (до миграции)
```
refoauto/
├── scripts/
├── models/
├── tests/
├── data/
├── config/
└── docs/
```

### Новая структура (после миграции)
```
refoauto/
├── clients_config.json      # ← НОВОЕ: конфигурация клиентов
├── .env                     # ← НОВОЕ: активный клиент
├── src/
│   ├── config_manager.py    # ← НОВОЕ: менеджер конфигураций
│   ├── hortman/             # ← Все старые файлы здесь
│   │   ├── scripts/
│   │   ├── models/
│   │   ├── tests/
│   │   ├── data/
│   │   ├── config/
│   │   └── docs/
│   └── milena/              # ← НОВОЕ: для нового клиента
└── README.md                # ← Обновлен
```

## Что было автоматически перемещено

Все файлы из корня проекта были перемещены в `src/hortman/`:

- `scripts/*` → `src/hortman/scripts/`
- `models/*` → `src/hortman/models/`
- `tests/*` → `src/hortman/tests/`
- `data/*` → `src/hortman/data/`
- `config/*` → `src/hortman/config/`
- `docs/*` → `src/hortman/docs/`

## Как использовать после миграции

### Вариант 1: Работать из директории клиента (рекомендуется)

```bash
cd src/hortman

# Все старые команды работают как раньше
python scripts/get_categories.py --all
python scripts/sync_with_api.py
python scripts/process_data.py
```

### Вариант 2: Использовать run.py (в разработке)

```bash
# Из корня проекта
python run.py hortman get_categories --all
```

## Проверка после миграции

### 1. Проверить структуру

```bash
# Должны существовать:
ls src/hortman/scripts/
ls src/hortman/data/output/
ls src/milena/
```

### 2. Проверить конфигурацию

```bash
# Просмотреть конфигурацию
cat clients_config.json
cat .env
```

### 3. Протестировать config_manager

```bash
# Должен показать конфигурацию hortman
python src/config_manager.py
```

### 4. Запустить базовый скрипт

```bash
cd src/hortman
python scripts/get_categories.py --categories
```

## Добавление нового клиента (Milena)

### Шаг 1: Настроить clients_config.json

```json
{
  "clients": {
    "milena": {
      "enabled": true,
      "display_name": "Milena Clinics",
      "locations": [
        {
          "location_id": 30,  // ← Укажите ваш location_id
          "name": "Main",
          "branch": "main"
        }
      ],
      "branch_to_location": {
        "main": 30
      }
    }
  }
}
```

### Шаг 2: Установить активного клиента

В `.env`:
```
ACTIVE_CLIENT=milena
```

### Шаг 3: Скопировать скрипты (если нужно)

```bash
# Если хотите использовать те же скрипты
cp -r src/hortman/scripts/* src/milena/scripts/
cp -r src/hortman/models/* src/milena/models/
```

### Шаг 4: Добавить данные

```bash
# Положите ваш CSV в:
src/milena/data/input/raw_data.csv
```

### Шаг 5: Запустить

```bash
cd src/milena
python scripts/process_data.py
python scripts/sync_with_api.py
```

## Troubleshooting

### Проблема: "ModuleNotFoundError: No module named 'scripts'"

**Причина:** Скрипт запущен из неправильной директории.

**Решение:** Перейдите в директорию клиента:
```bash
cd src/hortman  # или src/milena
python scripts/your_script.py
```

### Проблема: "FileNotFoundError: clients_config.json not found"

**Причина:** `clients_config.json` должен быть в корне проекта.

**Решение:** Убедитесь, что файл существует:
```bash
ls clients_config.json
```

### Проблема: Данные не найдены

**Причина:** Скрипты ищут данные относительно текущей директории.

**Решение:** Запускайте из директории клиента:
```bash
cd src/hortman
python scripts/process_data.py
```

### Проблема: Старые скрипты ссылаются на старые пути

**Причина:** Некоторые скрипты могут иметь абсолютные пути к старой структуре.

**Решение:** Скрипты используют относительные пути от `Path(__file__).parent`, поэтому должны работать.

## Откат миграции (если нужно)

Если что-то пошло не так:

```bash
# Вернуть файлы в корень (НЕ рекомендуется)
mv src/hortman/scripts/* scripts/
mv src/hortman/models/* models/
mv src/hortman/tests/* tests/
mv src/hortman/data/* data/
mv src/hortman/config/* config/
mv src/hortman/docs/* docs/

# Удалить новые файлы
rm -rf src/
rm clients_config.json .env .env.example
```

## Следующие шаги

1. ✅ Проверить, что Hortman работает из `src/hortman/`
2. ✅ Настроить `clients_config.json` для Milena
3. ✅ Добавить данные для Milena в `src/milena/data/input/`
4. ✅ Запустить обработку для Milena
5. ✅ Протестировать переключение между клиентами

## Контрольный список

- [ ] `clients_config.json` создан и настроен
- [ ] `.env` файл создан с `ACTIVE_CLIENT=hortman`
- [ ] Все файлы Hortman перемещены в `src/hortman/`
- [ ] `src/milena/` структура создана
- [ ] Старые скрипты работают из `src/hortman/`
- [ ] Config manager протестирован
- [ ] Новая документация прочитана

## Дополнительная помощь

См. главный [README.md](README.md) для полной документации.
