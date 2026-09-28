import json
import re
import urllib.error
import urllib.request


SYSTEM_PROMPT = """你是校园二手商品搜索助手。
你的任务是把用户的自然语言需求解析成可检索的 JSON。
只返回 JSON，不要返回 Markdown、解释或额外文字。
字段：
- intent_summary: 用一句中文概括用户想找什么
- keywords: 2 到 8 个中文关键词，适合匹配商品标题和描述
- tags: 0 到 6 个商品标签，每个标签以 # 开头
- min_points: 用户明确最低积分预算时返回整数，否则 null
- max_points: 用户明确最高积分预算时返回整数，否则 null
不要编造过细条件；不确定时保持 null 或空数组。
"""

TAG_PROMPT = """你是校园二手商品标签助手。
请根据商品标题和描述生成 3 到 6 个简短中文标签。
只返回 JSON，不要返回 Markdown、解释或额外文字。
字段：
- tags: 字符串数组，每个标签以 # 开头，适合校园二手商品搜索。
要求：
- 标签不超过 8 个字。
- 优先概括品类、用途、状态、适合人群、颜色或场景。
- 不要生成价格、联系方式、夸张营销词。
"""


def parse_product_search_intent(query_text, config):
    if not query_text:
        return None
    if not config.get("AI_ENABLED"):
        return None
    if not config.get("AI_API_KEY"):
        return None

    payload = {
        "model": config.get("AI_MODEL"),
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query_text},
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        config.get("AI_API_BASE_URL"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.get('AI_API_KEY')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.get("AI_REQUEST_TIMEOUT", 12)) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None

    content = _extract_message_content(response_data)
    if not content:
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = _parse_embedded_json(content)
        if parsed is None:
            return None

    return _normalize_intent(parsed)


def generate_product_tags(title, description, config):
    text = "\n".join(part for part in [f"标题：{title}" if title else "", f"描述：{description}" if description else ""] if part)
    if not text:
        return []
    if not config.get("AI_ENABLED") or not config.get("AI_API_KEY"):
        return []

    payload = {
        "model": config.get("AI_MODEL"),
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": TAG_PROMPT},
            {"role": "user", "content": text},
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        config.get("AI_API_BASE_URL"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.get('AI_API_KEY')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.get("AI_REQUEST_TIMEOUT", 12)) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []

    content = _extract_message_content(response_data)
    if not content:
        return []
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = _parse_embedded_json(content)
        if parsed is None:
            return []
    return _clean_text_list(parsed.get("tags"), max_items=6, with_hash=True)


def _extract_message_content(response_data):
    choices = response_data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def _parse_embedded_json(content):
    match = re.search(r"\{.*\}", content, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _normalize_intent(parsed):
    keywords = _clean_text_list(parsed.get("keywords"), max_items=8, with_hash=False)
    tags = _clean_text_list(parsed.get("tags"), max_items=6, with_hash=True)
    return {
        "intent_summary": str(parsed.get("intent_summary") or "").strip()[:80],
        "keywords": keywords,
        "tags": tags,
        "min_points": _clean_int(parsed.get("min_points")),
        "max_points": _clean_int(parsed.get("max_points")),
    }


def _clean_text_list(value, max_items, with_hash):
    if not isinstance(value, list):
        return []

    cleaned = []
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        if with_hash and not text.startswith("#"):
            text = f"#{text}"
        if not with_hash:
            text = text.lstrip("#")
        if text not in cleaned:
            cleaned.append(text[:20])
        if len(cleaned) >= max_items:
            break
    return cleaned


def _clean_int(value):
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None
