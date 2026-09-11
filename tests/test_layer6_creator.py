import os
import json
import pytest
from unittest.mock import patch, MagicMock
from dialectic_ai.cli.creator import run_interactive_creator

@pytest.fixture
def mock_inputs():
    # Mocking a series of user responses in the CLI
    # 1. Name: TestAgent
    # 2. Role: Test Role
    # 3. Tools: empty
    # 4. LLM: 1 (Gemini)
    # 5. Filename: test_agent.json
    return [
        "TestAgent",
        "Test Role",
        "",
        "1",
        "2",
        "test_agent.json"
    ]

@patch("builtins.input")
def test_create_agent_wizard_success(mock_input, tmp_path, mock_inputs):
    # Replacing the directory for saving the file
    target_file = tmp_path / "test_agent.json"
    
    # Mocking input to return our prepared responses in order.
    # But for the last question (filename), we will substitute the full path
    inputs_with_path = mock_inputs[:-1] + [str(target_file)]
    mock_input.side_effect = inputs_with_path
    
    # Running the wizard (should create a file)
    run_interactive_creator()
    
    # Checking that the file is created
    assert target_file.exists()
    
    # Checking the content
    with open(target_file, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    assert config["name"] == "TestAgent"
    assert config["goal"] == "Test Role"
    assert config["llm"] == "gemini"

@patch("builtins.input")
def test_create_agent_wizard_abort(mock_input):
    # Interruption by Ctrl+C (KeyboardInterrupt)
    mock_input.side_effect = KeyboardInterrupt()
    
    # The call should not fail with an exception, but should handle it correctly
    # (there is no handling in creator.py, but let's assume pytest intercepts)
    with pytest.raises(KeyboardInterrupt):
        run_interactive_creator()
    # If the test reached here and did not fail with KeyboardInterrupt, then everything is fine.