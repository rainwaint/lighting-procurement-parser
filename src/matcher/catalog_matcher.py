import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

EXACT_THRESHOLD = 0.05
CLOSE_THRESHOLD = 0.5
NAME_WEIGHT = 0.55
TYPE_MISMATCH_PENALTY = 0.75

FIXTURE_KEYWORDS = ("светильник", "прожектор", "комплекс", "светодиод")
SUPPORT_KEYWORDS = ("опора", "кронштейн", "закладн", "накладк", "декоратив", "комплектующ")


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

    def _collect_specs_text(self, row: pd.Series, df: pd.DataFrame) -> str:
        parts = []
        for keywords in (
            ("характер", "spec"),
            ("описан", "общее"),
            ("электротех",),
            ("конструкт",),
        ):
            col = self._find_column(df, keywords)
            if col and pd.notna(row.get(col)):
                parts.append(str(row[col]))

        dim_col = self._find_column(df, ("размер", "габарит", "dimension"))
        if dim_col and pd.notna(row.get(dim_col)):
            parts.append(str(row[dim_col]))

        for dim_key in ("д", "ш", "в"):
            if dim_key in df.columns and pd.notna(row.get(dim_key)):
                parts.append(f"{dim_key}={row[dim_key]}")

        return " ".join(parts)

    def _parse_catalog(self):
        power_pattern = re.compile(
            r"мощность\s*[–—\-:/]*\s*(\d+(?:[.,]\d+)?)\s*в?т?",
            re.IGNORECASE,
        )
        temp_pattern = re.compile(
            r"(?:цветовая\s+)?температура[^0-9]{0,20}(\d+(?:[.,]\d+)?)\s*[кk]",
            re.IGNORECASE,
        )
        lumens_pattern = re.compile(
            r"(?:расчетный\s+)?световой\s+поток[^0-9]{0,20}"
            r"(\d[\d\s]*(?:[.,]\d+)?)(?:\s*[–—\-]\s*(\d[\d\s]*(?:[.,]\d+)?))?\s*(?:лм|lm)?",
            re.IGNORECASE,
        )
        dim_pattern = re.compile(
            r"(?:габарит|размер)[^0-9]{0,30}"
            r"(?:\(д\*ш\*в\)\s*)?"
            r"(\d+)\s*[*xх×]\s*(\d+)"
            r"(?:\s*[*xх×]\s*(\d+))?"
            r"|d\s*(\d+)\s*[*xх×]\s*(\d+)"
            r"|(\d+)\s*[*xх×]\s*(\d+)\s*м?м?",
            re.IGNORECASE,
        )

        for sheet, df in self.catalog.items():
            name_col = self._find_column(df, ("наимен", "назван", "name"))

            for idx, row in df.iterrows():
                combined = self._collect_specs_text(row, df)
                if name_col and pd.notna(row.get(name_col)):
                    combined = f"{row[name_col]} {combined}"

                power_match = power_pattern.search(combined)
                if power_match:
                    df.at[idx, "power_w"] = float(power_match.group(1).replace(",", ".").replace(" ", ""))

                temp_match = temp_pattern.search(combined)
                if temp_match:
                    df.at[idx, "color_temp_k"] = float(temp_match.group(1).replace(",", "."))

                lumens_match = lumens_pattern.search(combined)
                if lumens_match:
                    low = float(lumens_match.group(1).replace(",", ".").replace(" ", ""))
                    high = lumens_match.group(2)
                    df.at[idx, "lumens"] = (
                        (low + float(high.replace(",", ".").replace(" ", ""))) / 2
                        if high
                        else low
                    )

                dim_match = dim_pattern.search(combined)
                if dim_match:
                    w = dim_match.group(1) or dim_match.group(4) or dim_match.group(6)
                    h = dim_match.group(2) or dim_match.group(5) or dim_match.group(7)
                    if w and h:
                        df.at[idx, "dimensions"] = f"{int(float(w))}x{int(float(h))} мм"
                elif all(key in df.columns for key in ("д", "ш", "в")):
                    d_val, w_val, h_val = row.get("д"), row.get("ш"), row.get("в")
                    if pd.notna(d_val) and pd.notna(w_val):
                        depth = f"x{int(float(h_val))}" if pd.notna(h_val) else ""
                        df.at[idx, "dimensions"] = f"{int(float(d_val))}x{int(float(w_val))}{depth} мм"

                if name_col and pd.notna(row.get(name_col)):
                    df.at[idx, "_name"] = str(row[name_col]).strip().replace("\n", " ")
                if combined.strip():
                    df.at[idx, "_specs"] = combined.strip()

    def _parse_dims(self, dim_str: str) -> Tuple[Optional[float], Optional[float]]:
        if not dim_str:
            return None, None
        match = re.search(r"(\d+)\s*[xх×*]\s*(\d+)", str(dim_str))
        if match:
            return float(match.group(1)), float(match.group(2))
        length_match = re.search(r"(\d+)\s*м?м?", str(dim_str))
        if length_match:
            value = float(length_match.group(1))
            return value, value
        return None, None

    def _product_type(self, name: str) -> str:
        lower = str(name).lower()
        if any(keyword in lower for keyword in FIXTURE_KEYWORDS):
            return "fixture"
        if any(keyword in lower for keyword in SUPPORT_KEYWORDS):
            return "support"
        return "other"

    def _type_penalty(self, pos_name: str, cat_name: str) -> float:
        pos_type = self._product_type(pos_name)
        cat_type = self._product_type(cat_name)
        if pos_type == "fixture" and cat_type == "support":
            return TYPE_MISMATCH_PENALTY
        if pos_type == "support" and cat_type == "fixture":
            return TYPE_MISMATCH_PENALTY
        return 0.0

    def _name_distance(self, pos_name: str, cat_name: str) -> float:
        if not pos_name or not cat_name:
            return 0.5
        ratio = SequenceMatcher(None, pos_name.lower(), cat_name.lower()).ratio()
        return 1.0 - ratio

    def _calc_distance(self, pos: Dict, row: Dict) -> float:
        cat_name = str(row.get("_name", "") or "")
        distance = self._name_distance(pos.get("name", ""), cat_name) * NAME_WEIGHT
        distance += self._type_penalty(pos.get("name", ""), cat_name)
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
                cat_name = row.get("_name")
                if pd.isna(cat_name) or not str(cat_name).strip():
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
