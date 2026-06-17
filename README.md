# Lighting Procurement Parser

Парсер закупок светотехники: извлечение позиций из Word/PDF, сопоставление с Excel-каталогом, экспорт в CSV/XLS/XLSX.

## Запуск

```bash
cp .env.example .env   # OPENAI_API_KEY=...
pip install -r requirements.txt
python scripts/generate_demo_data.py   # если нет файлов из ТЗ

python src/main.py -i data/input/input.docx -c data/catalog/catalog.xlsx -o data/output/result.xlsx
python src/main.py -i data/input/input.docx -c data/catalog/catalog.xlsx -o data/output/result.csv --no-llm
```

Docker (LibreOffice для `.doc` + PDF):

```bash
cd docker && docker compose up --build
```

Файлы из задания положите в `data/catalog/` и `data/input/` (см. `data/README.md`).

## Архитектура

1. **Парсинг** — `word_parser` (docx/doc через LibreOffice или Word COM), `pdf_parser` (pdfplumber).
2. **Извлечение позиций** — GPT-4o-mini по чанкам текста; fallback `--no-llm` (regex).
3. **Сопоставление** — по всем листам каталога: название (SequenceMatcher) + размеры, мощность, CCT, люмены; при отсутствии точного совпадения — ближайшая позиция с комментарием.
4. **Экспорт** — таблица: №, название, кол-во, характеристики, наименование/характеристики из каталога, комментарий.

## Примечание
Для использования OpenAI (опционально) нужно:

Получить API-ключ на platform.openai.com

Создать файл .env с OPENAI_API_KEY=ваш_ключ

Убедиться, что SOCKS-прокси отключён

Без OpenAI парсер работает в rule-based режиме через флаг --no-llm.

## Библиотеки

python-docx, pdfplumber, pandas, openpyxl, xlwt, openai, python-dotenv; LibreOffice (Docker) для `.doc`.

## Сделано / не сделано

**Сделано:** doc/docx/pdf, LLM + rule fallback, матчинг по 4 параметрам и названию, ближайшее совпадение, Docker, полный формат выхода.

**Не сделано:** прогон на реальных файлах ТЗ (их нет в репозитории), embeddings, unit-тесты, UI.

**Звёздочки:** PDF ✅, Docker ✅.

**Время:** ~6–7 ч (оценка с доработками).

**При большем дедлайне:** тесты на примерах ТЗ, embeddings для названий, batch-CLI, кэш LLM, валидация схемы каталога.
