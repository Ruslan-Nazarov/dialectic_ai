"""
dialectic_ai/core/decorators.py

DIALECTICAL DESCRIPTION:
  Origin: Creating the tool required writing a cumbersome class (boiler-plate),
    which discouraged developers (as we saw in comparison with LangChain).
  Contradiction: We want the convenience of LangChain (@tool), but do not want to lose our strict
    dialectical discipline (Rule 1).
  How it resolves: Combines function parsing through inspect (like in LangChain) and strict
    dialectical justification (like in DialecticAI) in one decorator @dialectical_tool.
  What it leads to: A sharp acceleration in the development of agents and the creation of an ecosystem (dialectic_ai.tools).
  Own contradictions: Hidden "magic" of class creation under the hood. Supports
    only basic types of arguments.
"""
import inspect
from typing import Callable, Type

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import Tool


def dialectical_tool(
    origin: str,
    contradiction: str,
    resolves: str,
    generates: str = "Data for synthesis",
    own_contradictions: str = "The tool may return a runtime error or empty data",
):
    """
    A smart decorator that transforms a regular Python function into a full-fledged `Tool` of the framework.
    Automatically parses the docstring and type annotations (type hints) into a JSON schema for LLM,
    strictly requiring the description of dialectical metadata (Rule 1).
    """
    def wrapper(func: Callable) -> Type[Tool]:
        sig = inspect.signature(func)
        properties = {}
        required = []
        for name, param in sig.parameters.items():
            # NOTE: only basic types supported; list[str] / Optional etc. fall back to "string".
            # See CODE_REVIEW.md [SMELL] core/decorators.py for the full caveat.
            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is bool:
                param_type = "boolean"
            elif param.annotation is float:
                param_type = "number"
                
            properties[name] = {"type": param_type, "description": f"Parameter {name}"}
            if param.default == inspect.Parameter.empty:
                required.append(name)
                
        schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }
        
        class DynamicTool(Tool):
            @property
            def name(self) -> str:
                return func.__name__
                
            @property
            def description(self) -> str:
                return func.__doc__ or f"Tool {func.__name__}"
                
            @property
            def category(self) -> str:
                return "Action"
                
            async def execute(self, args: dict) -> Evidence:
                try:
                    if inspect.iscoroutinefunction(func):
                        result = await func(**args)
                    else:
                        result = func(**args)
                    return Evidence(content=str(result), source=self.name, tool_name=self.name)
                except Exception as e:
                    return Evidence(content=str(e), source=self.name, tool_name=self.name, success=False, error=str(e))
                    
            def parameters(self) -> dict:
                return schema
                
        # Apply the original dialectical decorator
        DynamicTool = dialectical(
            origin=origin,
            contradiction=contradiction,
            resolves=resolves,
            generates=generates,
            own_contradictions=own_contradictions,
            layer=2
        )(DynamicTool)
        
        DynamicTool.__name__ = f"{func.__name__.capitalize()}Tool"
        return DynamicTool

    return wrapper
