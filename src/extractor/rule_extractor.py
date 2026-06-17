import re
from typing import List


def _to_float(value: str) -> float | None:
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _extract_specs(text: str) -> dict:
    specs = {}
    dim_match = re.search(
        r"(?:длина|габарит|размер)[^\d]{0,20}(\d+)\s*м?м?"
        r"|(\d+)\s*[xх×*]\s*(\d+)\s*(?:[*xх×]\s*\d+\s*)?м?м?",
        text,
        re.IGNORECASE,
    )
    if dim_match:
        if dim_match.group(1):
            specs["dimensions"] = f"{dim_match.group(1)} мм"
        elif dim_match.group(2) and dim_match.group(3):
            specs["dimensions"] = f"{dim_match.group(2)}x{dim_match.group(3)} мм"

    power_match = re.search(
        r"мощность\s*[–—\-:]?\s*(\d+(?:[.,]\d+)?)\s*(?:Вт|W|ватт)?"
        r"|(\d+(?:[.,]\d+)?)\s*(?:Вт|W)\b",
        text,
        re.IGNORECASE,
    )
    if power_match:
        specs["power_w"] = _to_float(power_match.group(1) or power_match.group(2))

    temp_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:К|K|кельвин)", text, re.IGNORECASE)
    if temp_match:
        specs["color_temp_k"] = _to_float(temp_match.group(1))

    lumens_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:Лм|Lm|люмен)", text, re.IGNORECASE)
    if lumens_match:
        specs["lumens"] = _to_float(lumens_match.group(1))

    return specs


def _extract_quantity(text: str) -> int:
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    if len(parts) >= 2 and parts[-2].lower() in {"шт", "шт.", "ед", "ед."} and parts[-1].isdigit():
        return int(parts[-1])

    match = re.search(r"(\d+)\s*(?:шт\.?|штук|ед\.?|единиц)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"[—\-–]\s*(\d+)\s*$", text.strip())
    if match:
        return int(match.group(1))
    return 1


def _looks_like_lighting(text: str) -> bool:
    keywords = (
        "светильник",
        "светодиод",
        "прожектор",
        "освещ",
        "люмен",
        "люмин",
        "опора",
        "консоль",
        "кронштейн",
        "dku",
        "дку",
        "аварийн",
        "комплекс",
        "pfl",
        "pandora",
    )
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


META_ROW_KEYWORDS = (
    "наименование закупки",
    "описание объекта закупки",
    "требования к гарантии",
    "параметры требований",
    "конкретные требования",
    "место поставки",
    "срок поставки",
)


def _is_meta_row(name: str) -> bool:
    lower = name.lower()
    return any(keyword in lower for keyword in META_ROW_KEYWORDS)


def _is_table_header(parts: List[str]) -> bool:
    joined = " ".join(parts).lower()
    return "наименование" in joined and ("кол-во" in joined or "колич" in joined or "п/п" in joined)


def _parse_table_row(parts: List[str]) -> dict | None:
    if len(parts) < 3:
        return None

    if parts[0].isdigit():
        name = parts[1]
        specs_text = " ".join(parts[2:-2] if len(parts) >= 5 else parts[2:])
        quantity = _extract_quantity(" | ".join(parts))
    else:
        name = parts[0]
        specs_text = " ".join(parts[1:-2] if len(parts) >= 4 else parts[1:])
        quantity = _extract_quantity(" | ".join(parts))

    if not _looks_like_lighting(f"{name} {specs_text}"):
        return None
    if len(name) < 3 or _is_meta_row(name):
        return None

    return {
        "name": name,
        "quantity": quantity,
        **_extract_specs(f"{name} {specs_text}"),
    }


def _is_position_line(text: str) -> bool:
    if re.match(r"^(заказчик|поставщик|проект|примечан|итого|всего)\b", text, re.IGNORECASE):
        return False
    if not _looks_like_lighting(text):
        return False

    specs = _extract_specs(text)
    has_qty = bool(re.search(r"\d+\s*(?:шт\.?|штук|ед\.?)", text, re.IGNORECASE))
    is_numbered = bool(re.match(r"^\d+[\).\s|]", text))
    is_table = "|" in text and len([part for part in text.split("|") if part.strip()]) >= 3

    return is_table or (is_numbered and (has_qty or specs)) or (has_qty and specs)


def extract_positions(text: str) -> List[dict]:
    positions = []
    blocks = re.split(r"\n\s*\n|\r\n\s*\r\n", text)

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        for line in lines:
            if "|" not in line:
                continue

            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) < 3 or _is_table_header(parts):
                continue

            parsed = _parse_table_row(parts)
            if parsed:
                positions.append(parsed)
                continue

        for line in lines:
            if "|" in line:
                continue
            if not _is_position_line(line):
                continue

            name = re.sub(r"^\d+[\).\s-]+", "", line).strip()
            name = re.split(r"[—\-–]\s*\d+\s*шт", name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if len(name) < 5 or _is_meta_row(name):
                continue

            positions.append(
                {
                    "name": name,
                    "quantity": _extract_quantity(line),
                    **_extract_specs(line),
                }
            )

    deduped = []
    seen = set()
    for pos in positions:
        key = (pos.get("name", "").lower(), pos.get("quantity"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(pos)

    return deduped
