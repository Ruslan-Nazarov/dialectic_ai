"""The control arm for engine comparisons: the same model, role and tools in a plain
native function-calling loop (call tools until the model answers in text), with no
dialectical protocol, judge or roadmap. Anything the engine adds is measured against this."""
import json
from dataclasses import dataclass, field


@dataclass
class BaselineRun:
    response: str = ""
    completed: bool = False
    stop_reason: str = ""
    tool_calls: list = field(default_factory=list)      # [{"name", "args", "success", "content"}]

    def successful_calls(self, tool_name=None):
        return [c for c in self.tool_calls if c["success"] and (tool_name is None or c["name"] == tool_name)]


def _tool_schema(tool) -> dict:
    return {"type": "function", "function": {"name": tool.name, "description": tool.description,
                                             "parameters": tool.parameters()}}


async def run_baseline(llm, role: str, task: str, tools: list, max_steps: int = 12) -> BaselineRun:
    """`llm` must support native tool calls through generate_result (OpenAI-compatible)."""
    registry = {t.name: t for t in tools}
    schemas = [_tool_schema(t) for t in tools]
    messages = [{"role": "system", "content": role}, {"role": "user", "content": task}]
    run = BaselineRun()
    for _ in range(max_steps):
        result = await llm.generate_result(messages, tools=schemas)
        if not result.tool_calls:
            run.response, run.completed = result.text or "", True
            return run
        messages.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
            for c in result.tool_calls]})
        for call in result.tool_calls:
            tool = registry.get(call.name)
            if tool is None:
                success, content = False, f"Unknown tool {call.name}"
            else:
                try:
                    evidence = await tool.execute(call.arguments)
                    success, content = evidence.success, evidence.content if evidence.success else evidence.error
                except Exception as exc:
                    success, content = False, f"{type(exc).__name__}: {exc}"
            run.tool_calls.append({"name": call.name, "args": call.arguments, "success": success, "content": content})
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)})
    run.stop_reason = "max_steps"
    return run
