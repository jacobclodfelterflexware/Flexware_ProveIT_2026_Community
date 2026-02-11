"""Tests for prompt template generation."""
import sys
sys.path.insert(0, '../src')

from prompts.schema_suggestion import (
    SYSTEM_PROMPT,
    build_user_prompt,
    _format_similar_topics,
    _format_similar_messages,
    _format_tree
)


def test_system_prompt_exists():
    """System prompt should be non-empty."""
    assert len(SYSTEM_PROMPT) > 100
    assert "MQTT" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT


def test_format_similar_topics_empty():
    """Empty topics list should return message."""
    result = _format_similar_topics([])
    assert result == "No similar topics found."


def test_format_similar_topics_with_data():
    """Topics should be formatted with broker tags."""
    topics = [
        {"path": "plant/line1/temp", "broker": "curated", "score": 0.95},
        {"path": "building/sensor1", "broker": "uncurated", "score": 0.80},
    ]
    result = _format_similar_topics(topics)
    assert "CURATED" in result
    assert "uncurated" in result
    assert "plant/line1/temp" in result
    assert "0.95" in result


def test_format_similar_messages_empty():
    """Empty messages list should return message."""
    result = _format_similar_messages([])
    assert result == "No similar messages found."


def test_format_similar_messages_with_data():
    """Messages should be formatted with broker grouping."""
    messages = [
        {"topicPath": "plant/temp", "broker": "curated", "payloadText": '{"t": 21}'},
        {"topicPath": "raw/sensor", "broker": "uncurated", "payloadText": '{"val": 22}'},
    ]
    result = _format_similar_messages(messages)
    assert "Curated Broker" in result
    assert "Uncurated Broker" in result
    assert "plant/temp" in result


def test_format_tree_empty():
    """Empty tree should return message."""
    result = _format_tree({})
    assert result == "No curated topic tree available."


def test_format_tree_with_data():
    """Tree should be formatted hierarchically."""
    tree = {
        "plant": {
            "line1": {
                "sensor1": {}
            }
        }
    }
    result = _format_tree(tree)
    assert "plant" in result
    assert "line1" in result


def test_build_user_prompt():
    """Full user prompt should include all sections."""
    prompt = build_user_prompt(
        raw_topic="building/4f/temp",
        raw_payload='{"t": 21.5}',
        similar_topics=[],
        similar_messages=[],
        curated_tree={}
    )
    assert "building/4f/temp" in prompt
    assert '{"t": 21.5}' in prompt
    assert "Similar Topics" in prompt
    assert "Similar Messages" in prompt
    assert "Curated Topic Structure" in prompt


if __name__ == "__main__":
    test_system_prompt_exists()
    test_format_similar_topics_empty()
    test_format_similar_topics_with_data()
    test_format_similar_messages_empty()
    test_format_similar_messages_with_data()
    test_format_tree_empty()
    test_format_tree_with_data()
    test_build_user_prompt()
    print("All prompt tests passed!")
