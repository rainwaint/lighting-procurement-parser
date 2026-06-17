"""Run parser on assignment files and compare with reference outputs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from extractor.rule_extractor import extract_positions
from matcher.catalog_matcher import match_with_catalog
from output.exporter import export_results
from parser.word_parser import parse_word

DATA = ROOT / "data"
CATALOG = max((DATA / "catalog").glob("*.xlsx"), key=lambda p: p.stat().st_size)
INPUTS = {
    "A": next(p for p in (DATA / "input").glob("*.doc") if p.suffix.lower() == ".doc"),
    "B": next(p for p in (DATA / "input").glob("*.docx") if "input.docx" != p.name.lower()),
}
OUTPUT_DIR = DATA / "output"
REFERENCES = {
    "1": next(OUTPUT_DIR.glob("*1.xls")),
    "2": next(OUTPUT_DIR.glob("*2.xls")),
    "3": next(OUTPUT_DIR.glob("*3.xls")),
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = df.copy()
    mapping = {
        "Наименование": "Название позиции",
        "Кол-во": "Требуемое кол-во",
        "Наименование товара из каталога": "Наименование из каталога",
        "Наименование товара из каталога ": "Наименование из каталога",
        "Характеристики товара из каталога": "Характеристики из каталога",
        "Характеристики товара из каталога ": "Характеристики из каталога",
    }
    renamed = renamed.rename(columns=mapping)
    keep = [
        "Название позиции",
        "Требуемое кол-во",
        "Характеристики",
        "Наименование из каталога",
        "Характеристики из каталога",
        "Комментарий",
    ]
    for col in keep:
        if col not in renamed.columns:
            renamed[col] = ""
    return renamed[keep]


def compare_result(actual: pd.DataFrame, reference: pd.DataFrame, label: str) -> None:
    actual_n = normalize_columns(actual)
    ref_n = normalize_columns(reference)

    print(f"\n{'=' * 70}")
    print(f"СРАВНЕНИЕ: {label}")
    print(f"{'=' * 70}")
    print(f"Позиций — наш: {len(actual_n)}, эталон: {len(ref_n)}")

    max_rows = max(len(actual_n), len(ref_n))
    for i in range(max_rows):
        print(f"\n--- Позиция {i + 1} ---")
        if i >= len(actual_n):
            print("НАШ РЕЗУЛЬТАТ: <нет строки>")
        else:
            row = actual_n.iloc[i]
            print(f"Название: {row['Название позиции']}")
            print(f"Кол-во:   {row['Требуемое кол-во']}")
            print(f"Характер.: {str(row['Характеристики'])[:120]}")
            print(f"Каталог:  {str(row['Наименование из каталога'])[:100]}")
            print(f"Коммент.: {str(row['Комментарий'])[:120]}")

        if i >= len(ref_n):
            print("ЭТАЛОН: <нет строки>")
        else:
            row = ref_n.iloc[i]
            print("--- эталон ---")
            print(f"Название: {row['Название позиции']}")
            print(f"Кол-во:   {row['Требуемое кол-во']}")
            print(f"Характер.: {str(row['Характеристики'])[:120]}")
            print(f"Каталог:  {str(row['Наименование из каталога'])[:100]}")
            print(f"Коммент.: {str(row['Комментарий'])[:120]}")


def run_file(label: str, input_path: Path) -> pd.DataFrame:
    print(f"\n>>> Обработка файла {label}: {input_path.name}")
    text = parse_word(str(input_path))
    positions = extract_positions(text)
    print(f"Извлечено позиций: {len(positions)}")
    for pos in positions:
        print(f"  - {pos.get('name')} x{pos.get('quantity')} | {pos}")
    results = match_with_catalog(str(CATALOG), positions)
    out = DATA / "output" / f"result_{label}.xlsx"
    export_results(results, str(out))
    print(f"Сохранено: {out}")
    return results


def main():
    print(f"Каталог: {CATALOG.name}")

    result_b = run_file("B", INPUTS["B"])
    ref2 = pd.read_excel(REFERENCES["2"])
    ref3 = pd.read_excel(REFERENCES["3"])
    compare_result(result_b, ref2, "Файл Б vs Пример выходного файла 2")
    compare_result(result_b, ref3, "Файл Б vs Пример выходного файла 3")

    try:
        result_a = run_file("A", INPUTS["A"])
        ref1 = pd.read_excel(REFERENCES["1"])
        compare_result(result_a, ref1, "Файл А vs Пример выходного файла 1")
    except Exception as exc:
        print(f"\nФайл А не обработан локально: {exc}")
        print("Для .doc нужен LibreOffice (Docker: cd docker && docker compose run ...)")


if __name__ == "__main__":
    main()
