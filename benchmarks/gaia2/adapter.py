import asyncio
import json
import inspect
from dialectic_ai.core.schema import AgentInput, Evidence
from are.simulation.agents.are_simulation_agent import AgentExecutionResult
from dialectic_ai.core.tool import ActionTool
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.integrations.openai.llm import OpenAILLM
from are.simulation.tool_utils import AppTool

from dialectic_ai.core.dialectical import dialectical

@dialectical(
    origin="Integration with ARE simulation environment",
    contradiction="ARE tools have their own schema and execution model, DialecticEngine expects Dialectical Tool",
    resolves="Wraps AppTool into ActionTool to make it compatible with DialecticAI framework",
    generates="Allows DialecticAI agents to execute tools within GAIA2 sandbox",
    own_contradictions="Execution errors from ARE might need special parsing so they don't break agent flow",
    layer=2
)
class AREToolWrapper(ActionTool):
    def __init__(self, are_tool: AppTool):
        self.are_tool = are_tool
        
    @property
    def name(self) -> str:
        return self.are_tool.name
        
    @property
    def description(self) -> str:
        desc = self.are_tool.function_description or ""
        # Sometimes return type is important to know for the LLM
        ret = getattr(self.are_tool, 'return_type', None)
        if ret:
            desc += f"\nReturns: {ret}"
        return desc
        
    @property
    def category(self) -> str:
        return "Action"
        
    def parameters(self) -> dict:
        props = {}
        required = []
        for arg in getattr(self.are_tool, "args", []):
            arg_type = str(getattr(arg, "arg_type", "any")).lower()
            
            if "str" in arg_type: json_type = "string"
            elif "int" in arg_type: json_type = "integer"
            elif "float" in arg_type: json_type = "number"
            elif "bool" in arg_type: json_type = "boolean"
            elif "list" in arg_type: json_type = "array"
            elif "dict" in arg_type: json_type = "object"
            else: json_type = "string" # fallback
            
            prop = {"type": json_type}
            if getattr(arg, "description", None):
                prop["description"] = arg.description
            if getattr(arg, "has_default", False):
                prop["default"] = arg.default
            else:
                required.append(arg.name)
                
            if json_type == "array":
                prop["items"] = {"type": "string"}
                
            props[arg.name] = prop
            
        return {
            "type": "object",
            "properties": props,
            "required": required
        }
        
    async def execute(self, args: dict) -> Evidence:
        try:
            print(f"[AREToolWrapper] Executing {self.name} with {args}")
            # Real execution
            result = self.are_tool(**args)
            return Evidence(
                source=self.name,
                content=result if isinstance(result, (str, dict, list, int, float, bool)) else str(result),
                success=True
            )
        except Exception as e:
            print(f"[AREToolWrapper] Error in {self.name}: {e}")
            return Evidence(
                source=self.name,
                content=None,
                success=False,
                error=str(e)
            )


class ToolSelector:
    def __init__(self):
        self.app_keywords = {
            "Emails": ["email", "mail", "message"],
            "Contacts": ["contact", "people", "person"],
            "InternalContacts": ["contact", "people", "person"],
            "Shopping": ["buy", "purchase", "shop", "order", "product", "price"],
            "Calendar": ["calendar", "schedule", "event", "appointment", "date"],
            "Files": ["file", "document", "folder", "read", "write", "pdf"],
            "Messages": ["message", "sms", "text", "chat"],
            "Chats": ["chat", "message"],
            "RentAFlat": ["flat", "apartment", "rent"],
            "City": ["city", "weather", "crime"],
            "Cabs": ["cab", "taxi", "ride", "uber"],
            "SystemApp": []
        }
        
    def select(self, tools: list[AREToolWrapper], task_text: str) -> tuple[list[AREToolWrapper], set[str]]:
        task_lower = task_text.lower()
        selected_apps = {"AgentUserInterface"} # Always include user interaction tools
        
        for app, keywords in self.app_keywords.items():
            if any(kw in task_lower for kw in keywords):
                selected_apps.add(app)
                
        selected_tools = []
        for tool in tools:
            app_name = tool.name.split("__")[0] if "__" in tool.name else tool.name
            if app_name in selected_apps:
                selected_tools.append(tool)
                
        return selected_tools, selected_apps


class DialecticAREAgent:
    def __init__(self):
        self.max_iterations = 30
        self.tool_selection = "relevant" # "all" or "relevant"
        
    def run_scenario(self, scenario, notification_system, initial_agent_logs=None) -> AgentExecutionResult:
        scenario_name = getattr(scenario, "name", "unknown")
        print(f"\n[DialecticAREAgent] Connected to ARE Scenario: {scenario_name}")
        
        # 1. Extract Task from first USER event
        task_text = "No task found"
        if hasattr(scenario, "events"):
            # The initial task is usually sent to the agent via AgentUserInterface
            for ev in scenario.events:
                # Check the event itself
                action = getattr(ev, "action", None)
                if action and "send_message_to_agent" in str(getattr(action, "function", "")):
                    args = getattr(action, "args", {})
                    if "content" in args:
                        task_text = args["content"]
                        break
                
                # Check successors
                for succ in getattr(ev, "successors", []):
                    action = getattr(succ, "action", None)
                    if action and "send_message_to_agent" in str(getattr(action, "function", "")):
                        args = getattr(action, "args", {})
                        if "content" in args:
                            task_text = args["content"]
                            break
                if task_text != "No task found":
                    break
                        
        print(f"\n[DialecticAREAgent] Extracted Task:\n{task_text}\n")
        
        # 2. Extract tools and apply ToolSelector
        adapted_tools = []
        if hasattr(scenario, "apps"):
            for app in scenario.apps:
                for tool in app.get_tools():
                    adapted_tools.append(AREToolWrapper(tool))
                    
        total_tools_count = len(adapted_tools)
        total_schema_size = len(json.dumps([t.parameters() for t in adapted_tools]))
        total_tokens_est = total_schema_size // 4
        
        if self.tool_selection == "relevant":
            selector = ToolSelector()
            selected_tools, selected_apps = selector.select(adapted_tools, task_text)
        else:
            selected_tools = adapted_tools
            selected_apps = set(t.name.split("__")[0] if "__" in t.name else t.name for t in adapted_tools)
            
        selected_tools_count = len(selected_tools)
        excluded_tools_count = total_tools_count - selected_tools_count
        selected_schema_size = len(json.dumps([t.parameters() for t in selected_tools]))
        selected_tokens_est = selected_schema_size // 4
        
        print("\n--- Tool Selection Diagnostics ---")
        print(f"ARE tools available: {total_tools_count}")
        print(f"Selected apps: {', '.join(sorted(selected_apps))}")
        print(f"Selected tools: {selected_tools_count}")
        print(f"Excluded tools: {excluded_tools_count}")
        print(f"Schema size (all): {total_schema_size} characters (~{total_tokens_est} tokens)")
        print(f"Schema size (selected): {selected_schema_size} characters (~{selected_tokens_est} tokens)")
        print("----------------------------------\n")
        print("Selected tools names:")
        for t in selected_tools:
            print(f" - {t.name}")
        
        # Check if dry-run based on sys.argv
        import sys
        if "--dry-run" in sys.argv:
            print("\n[DialecticAREAgent] Dry-run mode: skipping actual LLM generation.")
            return AgentExecutionResult(
                output="Dry run placeholder answer",
                metadata={"llm_calls": 0, "tool_calls": 0, "iterations": 0}
            )
            
        print("\n[DialecticAREAgent] Starting REAL Execution with DialecticalEngine...")
        
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        # 3. Create Agent
        llm = OpenAILLM(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv("OPENROUTER_BASE_URL"),
            model="meta-llama/llama-3.1-70b-instruct"
        )
        agent = DialecticalAgent(
            goal="You are an AI assistant that executes tasks strictly using the provided tools. Respond with a final answer when done.",
            llm=llm,
            tools=selected_tools
        )
        
        # 4. Create Engine
        engine = DialecticalEngine(
            agent=agent,
            max_iterations=self.max_iterations
        )
        
        # 5. Run Engine synchronously
        user_input = AgentInput(user_message=task_text, session_id=scenario_name)
        output = asyncio.run(engine.run(user_input))
        
        print("\n[DialecticAREAgent] Final Answer:", output.response)
        
        # In DialecticAI 2.0, the logger writes to trace.jsonl directly and doesn't hold an in-memory dictionary.
        # We can approximate stats differently if needed, or just return default zeros for the benchmark format.
        return AgentExecutionResult(
            output=output.response,
            metadata={
                "llm_calls": 0,
                "tool_calls": 0,
                "iterations": 0
            }
        )
