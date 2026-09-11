import pytest
import urllib.request
import urllib.error
from unittest.mock import patch, MagicMock
from dialectic_ai.integrations.web.tool import WebFetchCheck

@pytest.mark.asyncio
async def test_web_fetch_initialization():
    tool = WebFetchCheck()
    assert tool.name == "fetch_url"
    assert "url" in tool.parameters()["properties"]

@pytest.mark.asyncio
@patch("urllib.request.urlopen")
async def test_web_fetch_success(mock_urlopen):
    # Mocking a successful response
    mock_response = MagicMock()
    mock_response.read.return_value = b"<html>Test content</html>"
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    tool = WebFetchCheck()
    evidence = await tool.execute(args={"url": "http://example.com"})
    
    assert evidence.success is True
    assert "Test content" in evidence.content
    mock_urlopen.assert_called_once()
    args_call, kwargs_call = mock_urlopen.call_args
    assert args_call[0].full_url == "http://example.com"
    assert kwargs_call["timeout"] == 10.0

@pytest.mark.asyncio
@patch("urllib.request.urlopen")
async def test_web_fetch_http_error(mock_urlopen):
    # Mocking an HTTP error
    mock_urlopen.side_effect = urllib.error.HTTPError(
        url="http://example.com", code=404, msg="Not Found", hdrs=None, fp=None
    )
    
    tool = WebFetchCheck()
    evidence = await tool.execute(args={"url": "http://example.com"})
    
    assert evidence.success is False
    assert "HTTP Error 404: Not Found" in evidence.error

@pytest.mark.asyncio
@patch("urllib.request.urlopen")
async def test_web_fetch_timeout(mock_urlopen):
    import socket
    # Mocking a timeout
    mock_urlopen.side_effect = socket.timeout("timed out")
    
    tool = WebFetchCheck()
    evidence = await tool.execute(args={"url": "http://example.com"})
    
    assert evidence.success is False
    assert "timed out" in evidence.error