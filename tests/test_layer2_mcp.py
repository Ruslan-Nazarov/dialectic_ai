import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dialectic_ai.integrations.mcp.tool import MCPTool

@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session

@pytest.fixture
def mock_mcp_tool_schema():
    schema = MagicMock()
    schema.name = "test_tool"
    schema.description = "A test MCP tool"
    schema.inputSchema = {"type": "object", "properties": {"arg1": {"type": "string"}}}
    return schema

@pytest.mark.asyncio
@patch("dialectic_ai.integrations.mcp.tool.MCP_AVAILABLE", True)
async def test_mcp_tool_initialization(mock_session, mock_mcp_tool_schema):
    tool = MCPTool(session=mock_session, mcp_tool=mock_mcp_tool_schema)
    assert tool.name == "test_tool"
    assert tool.description == "A test MCP tool"
    assert "arg1" in tool.parameters()["properties"]

@pytest.mark.asyncio
@patch("dialectic_ai.integrations.mcp.tool.MCP_AVAILABLE", True)
async def test_mcp_tool_execute_success(mock_session, mock_mcp_tool_schema):
    # Successful call
    mock_result = MagicMock()
    mock_result.isError = False
    
    mock_content = MagicMock()
    mock_content.text = "Success result"
    mock_result.content = [mock_content]
    
    mock_session.call_tool.return_value = mock_result
    
    tool = MCPTool(session=mock_session, mcp_tool=mock_mcp_tool_schema)
    evidence = await tool.execute({"arg1": "value1"})
    
    assert evidence.success is True
    assert evidence.content == "Success result"
    mock_session.call_tool.assert_called_once_with("test_tool", arguments={"arg1": "value1"})

@pytest.mark.asyncio
@patch("dialectic_ai.integrations.mcp.tool.MCP_AVAILABLE", True)
async def test_mcp_tool_execute_error(mock_session, mock_mcp_tool_schema):
    # Error during call (Exception from MCP server or network)
    mock_session.call_tool.side_effect = Exception("MCP connection failed")
    
    tool = MCPTool(session=mock_session, mcp_tool=mock_mcp_tool_schema)
    evidence = await tool.execute({"arg1": "value1"})
    
    assert evidence.success is False
    assert "MCP connection failed" in evidence.error