# Explicit re-exports so `from dialectic_ai.integrations.mcp import MCPTool` works
# and ruff F401 (imported-but-unused in __init__) is correctly suppressed.
from .tool import MCPTool as MCPTool
from .tool import load_mcp_tools as load_mcp_tools

