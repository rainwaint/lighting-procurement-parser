import json
import os
import logging
import requests

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
Ты — специалист по извлечению данных из технических документов.
Извлеки все позиции светотехнического оборудования из текста.

Для каждой позиции укажи JSON-объект:
- name (строка): название позиции
- quantity (число): количество
- dimensions (строка): размеры (например "600x600 мм")
- power_w (число): мощность в ваттах
- color_temp_k (число): цветовая температура в кельвинах
- lumens (число): световой поток в люменах

Если характеристика не указана — используй null.

Верни ТОЛЬКО JSON-массив.

Текст:
{text}
"""

def extract_positions(text: str) -> list:
    """Извлекает позиции через OpenAI (HTTP client без httpx)"""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, using rule-based extractor")
        from .rule_based_extractor import extract_positions_rule_based
        return extract_positions_rule_based(text)
    
    try:
        # Определяем URL
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        url = f"{base_url}/chat/completions"
        
        # Формируем запрос
        prompt = PROMPT_TEMPLATE.format(text=text[:8000])
        
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 2000
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Отправляем запрос с полным отключением прокси
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            proxies={"http": None, "https": None},  # Ключевой момент!
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Очищаем маркеры кода
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            positions = json.loads(content)
            return positions if isinstance(positions, list) else [positions]
        else:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
            # Fallback на rule-based
            from .rule_based_extractor import extract_positions_rule_based
            return extract_positions_rule_based(text)
            
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        logger.info("Falling back to rule-based extractor")
        from .rule_based_extractor import extract_positions_rule_based
        return extract_positions_rule_based(text)
