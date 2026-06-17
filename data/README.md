# Данные для парсера

Положите файлы из тестового задания:

- `catalog/КАТАЛОГ_ред_18.03.26.xlsx` — фиксированный каталог
- `input/` — входные `.doc`, `.docx`, `.pdf`
- `output/` — сюда сохраняются результаты

Для локальной проверки без файлов задания:

```bash
python scripts/generate_demo_data.py
```

Будут созданы `catalog/catalog.xlsx` и `input/input.docx`.
