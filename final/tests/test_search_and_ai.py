"""Fast regression checks for the scale/search and AI response boundaries."""

from services.ai_client import _extract_message_content, _normalize_intent
from services.product_search import _expand_terms


def test_ai_intent_is_normalized_to_safe_bounds():
    intent = _normalize_intent(
        {
            "intent_summary": "  考研数学教材  " * 20,
            "keywords": ["高数", "高数", "教材"] + list(range(20)),
            "tags": ["教材", "#教材", "#考研"],
            "min_points": "20",
            "max_points": "80",
        }
    )
    assert intent["intent_summary"] == intent["intent_summary"].strip()[:80]
    assert len(intent["keywords"]) <= 8
    assert intent["tags"] == ["#教材", "#考研"]
    assert intent["min_points"] == 20
    assert intent["max_points"] == 80


def test_ai_message_content_supports_text_blocks():
    response = {"choices": [{"message": {"content": [{"type": "text", "text": "{\"keywords\": []}"}]}}]}
    assert _extract_message_content(response) == '{"keywords": []}'


def test_search_expands_common_campus_synonyms_without_network():
    terms = _expand_terms(["高数"])
    assert "高等数学" in terms
    assert "教材" in _expand_terms(["书"])
