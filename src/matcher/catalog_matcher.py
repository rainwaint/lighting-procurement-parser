import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

EXACT_THRESHOLD = 0.05
CLOSE_THRESHOLD = 0.5
NAME_WEIGHT = 0.35


class CatalogMatcher:
    def __init__(self, catalog_path: str):
        self.catalog = self._load_catalog(catalog_path)
        self._parse_catalog()

    def _load_catalog(self, path: str) -> dict:
        xl = pd.ExcelFile(path)
        return {sheet: pd.read_excel(xl, sheet_name=sheet) for sheet in xl.sheet_names}

    def _find_column(self, df: pd.DataFrame, keywords: Tuple[str, ...]) -> Optional[str]:
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in keywords):
                return col
        return None

    def _parse_catalog(self):
        dim_pattern = re.compile(
            r"(?:размер|габарит)[^:]*:\s*(\d+)\s*[xх×]\s*(\d+)|(\d+)\s*[xх×]\s*(\d+)\s*м?м?",
            re.IGNORECASE,
        )
        power_pattern = re.compile(r"мощность[^:]*:\s*([\d.]+)\s*[вw]", re.IGNORECASE)
        temp_pattern = re.compile(r"(?:цветовая\s+)?температура[^:]*:\s*([\d.]+)\s*[кk]", re.IGNORECASE)
        lumens_pattern = re.compile(r"световой\s+поток[^:]*:\s*([\d.]+)\s*[лl]", re.IGNORECASE)

        for sheet, df in self.catalog.items():
            name_col = self._find_column(df, ("наимен", "назван", "name"))
            specs_col = self._find_column(df, ("характер", "spec"))
            dim_col = self._find_column(df, ("размер", "габарит", "dimension"))

            for idx, row in df.iterrows():
                specs_text = ""
                if specs_col and pd.notna(row.get(specs_col)):
                    specs_text = str(row[specs_col])
                elif name_col and pd.notna(row.get(name_col)):
                    specs_text = str(row[name_col])

                combined = specs_text
                if dim_col and pd.notna(row.get(dim_col)):
                    combined = f"{combined} {row[dim_col]}"

                for pattern, field in (
                    (power_pattern, "power_w"),
                    (temp_pattern, "color_temp_k"),
                    (lumens_pattern, "lumens"),
                ):
                    match = pattern.search(combined)
                    if match:
                        df.at[idx, field] = float(match.group(1))

                if dim_col and pd.notna(row.get(dim_col)):
                    w, h = self._parse_dims(str(row[dim_col]))
                else:
                    w, h = None, None
                if w is None:
                    match = dim_pattern.search(combined)
                    if match:
                        w = float(match.group(1) or match.group(3))
                        h = float(match.group(2) or match.group(4))
                if w is not None:
                    df.at[idx, "dimensions"] = f"{int(w)}x{int(h)} мм"

                if name_col and pd.notna(row.get(name_col)):
                    df.at[idx, "_name"] = str(row[name_col]).strip()
                if specs_col and pd.notna(row.get(specs_col)):
                    df.at[idx, "_specs"] = str(row[specs_col]).strip()
                elif specs_text:
                    df.at[idx, "_specs"] = specs_text.strip()

    def _parse_dims(self, dim_str: str) -> Tuple[Optional[float], Optional[float]]:
        if not dim_str:
            return None, None
        match = re.search(r"(\d+)\s*[xх×]\s*(\d+)", str(dim_str))
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None

    def _name_distance(self, pos_name: str, cat_name: str) -> float:
        if not pos_name or not cat_name:
            return 0.5
        ratio = SequenceMatcher(None, pos_name.lower(), cat_name.lower()).ratio()
        return 1.0 - ratio

    def _calc_distance(self, pos: Dict, row: Dict) -> float:
        distance = self._name_distance(pos.get("name", ""), row.get("_name", "")) * NAME_WEIGHT
        param_count = 0

        for field, scale in (
            ("power_w", 300),
            ("color_temp_k", 5000),
            ("lumens", 50000),
        ):
            pos_val = pos.get(field)
            row_val = row.get(field)
            if pos_val is not None and row_val is not None and not pd.isna(row_val):
                distance += abs(float(pos_val) - float(row_val)) / scale
                param_count += 1

        pos_w, pos_h = self._parse_dims(pos.get("dimensions", ""))
        cat_w, cat_h = self._parse_dims(row.get("dimensions", ""))
        if pos_w and cat_w:
            distance += (abs(pos_w - cat_w) + abs((pos_h or pos_w) - (cat_h or cat_w))) / 4000
            param_count += 1

        if param_count == 0 and not pos.get("name"):
            return float("inf")

        return distance

    def _find_best_match(self, pos: Dict) -> Tuple[Optional[pd.Series], float]:
        best_match = None
        best_dist = float("inf")

        for sheet in self.catalog:
            for _, row in self.catalog[sheet].iterrows():
                if pd.isna(row.get("_name")) and pd.isna(row.get("_specs")):
                    continue
                dist = self._calc_distance(pos, row.to_dict())
                if dist < best_dist:
                    best_dist = dist
                    best_match = row

        return best_match, best_dist

    def _build_comment(self, best_match: Optional[pd.Series], best_dist: float) -> str:
        if best_match is None or best_dist == float("inf"):
            return "Не найдено в каталоге"
        if best_dist < EXACT_THRESHOLD:
            return "Точное совпадение"
        if best_dist < CLOSE_THRESHOLD:
            return "Близкое совпадение"
        return "Точного совпадения нет; выбрана наиболее близкая позиция"

    def match(self, positions: List[Dict]) -> pd.DataFrame:
        results = []
        for pos in positions:
            best_match, best_dist = self._find_best_match(pos)

            result = {
                "Название позиции": pos.get("name", ""),
                "Требуемое кол-во": pos.get("quantity", 1),
                "Характеристики": self._format_pos(pos),
                "Наименование из каталога": "",
                "Характеристики из каталога": "",
                "Комментарий": self._build_comment(best_match, best_dist),
            }

            if best_match is not None and best_dist != float("inf"):
                result["Наименование из каталога"] = str(best_match.get("_name", "") or "")
                result["Характеристики из каталога"] = str(best_match.get("_specs", "") or "")

            results.append(result)

        return pd.DataFrame(results)

    def _format_pos(self, pos: Dict) -> str:
        parts = []
        if pos.get("dimensions"):
            parts.append(f"Размеры: {pos['dimensions']}")
        if pos.get("power_w"):
            parts.append(f"Мощность: {pos['power_w']} Вт")
        if pos.get("color_temp_k"):
            parts.append(f"Температура: {pos['color_temp_k']} К")
        if pos.get("lumens"):
            parts.append(f"Световой поток: {pos['lumens']} Лм")
        return "; ".join(parts) if parts else "Характеристики не указаны"


def match_with_catalog(catalog_path: str, positions: List[Dict]) -> pd.DataFrame:
    matcher = CatalogMatcher(catalog_path)
    return matcher.match(positions)
