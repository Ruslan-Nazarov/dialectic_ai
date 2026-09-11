"""
dialectic_ai/reality/python_executor.py

DIALECTICAL DESCRIPTION:
  Origin: The tutor looked at the student's code and could mistakenly say
    "everything is correct" — he could not actually run the code and see the error.
  Contradiction: LLM evaluates the code abstractly. Real errors (IndentationError,
    ZeroDivisionError, infinite loop) are invisible without actual execution.
  How it resolves: Runs Python code in an isolated subprocess with a timeout.
    Returns stdout or stderr as CollisionResult — an objective fact of reality.
  What it leads to: The agent receives the actual output of the program and builds its response
    on facts, not assumptions. The basis for Code Review agents.
  Own contradictions: subprocess — unsafe without a sandbox. Malicious
    code can harm the system. Isolation is needed (Docker/RestrictedPython).
    Timeout does not protect against memory leaks and fork-bomb.
"""
import subprocess
import sys
import tempfile
import os
import uuid
import asyncio
import ast

def _check_ast(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"{type(e).__name__}: {e.msg} on line {e.lineno}"
        
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module]
            for name in names:
                if name and any(blocked in name for blocked in ["os", "subprocess", "socket", "ctypes"]):
                    return f"Import of module '{name}' is forbidden in sandbox."
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec", "open"]:
                return f"Function '{node.func.id}' is forbidden in sandbox."
    return None

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ActionTool


@dialectical(
    origin="The tutor could not run the student's code — he only read it with the eyes of LLM and could be mistaken",
    contradiction="LLM gives a subjective evaluation of the code. Real runtime errors are invisible without execution",
    resolves="Runs the code in an isolated subprocess. Returns real stdout/stderr — "
             "an objective fact that LLM cannot ignore",
    generates="The basis for educational agents (tutor), code review agents, CI/CD agents. "
              "The agent now works with facts, not assumptions",
    own_contradictions="subprocess without a sandbox — a potential security threat. "
                       "Docker isolation is needed for production. Timeout does not protect against fork-bomb",
    layer=2,
)
class PythonExecutor(ActionTool):
    """
    Tool for confronting reality: executing Python code.
    Returns actual output or runtime error.
    
    WARNING (DISCLAIMER): This uses a developer sandbox, not a production-level isolation.
    Do not use this for untrusted code in production until Docker/gVisor level 
    isolation is implemented.
    """

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "execute_python_code"

    @property
    def description(self) -> str:
        return "Executes arbitrary Python code in a local environment. Useful for calculations, algorithm verification, or OS access."

    @property
    def category(self) -> str:
        return "Execution & System"

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute in an isolated environment."
                }
            },
            "required": ["code"]
        }

    async def execute(self, args: dict) -> Evidence:
        code = args.get("code", "")
        if not code.strip():
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error="Empty code passed to execute_python_code",
            )

        ast_error = _check_ast(code)
        if ast_error:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=ast_error,
            )

        sandbox_preamble = """
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
except ImportError:
    pass
"""
        # Write code to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(sandbox_preamble + code)
            tmp_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
                stdout = stdout_bytes.decode('utf-8', errors='replace')
                stderr = stderr_bytes.decode('utf-8', errors='replace')
                
                if process.returncode == 0:
                    return Evidence(
                        id=str(uuid.uuid4()),
                        source=self.name,
                        content=stdout.strip(),
                        tool_name=self.name,
                        success=True,
                    )
                else:
                    return Evidence(
                        id=str(uuid.uuid4()),
                        source=self.name,
                        content=stdout.strip(),
                        tool_name=self.name,
                        success=False,
                        error=stderr.strip(),
                    )
            except asyncio.TimeoutError:
                process.kill()
                return Evidence(
                    id=str(uuid.uuid4()),
                    source=self.name,
                    content="",
                    tool_name=self.name,
                    success=False,
                    error=f"Timeout: code executed longer than {self.timeout} seconds. Possible infinite loop.",
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
        finally:
            os.unlink(tmp_path)
