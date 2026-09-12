import os
import sys
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.engine.parser import parse_llm_response, ParseError, JSON_REPAIR_AVAILABLE

def test_parse_valid_json():
    raw = '{"decision": "test", "response": "hello", "tool_calls": []}'
    parsed = parse_llm_response(raw)
    assert parsed["decision"] == "test"
    assert parsed["response"] == "hello"

def test_parse_markdown_json():
    raw = '''```json
{
  "decision": "markdown",
  "response": "block"
}
```'''
    parsed = parse_llm_response(raw)
    assert parsed["decision"] == "markdown"
    assert parsed["response"] == "block"

def test_parse_unclean_prefix_suffix():
    raw = '''Some text before
{
  "decision": "prefix",
  "response": "suffix"
}
Some text after'''
    parsed = parse_llm_response(raw)
    assert parsed["decision"] == "prefix"

@pytest.mark.skipif(not JSON_REPAIR_AVAILABLE, reason="json_repair not installed")
def test_parse_broken_json():
    # Missing quotes around key and missing comma
    raw = '''{
      decision: "broken"
      "response": "fixed"
    }'''
    parsed = parse_llm_response(raw)
    assert parsed["decision"] == "broken"
    assert parsed["response"] == "fixed"

def test_parse_failure():
    raw = "Just a normal text without any json."
    with pytest.raises(ParseError):
        parse_llm_response(raw)
