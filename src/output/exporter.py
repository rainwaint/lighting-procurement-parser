from pathlib import Path

import pandas as pd


def export_results(df: pd.DataFrame, output_path: str):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_df = df.copy()
    export_df.insert(0, "№", range(1, len(export_df) + 1))

    suffix = output_path.suffix.lower()
    if suffix == ".csv":
        export_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    elif suffix == ".xlsx":
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            export_df.to_excel(writer, sheet_name="Лист1", index=False)
    elif suffix == ".xls":
        try:
            with pd.ExcelWriter(output_path, engine="xlwt") as writer:
                export_df.to_excel(writer, sheet_name="Лист1", index=False)
        except ValueError:
            xlsx_path = output_path.with_suffix(".xlsx")
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                export_df.to_excel(writer, sheet_name="Лист1", index=False)
            raise ValueError(
                f"Cannot write legacy .xls (row/column limits). Saved as {xlsx_path.name} instead."
            ) from None
    else:
        raise ValueError("Output must be .csv, .xlsx or .xls")
