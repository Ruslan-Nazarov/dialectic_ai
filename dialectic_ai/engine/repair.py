import json
from typing import Optional

class JSONRepairer:
    def __init__(self, agent):
        self.agent = agent
        
    async def repair(self, malformed_json: str) -> str:
        prompt = f"""
You are a JSON repair tool. The following text was supposed to be a valid JSON object but it is malformed (e.g. truncated, missing brackets, trailing commas, or markdown formatting).
Fix it and return ONLY the valid JSON object, without any markdown backticks or explanations.

Malformed JSON:
{malformed_json}
"""
        response = await self.agent.llm.generate([{"role": "user", "content": prompt}])
        # Strip markdown if present
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
