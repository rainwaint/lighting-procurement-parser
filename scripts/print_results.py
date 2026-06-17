import pandas as pd
from pathlib import Path

for label in ("B", "A"):
    path = Path(f"data/output/result_{label}.xlsx")
    if not path.exists():
        continue
    df = pd.read_excel(path)
    print(f"=== RESULT {label} ===")
    for _, row in df.iterrows():
        print(f"{row['№']}. {row['Название позиции']} x{row['Требуемое кол-во']}")
        print(f"   Каталог: {str(row['Наименование из каталога'])[:80]}")
        print(f"   Коммент: {str(row['Комментарий'])[:100]}")
