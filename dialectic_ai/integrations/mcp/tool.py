"""
dialectic_ai/integrations/mcp/tool.py

DIALECTICAL DESCRIPTION:
  Origin: The ecosystem of AI tools is fragmented. For each database,
    search engine, or API, a separate `ActionTool` class must be written.
  Contradiction: We want unlimited capabilities for the agent, but we do not want
    to maintain hundreds of integrations.
  How it resolves: Using the Model Context Protocol (MCP) standard from Anthropic.
    Allows connecting any compatible MCP server and automatically 
    converting its tools into native ActionTool of the framework.
  What it leads to: Instant access to thousands of ready-made tools (Github, 
    Postgres, Slack) without writing a single line of business logic.
  Own contradictions: MCP is a third-party protocol that adds a dependency
    and network overhead (via stdio or sse).
"""
import uuid
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ActionTool

try:
    from mcp import ClientSession
    from mcp.types import Tool as McpToolSchema
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    McpToolSchema = None


from dialectic_ai.core.dialectical import dialectical

@dialectical(
    origin="The ecosystem of AI tools is fragmented. For each database, search engine, or API, a separate `ActionTool` class must be written.",
    contradiction="We want unlimited capabilities for the agent, but we do not want to maintain hundreds of integrations.",
    resolves="Using the Model Context Protocol (MCP) standard from Anthropic. Allows connecting any compatible MCP server and automatically converting its tools into native ActionTool of the framework.",
    generates="Instant access to thousands of ready-made tools (Github, Postgres, Slack) without writing a single line of business logic.",
    own_contradictions="MCP is a third-party protocol that adds a dependency and network overhead (via stdio or sse)."
)
class MCPTool(ActionTool):
    """
    Adapter that transforms an MCP server tool 
    into a native DialecticAI tool.
    """
    def __init__(self, session: "ClientSession", mcp_tool: "McpToolSchema"):
        if not MCP_AVAILABLE:
            raise ImportError("To use MCPTool, the 'mcp' package must be installed: pip install mcp")
            
        self._session = session
        self._mcp_tool = mcp_tool

    @property
    def name(self) -> str:
        return self._mcp_tool.name

    @property
    def description(self) -> str:
        return self._mcp_tool.description or f"MCP Tool: {self._mcp_tool.name}"

    @property
    def category(self) -> str:
        return "MCP Integration"

    def parameters(self) -> dict:
        return self._mcp_tool.inputSchema

    async def execute(self, args: dict) -> Evidence:
        try:
            # Call the tool through the MCP session
            result = await self._session.call_tool(self.name, arguments=args)
            
            # Convert the MCP response (list of content) into a string
            content_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_parts.append(item.text)
                else:
                    content_parts.append(str(item))
                    
            content_str = "\n".join(content_parts)
            
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content=content_str,
                tool_name=self.name,
                success=not result.isError,
            )
        except Exception as e:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=f"MCP tool error: {e}",
            )


async def load_mcp_tools(session: "ClientSession") -> list[MCPTool]:
    """
    Helper function. Requests all available tools from the MCP server
    and returns them as a list of MCPTool adapters.
    """
    if not MCP_AVAILABLE:
        raise ImportError("To use MCPTool, the 'mcp' package must be installed: pip install mcp")
        
    tools_response = await session.list_tools()
    return [MCPTool(session, t) for t in tools_response.tools]
