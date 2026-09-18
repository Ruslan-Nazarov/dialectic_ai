"""
dialectic_ai/integrations/web/tool.py

Reality Check Tool: Reading web pages.
Demonstrates how easy it is to extend the framework with new capabilities.
"""
import asyncio
import urllib.error
import urllib.request
import uuid

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ObservationTool


@dialectical(
    origin="The agent must be able to interact with the internet",
    contradiction="LLM hallucinates facts if it cannot verify reality",
    resolves="Allows the agent to download raw web pages",
    generates="Access to fresh data and documentation",
    own_contradictions="May be blocked by CAPTCHA or return too much junk HTML",
    layer=2,
)
class WebFetchCheck(ObservationTool):
    """
    Tool for downloading the content of web pages (GET request).
    Allows the agent to obtain fresh information from the internet.
    """

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "Downloads the textual content from the specified URL. Use to search for information on the web."

    @property
    def category(self) -> str:
        return "Web & Networking"

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL (starts with http:// or https://)"
                }
            },
            "required": ["url"]
        }

    async def execute(self, args: dict) -> Evidence:
        url = args.get("url", "")
        if not url:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error="URL not specified",
            )
        
        def _fetch():
            # Fixing encoding for Cyrillic in URL
            parts = list(urllib.parse.urlsplit(url))
            parts[2] = urllib.parse.quote(parts[2])
            parts[3] = urllib.parse.quote(parts[3], safe="=&")
            safe_url = urllib.parse.urlunsplit(parts)

            req = urllib.request.Request(
                safe_url, 
                headers={'User-Agent': 'Mozilla/5.0 DialecticAI/1.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read().decode('utf-8', errors='ignore')
                return content[:5000] + ("\n...[TRUNCATED]" if len(content) > 5000 else "")

        try:
            content = await asyncio.to_thread(_fetch)
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content=content,
                tool_name=self.name,
                success=True,
            )
        except Exception as e:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=str(e),
            )