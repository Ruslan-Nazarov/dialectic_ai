import asyncio
import json
import inspect
import re
from datetime import datetime, timezone
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
        if "list_" in self.name:
            desc += "\n[!] Use this ONLY to list all items without filtering. For searching/filtering, use the corresponding search_* tool."
        return desc
        
    @property
    def category(self) -> str:
        return "Action"
        
    def parameters(self) -> dict:
        props = {}
        required = []
        for arg in getattr(self.are_tool, "args", []):
            arg_type = str(getattr(arg, "arg_type", "any")).lower()

            # 2026-09-14: container types must be checked BEFORE scalar types. A type string
            # like "list[str] | none" contains "str" as a substring, so the old order (str first)
            # classified every list[str]/list[int]/dict[str,...] argument as a plain scalar --
            # "recipients: list[str]" and "attendees: list[str]" were both reported as {"type":
            # "string"}, so the execute()-time str->[str] auto-coercion below never ran, and the
            # agent's plain-string values were rejected by the real tool on nearly every scenario
            # that sends email or adds calendar attendees.
            if "list" in arg_type: json_type = "array"
            elif "dict" in arg_type: json_type = "object"
            elif "bool" in arg_type: json_type = "boolean"
            elif "int" in arg_type: json_type = "integer"
            elif "float" in arg_type: json_type = "number"
            elif "str" in arg_type: json_type = "string"
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
            
            # Type coercion and datetime normalization
            for arg_name, arg_value in args.items():
                schema = self.parameters().get("properties", {}).get(arg_name, {})
                schema_type = schema.get("type")
                if schema_type == "array" and isinstance(arg_value, str):
                    args[arg_name] = [arg_value]
                # 2026-09-14: same class of bug as the array coercion above -- the LLM reliably
                # passes numeric/boolean arguments as strings (e.g. idx='-1' where the tool wants
                # an int), and nothing coerced those, so a plainly correct-looking call failed
                # outright. Only coerce when the string is actually parseable as that type;
                # otherwise leave it as-is so the real tool call raises its own clear type error.
                elif schema_type == "integer" and isinstance(arg_value, str):
                    try:
                        args[arg_name] = int(arg_value.strip())
                    except ValueError:
                        pass
                elif schema_type == "number" and isinstance(arg_value, str):
                    try:
                        args[arg_name] = float(arg_value.strip())
                    except ValueError:
                        pass
                elif schema_type == "boolean" and isinstance(arg_value, str):
                    if arg_value.strip().lower() in ("true", "false"):
                        args[arg_name] = arg_value.strip().lower() == "true"

                if isinstance(arg_value, str):
                    if "MM-DD" in arg_value or "YYYY" in arg_value or "HH:MM" in arg_value:
                        return Evidence(source=self.name, content=None, success=False, error="You passed a template string, replace it with actual values")
                    if re.search(r"\{\{.*?\}\}", arg_value):
                        # 2026-09-14: observed the agent passing '{{contacts}}', '{{product_id}}' etc.
                        # -- referencing another tool call's result that does not exist yet, because
                        # tool_calls listed in the SAME turn all run in parallel (see _phase_collide's
                        # asyncio.gather), not in sequence. There is no templating/variable-substitution
                        # mechanism in this framework to resolve such a placeholder.
                        return Evidence(
                            source=self.name, content=None, success=False,
                            error=(
                                f"You passed an unresolved placeholder ('{arg_value}') instead of an actual "
                                "value. Tool calls in the same turn run in PARALLEL, so a later call can never "
                                "see an earlier call's result within that same turn. Call only the tool that "
                                "produces this value now, wait for its Observation, then call this tool with "
                                "the real value in a later turn."
                            ),
                        )
                    if arg_name in ["start_datetime", "end_datetime", "ride_time", "time", "date"]:
                        if "T" in arg_value:
                            arg_value = arg_value.replace("T", " ")
                        if len(arg_value) == 10:
                            arg_value = arg_value + " 00:00:00"
                        elif len(arg_value) == 16:
                            arg_value = arg_value + ":00"
                        args[arg_name] = arg_value

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
            "EmailClientV2": ["email", "mail", "message"],
            "MessagingAppV2": ["message", "sms", "text", "chat"],
            "ReminderApp": ["remind", "reminder", "alarm"],
            "RentAFlat": ["flat", "apartment", "rent", "propert", "sqft", "sq ft", "listing", "lease"],
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
        scenario_name = getattr(scenario, "scenario_id", None) or getattr(scenario, "name", "unknown")
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
        
        # Check if dry-run based on env var
        import sys
        import os
        
        # Pre-execution logging for payload sizing
        print("\n--- LLM PAYLOAD ESTIMATION ---")
        print(f"Scenario ID: {scenario_name}")
        print("Provider: BalancingLLM (Groq, Cerebras, Gemini)")
        print(f"Total ARE tools: {total_tools_count}")
        print(f"Selected apps: {', '.join(sorted(selected_apps))}")
        print(f"Selected tools: {selected_tools_count}")
        print(f"Tool schema size: {selected_schema_size} chars (~{selected_tokens_est} tokens)")
        estimated_input = selected_tokens_est + 250
        print(f"Estimated input tokens: {estimated_input}")
        print("Max tokens: 4096")
        print("-------------------------------\n")

        if os.getenv("DRY_RUN") == "1":
            print("\n[DialecticAREAgent] Dry-run mode: skipping actual LLM generation.")
            return AgentExecutionResult(
                output="Dry run placeholder answer",
                metadata={"status": "dry-run", "llm_calls": 0, "tool_calls": 0, "iterations": 0}
            )
            
        print("\n[DialecticAREAgent] Starting REAL Execution with DialecticalEngine...")
        
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        # 3. Create Agent
        from dialectic_ai.core.llm import BalancingLLM
        from dialectic_ai.integrations.openai.llm import OpenAILLM
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        
        try:
            from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
        except ImportError:
            GigaChatLLM = None
        
        # Provider selection, 2026-09-13: a real GAIA2 run (--limit 2) showed GigaChat handles
        # long (26+ iteration) real scenarios with zero quota/rate-limit errors, while Groq's
        # free tier (8000 TPM) throws 429 the moment a scenario's context grows -- and because
        # BalancingLLM round-robins rather than prioritizing, keeping Groq in the pool means a
        # fraction of calls hit that wall regardless of GigaChat's own headroom. Cerebras and
        # OpenRouter were never confirmed to avoid the same problem, so they stay out of the
        # default pool too. Gemini's free tier is even worse for this purpose (20 requests/day
        # total, already exhausted mid-run) -- pure round-robin noise, no upside. Set
        # GAIA2_EXTRA_PROVIDERS=1 to add all of them back in for comparison.
        providers = []
        if os.getenv("GIGACHAT_AUTH_KEY") and GigaChatLLM:
            providers.append(GigaChatLLM(
                auth_key=os.getenv("GIGACHAT_AUTH_KEY"),
                model=os.getenv("GIGACHAT_MODEL", "GigaChat-Pro"),
                # 2026-09-14: repeated ControlledRepairError crashes traced to GigaChat writing a
                # long free-form prose "summary of actions" before/instead of JSON, which got cut
                # off mid-sentence at the default 4096-token completion budget -- both the original
                # and the repair attempt hit the same ceiling. Raised headroom; does not fix a model
                # ignoring "JSON only," but removes truncation as the failure mode when it does.
                max_tokens=8192,
            ))

        if os.getenv("GAIA2_EXTRA_PROVIDERS") == "1":
            if os.getenv("GEMINI_API_KEY"):
                providers.append(GeminiLLM(
                    api_key=os.getenv("GEMINI_API_KEY"),
                    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
                ))
            if os.getenv("GROQ_API_KEY"):
                providers.append(OpenAILLM(
                    api_key=os.getenv("GROQ_API_KEY"),
                    base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                    max_tokens=4096, timeout=60
                ))
            if os.getenv("OPENROUTER_API_KEY"):
                providers.append(OpenAILLM(
                    api_key=os.getenv("OPENROUTER_API_KEY"),
                    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                    model="meta-llama/llama-3.1-70b-instruct",
                    max_tokens=4096, timeout=60
                ))
                providers.append(OpenAILLM(
                    api_key=os.getenv("OPENROUTER_API_KEY"),
                    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                    model="meta-llama/llama-3.3-70b-instruct",
                    max_tokens=4096, timeout=60
                ))
            if os.getenv("CEREBRAS_API_KEY"):
                providers.append(OpenAILLM(
                    api_key=os.getenv("CEREBRAS_API_KEY"),
                    base_url=os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
                    model=os.getenv("CEREBRAS_MODEL", "llama3.1-70b"),
                    max_tokens=4096, timeout=60
                ))

        if not providers:
            raise ValueError("No working LLM providers configured in .env")
            
        llm = BalancingLLM(providers)
        asyncio.run(llm.preflight_health_check())
        
        # 2026-09-14: `scenario.environment` does not exist anywhere in ARE's Scenario API (verified
        # against are.simulation.scenarios.scenario.Scenario and ScenarioImportedFromJson) -- this
        # hasattr check was always False, so every single scenario silently fell back to this
        # hardcoded 2023-10-04 date regardless of its real simulated time. For scenario_universe_24_la711e
        # the real start_time is 2024-10-15 -- a full year off -- which made every "this week" /
        # "today" calendar query the agent issued return zero events even when hundreds existed,
        # because the agent queried entirely the wrong year. The real attribute is `scenario.start_time`
        # (a Unix timestamp float), set directly on ScenarioImportedFromJson.
        env_time = "2023-10-04 12:00:00"
        raw_start_time = getattr(scenario, "start_time", None)
        if raw_start_time is not None:
            try:
                env_time = datetime.fromtimestamp(raw_start_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
                
        goal = f"""You are an AI assistant that executes tasks strictly using the provided tools. Respond with a final answer when done.
[System] Current simulated date and time is: {env_time}
[!] Rule: Never claim a product, contact, or email was not found until you explicitly verify all fields in the tool Observation output. Do not hallucinate truncations.
[!] CRITICAL RULE: A single ambiguous sub-item must never block unrelated sub-items. If you need to ask the user a clarifying question (e.g. via AgentUserInterface__send_message_to_user), do NOT stop and do NOT generate a final response! You MUST immediately continue using tools to execute EVERY other unrelated planned action. Only provide a final response when ALL possible actions have been completed.
[!] Rule: If you are forced to stop or ask the user a question, you MUST summarize all partial progress you have already achieved."""

        agent = DialecticalAgent(
            goal=goal,
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
                "status": getattr(output, "status", "unknown"),
                "llm_calls": 0,
                "tool_calls": 0,
                "iterations": 0
            }
        )
