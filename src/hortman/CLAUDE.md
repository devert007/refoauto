# Hortman Clinics

<!-- Заполни этот файл контекстом для Claude Code при работе с hortman -->
<!-- Claude Code автоматически подхватывает CLAUDE.md из текущей и родительских директорий -->

## Промпт

Главный промпт: `docs/PROMPT.md`

## Полезные команды

```bash
# Запуск скриптов
python run.py hortman get_categories --all
python run.py hortman sync_with_api
python run.py hortman process_data

# Тесты
cd src/hortman && pytest tests/ -v
```
