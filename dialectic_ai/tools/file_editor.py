import os

from dialectic_ai.core.decorators import dialectical_tool


@dialectical_tool(
    origin="The agent could only talk but could not save artifacts",
    contradiction="The developer had to manually copy code from the chat into files",
    resolves="Allows the agent to directly read the local file system",
)
def read_file(path: str) -> str:
    """Reads the contents of a file at the specified path."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"File reading error: {str(e)}"

@dialectical_tool(
    origin="The agent could only talk but could not save artifacts",
    contradiction="The developer had to manually copy code from the chat into files",
    resolves="Allows the agent to directly edit the local file system",
)
def write_file(path: str, content: str) -> str:
    """Writes content to a file at the specified path."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File {path} successfully saved."
    except Exception as e:
        return f"File writing error: {str(e)}"