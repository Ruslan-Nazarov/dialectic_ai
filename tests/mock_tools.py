"""
tests/mock_tools.py

Minimal, cheap tools for the local sandbox (see tests/local_runner.py).
No network calls, no real side effects — just enough behavior to exercise
the DialecticalEngine's generate -> collide -> synthesize cycle.
"""
import uuid

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ActionTool, ObservationTool


@dialectical(
    origin="Sandbox tools were real integrations (web, python) — too slow/costly for quick engine iteration",
    contradiction="Iterating on engine logic against real tools burns tokens and time on irrelevant network/API concerns",
    resolves="A trivial in-memory weather lookup with a fixed answer set, for fast local testing",
    generates="Local runner scenarios that exercise a single tool call",
    own_contradictions="Not representative of real-world tool failures (timeouts, bad schemas, etc.)",
    layer=2,
)
class MockWeatherTool(ObservationTool):
    """Returns a canned weather report for a small set of cities."""

    _WEATHER = {
        "paris": "18C, partly cloudy",
        "london": "14C, light rain",
        "oslo": "9C, clear sky",
    }

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Returns the current weather for a given city name."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Paris'."}
            },
            "required": ["city"],
        }

    async def execute(self, args: dict) -> Evidence:
        city = str(args.get("city", "")).strip().lower()
        report = self._WEATHER.get(city)
        if not report:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=f"No weather data for city '{city}'.",
            )
        return Evidence(
            id=str(uuid.uuid4()),
            source=self.name,
            content=f"Weather in {city.title()}: {report}",
            tool_name=self.name,
            success=True,
        )


@dialectical(
    origin="Sandbox needs a tool that computes something without hitting a real code executor",
    contradiction="PythonExecutor spins up a subprocess per call — too heavy for a fast debug loop",
    resolves="A trivial arithmetic evaluator restricted to +, -, *, / on numbers",
    generates="Local runner scenarios that exercise action-style tool calls",
    own_contradictions="Only supports basic arithmetic, not representative of general code execution",
    layer=2,
)
class MockCalculatorTool(ActionTool):
    """Evaluates a simple arithmetic expression, e.g. '2 + 2'."""

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "Evaluates a simple arithmetic expression made of numbers and + - * / ( )."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "e.g. '2 + 2 * 3'"}
            },
            "required": ["expression"],
        }

    async def execute(self, args: dict) -> Evidence:
        expression = str(args.get("expression", ""))
        allowed = set("0123456789+-*/(). ")
        if not expression or not set(expression) <= allowed:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error="Expression contains disallowed characters. Only digits and + - * / ( ) are allowed.",
            )
        try:
            result = eval(expression, {"__builtins__": {}}, {})
        except Exception as e:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=f"Could not evaluate expression: {e}",
            )
        return Evidence(
            id=str(uuid.uuid4()),
            source=self.name,
            content=str(result),
            tool_name=self.name,
            success=True,
        )


@dialectical(
    origin="Sandbox needs an action tool with a visible side effect, without touching real storage",
    contradiction="Real note-saving tools require a database or filesystem, adding setup overhead to the sandbox",
    resolves="An in-memory list that simulates saving a note and confirms the save",
    generates="Local runner scenarios that exercise multi-step plans (observe then act)",
    own_contradictions="Notes are lost when the process exits, unlike a real persistence layer",
    layer=2,
)
class MockNoteSaverTool(ActionTool):
    """Pretends to save a note; keeps it in memory for the lifetime of the process."""

    def __init__(self):
        self.saved_notes: list[str] = []

    @property
    def name(self) -> str:
        return "save_note"

    @property
    def description(self) -> str:
        return "Saves a text note for the user."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The note content to save."}
            },
            "required": ["text"],
        }

    async def execute(self, args: dict) -> Evidence:
        text = str(args.get("text", "")).strip()
        if not text:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error="Cannot save an empty note.",
            )
        self.saved_notes.append(text)
        return Evidence(
            id=str(uuid.uuid4()),
            source=self.name,
            content=f"Note saved: '{text}'",
            tool_name=self.name,
            success=True,
        )
