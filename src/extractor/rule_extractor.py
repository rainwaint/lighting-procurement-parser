import re
from typing import List


def _to_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except (TypeError, ValueError):
        return None


def _extract_specs(text: str) -> dict:
    specs = {}
    dim_match = re.search(r"(\d+)\s*[xх×]\s*(\d+)\s*м?м?", text, re.IGNORECASE)
    if dim_match:
        specs["dimensions"] = f"{dim_match.group(1)}x{dim_match.group(2)} мм"

    power_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:Вт|W|ватт)", text, re.IGNORECASE)
    if power_match:
        specs["power_w"] = _to_float(power_match.group(1))

    temp_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:К|K|кельвин)", text, re.IGNORECASE)
    if temp_match:
        specs["color_temp_k"] = _to_float(temp_match.group(1))

    lumens_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:Лм|Lm|люмен)", text, re.IGNORECASE)
    if lumens_match:
        specs["lumens"] = _to_float(lumens_match.group(1))

    return specs


def _extract_quantity(text: str) -> int:
    match = re.search(r"(\d+)\s*(?:шт\.?|штук|ед\.?|единиц)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"[—\-–]\s*(\d+)\s*$", text.strip())
    if match:
        return int(match.group(1))
    return 1


def _is_position_line(text: str) -> bool:
    if re.match(r"^(заказчик|поставщик|проект|примечан|итого|всего)\b", text, re.IGNORECASE):
        return False
    if not _looks_like_lighting(text):
        return False

    specs = _extract_specs(text)
    has_qty = bool(re.search(r"\d+\s*(?:шт\.?|штук|ед\.?)", text, re.IGNORECASE))
    is_numbered = bool(re.match(r"^\d+[\).\s-]", text))
    is_table = "|" in text and len([part for part in text.split("|") if part.strip()]) >= 3

    return is_table or (is_numbered and (has_qty or specs)) or (has_qty and specs)


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
        "dku",
        "дку",
        "аварийн",
        "комплекс",
    )
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def extract_positions(text: str) -> List[dict]:
    positions = []
    blocks = re.split(r"\n\s*\n|\r\n\s*\r\n", text)

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        for line in lines:
            if "|" in line:
                parts = [part.strip() for part in line.split("|") if part.strip()]
                if len(parts) >= 2 and _is_position_line(line):
                    name = parts[0]
                    quantity = _to_float(parts[1])
                    specs = _extract_specs(line)
                    positions.append(
                        {
                            "name": name,
                            "quantity": int(quantity) if quantity else 1,
                            **specs,
                        }
                    )
                continue

            if not _is_position_line(line):
                continue

            name = re.sub(r"^\d+[\).\s-]+", "", line).strip()
            name = re.split(r"[—\-–]\s*\d+\s*шт", name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if len(name) < 5:
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
