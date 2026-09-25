import json
import os
import sys
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure UTF-8 output encoding across Windows consoles
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Add project root to sys.path to allow importing from dialectic_ai
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dialectic_ai.cli.config_parser import TOOL_REGISTRY
from dialectic_ai.cli.creator import generate_agent

app = FastAPI(title="Dialectic AI Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = os.path.join(PROJECT_ROOT, "dashboard_agents.json")

class Agent(BaseModel):
    id: str
    name: str
    type: str
    complexity: str
    description: str
    status: str

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None
    created_agent: Optional[Agent] = None
    logs: Optional[List[str]] = None

class ChatTurn(BaseModel):
    role: str
    content: str
    thoughts: Optional[List[str]] = None

class TokenMetrics(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_calls: int = 0
    estimated: bool = True
    exact_calls: int = 0
    estimated_calls: int = 0
    last_updated: Optional[str] = None
    by_provider: dict = {}

class ProviderInfo(BaseModel):
    id: str
    name: str
    available: bool
    description: str
    model: str
    is_default: bool = False

class ProvidersResponse(BaseModel):
    providers: List[ProviderInfo]
    current_provider: str
    metrics: TokenMetrics

class TestRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    history: Optional[List[ChatTurn]] = []

class TestResponse(BaseModel):
    result: str
    agent_thoughts: List[str] = []
    tokens: Optional[TokenMetrics] = None

class ProposalRequest(BaseModel):
    context: str

class ProposalResponse(BaseModel):
    proposal: str

class RunRequest(BaseModel):
    agent_goal: str = Field(min_length=1, max_length=10000)
    task: str = Field(min_length=1, max_length=10000)
    provider: str = "mock"

class RunResponse(BaseModel):
    run_id: str

class RunListResponse(BaseModel):
    runs: List[dict]

METRICS_FILE = os.path.join(PROJECT_ROOT, "token_metrics.json")

# In-memory store for active V2 runs
ACTIVE_RUNS = {}
_METRICS_LOCK = Lock()


def load_token_metrics() -> dict:
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Initialize from trace.jsonl if available
    calls = 0
    prompt_tok = 0
    comp_tok = 0
    trace_file = os.path.join(PROJECT_ROOT, "trace.jsonl")
    if os.path.exists(trace_file):
        try:
            with open(trace_file, "r", encoding="utf-8") as f:
                for line in f:
                    if '"generate"' in line or '"synthesize"' in line:
                        calls += 1
            prompt_tok = calls * 320
            comp_tok = calls * 180
        except Exception:
            pass
    default_metrics = {
        "prompt_tokens": prompt_tok,
        "completion_tokens": comp_tok,
        "total_tokens": prompt_tok + comp_tok,
        "total_calls": calls,
        "estimated": bool(calls),
        "exact_calls": 0,
        "estimated_calls": calls,
        "last_updated": None,
        "by_provider": {
            "gigachat": {
                "prompt_tokens": prompt_tok,
                "completion_tokens": comp_tok,
                "total_tokens": prompt_tok + comp_tok,
                "calls": calls
            }
        }
    }
    save_token_metrics(default_metrics)
    return default_metrics

def save_token_metrics(metrics: dict):
    try:
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def record_token_usage(provider: str, prompt_text: str, completion_text: str) -> dict:
    p_tok = max(1, int(len(prompt_text) / 3.5))
    c_tok = max(1, int(len(completion_text) / 3.5))
    return _record_usage(provider, p_tok, c_tok, p_tok + c_tok, exact=False)


def record_model_usage(provider: str, usage) -> dict:
    return _record_usage(provider, usage.prompt_tokens, usage.completion_tokens,
                         usage.total_tokens, exact=True)


def _record_usage(provider: str, prompt_tokens: int, completion_tokens: int,
                  total_tokens: int, *, exact: bool) -> dict:
    with _METRICS_LOCK:
        metrics = load_token_metrics()
        metrics["prompt_tokens"] = metrics.get("prompt_tokens", 0) + prompt_tokens
        metrics["completion_tokens"] = metrics.get("completion_tokens", 0) + completion_tokens
        metrics["total_tokens"] = metrics.get("total_tokens", 0) + total_tokens
        metrics["total_calls"] = metrics.get("total_calls", 0) + 1
        counter = "exact_calls" if exact else "estimated_calls"
        metrics[counter] = metrics.get(counter, 0) + 1
        metrics["estimated"] = metrics.get("exact_calls", 0) == 0 and metrics.get("estimated_calls", 0) > 0
        metrics["last_updated"] = datetime.now(timezone.utc).isoformat()
        by_prov = metrics.setdefault("by_provider", {})
        prov_stat = by_prov.setdefault(provider, {"prompt_tokens": 0, "completion_tokens": 0,
                                                   "total_tokens": 0, "calls": 0,
                                                   "exact_calls": 0, "estimated_calls": 0})
        prov_stat["prompt_tokens"] += prompt_tokens
        prov_stat["completion_tokens"] += completion_tokens
        prov_stat["total_tokens"] += total_tokens
        prov_stat["calls"] += 1
        prov_stat[counter] = prov_stat.get(counter, 0) + 1
        save_token_metrics(metrics)
        return metrics

def load_agents() -> List[Agent]:
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [Agent(**agent) for agent in data]
    except Exception:
        return []

def save_agents(agents: List[Agent]):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump([agent.model_dump() for agent in agents], f, ensure_ascii=False, indent=2)

@app.get("/api/providers", response_model=ProvidersResponse)
async def get_providers():
    from dotenv import load_dotenv
    load_dotenv()
    
    gigachat_avail = bool(os.getenv("GIGACHAT_AUTH_KEY"))
    gemini_avail = bool(os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL"))
    groq_avail = bool(os.getenv("GROQ_API_KEY") and os.getenv("GROQ_MODEL"))
    openai_avail = bool(os.getenv("OPENAI_API_KEY"))
    
    providers = [
        ProviderInfo(
            id="gigachat",
            name="Sber GigaChat",
            available=gigachat_avail,
            description="Отечественная LLM (API PERS/CORP), поддержка русского языка",
            model="GigaChat",
            is_default=gigachat_avail
        ),
        ProviderInfo(
            id="gemini",
            name="Google Gemini",
            available=gemini_avail,
            description="Google AI Flash / Pro модели с поддержкой длинного контекста",
            model=os.getenv("GEMINI_MODEL", "not configured"),
            is_default=False if gigachat_avail else gemini_avail
        ),
        ProviderInfo(
            id="groq",
            name="Groq LPU",
            available=groq_avail,
            description="Сверхбыстрый inference LPU для open-source моделей",
            model=os.getenv("GROQ_MODEL", "not configured"),
            is_default=False
        ),
        ProviderInfo(
            id="openai",
            name="OpenAI (GPT-4o)",
            available=openai_avail,
            description="GPT-4o / GPT-4o-mini от OpenAI",
            model="gpt-4o-mini",
            is_default=False
        ),
        ProviderInfo(
            id="mock",
            name="Mock LLM (Sandbox)",
            available=True,
            description="Локальный генератор без расхода токенов и ключей API",
            model="dialectical-mock-v1",
            is_default=False if (gigachat_avail or gemini_avail or groq_avail) else True
        ),
    ]
    
    current = "gigachat" if gigachat_avail else ("gemini" if gemini_avail else ("groq" if groq_avail else "mock"))
    metrics_data = load_token_metrics()
    
    return ProvidersResponse(
        providers=providers,
        current_provider=current,
        metrics=TokenMetrics(**metrics_data)
    )

# Global chat state for the wizard
chat_state = {
    "step": 0,
    "name": "",
    "goal": "",
    "tools": [],
    "llm": ""
}

@app.get("/api/agents", response_model=List[Agent])
async def get_agents():
    return load_agents()

@app.get("/api/runs")
async def get_runs():
    return {"runs": [
        {
            "id": rid,
            "goal": r.get("task"),
            "task": r.get("task"),
            "agent_goal": r.get("agent_goal"),
            "provider": r.get("provider"),
            "status": r.get("status", "pending"),
            "error": r.get("error"),
        }
        for rid, r in ACTIVE_RUNS.items()
    ]}


def _build_llm_for_provider(provider: str):
    from dialectic_ai.integrations.providers import build_llm
    llm = build_llm(provider)
    llm.set_usage_callback(provider, record_model_usage)
    return llm


async def background_run_v2(run_id: str, agent_goal: str, task: str, provider: str):
    from dialectic_ai.agent.base import DialecticalAgent
    from dialectic_ai.core.schema import AgentInput
    from dialectic_ai.engine.executor import DialecticalEngine

    try:
        tool_names = ["web_search"] if provider == "mock" else ["fetch_url", "python_executor"]
        tools = [TOOL_REGISTRY[t]() for t in tool_names]
        llm = _build_llm_for_provider(provider)

        agent = DialecticalAgent(goal=agent_goal, llm=llm, tools=tools)
        engine = DialecticalEngine(agent, max_iterations=30)

        ACTIVE_RUNS[run_id]["engine"] = engine
        ACTIVE_RUNS[run_id]["status"] = "running"

        result = await engine.run(AgentInput(user_message=task))
        ACTIVE_RUNS[run_id]["status"] = result.status
        ACTIVE_RUNS[run_id]["result"] = result.response
        ACTIVE_RUNS[run_id]["validation_mode"] = result.validation_mode
        if result.status != "completed":
            ACTIVE_RUNS[run_id]["error"] = f"{result.response} ({result.stop_reason})"
    except Exception as e:
        import traceback
        ACTIVE_RUNS[run_id]["status"] = "error"
        ACTIVE_RUNS[run_id]["error"] = f"{type(e).__name__}: {e}"
        ACTIVE_RUNS[run_id]["traceback"] = traceback.format_exc()

@app.post("/api/run")
async def start_run(req: RunRequest):
    import asyncio
    agent_goal = req.agent_goal.strip()
    task = req.task.strip()
    if not agent_goal or not task:
        raise HTTPException(status_code=422, detail="Agent goal and task must not be blank")
    casual = task.casefold().strip(" .,!?:;—-()[]{}")
    if casual in {"привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер",
                  "hello", "hi", "hey", "спасибо", "thanks", "thank you"}:
        return {
            "run_id": None,
            "kind": "conversation",
            "message": f"Привет. Я готов работать в рамках своей цели: {agent_goal}",
        }
    try:
        _build_llm_for_provider(req.provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    run_id = str(uuid.uuid4())[:8]
    ACTIVE_RUNS[run_id] = {
        "id": run_id,
        "agent_goal": agent_goal,
        "task": task,
        "provider": req.provider,
        "engine": None,
        "status": "pending",
        "error": None,
    }
    ACTIVE_RUNS[run_id]["task_handle"] = asyncio.create_task(
        background_run_v2(run_id, agent_goal, task, req.provider)
    )
    return {"run_id": run_id, "kind": "runtime"}

@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    run = ACTIVE_RUNS.get(run_id)
    if run and run.get("task_handle"):
        run["task_handle"].cancel()
        import asyncio
        try:
            await run["task_handle"]
        except asyncio.CancelledError:
            pass
    ACTIVE_RUNS.pop(run_id, None)
    return {"ok": True}

@app.get("/api/state")
async def get_state(run_id: str):
    if run_id not in ACTIVE_RUNS:
        raise HTTPException(status_code=404, detail="Run not found")

    run = ACTIVE_RUNS[run_id]
    engine = run.get("engine")
    if not engine:
        return {"snapshot": None, "status": run.get("status", "pending"), "error": run.get("error")}

    from dialectic_ai.observability.read_model import RuntimeReadModel
    return {"snapshot": RuntimeReadModel(engine.state).get_snapshot(),
            "status": run.get("status", "running"), "error": run.get("error")}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_framework(msg: ChatMessage):
    global chat_state
    user_text = msg.message.strip()
    
    # State 0: Idle
    if chat_state["step"] == 0:
        if "создай" in user_text.lower() or "хочу" in user_text.lower() or "create" in user_text.lower():
            chat_state["step"] = 1
            return ChatResponse(
                reply="Отлично! Начнем создание агента. Шаг 1: Придумайте имя для агента (например, WebResearcher):"
            )
        else:
            return ChatResponse(
                reply="Я фреймворк Dialectic AI. Попросите меня создать агента, например: 'Создай агента-аналитика данных'."
            )
            
    # State 1: Name
    elif chat_state["step"] == 1:
        chat_state["name"] = user_text if user_text else "MyAgent"
        chat_state["step"] = 2
        return ChatResponse(
            reply=f"Принято. Имя агента: {chat_state['name']}. Шаг 2: Опишите цель агента (например: 'Искать факты в интернете'):"
        )
        
    # State 2: Goal
    elif chat_state["step"] == 2:
        chat_state["goal"] = user_text if user_text else "You are a helpful AI assistant."
        chat_state["step"] = 3
        
        # Build tools list text
        available_tools = list(TOOL_REGISTRY.keys())
        tools_desc = []
        for i, t in enumerate(available_tools):
            try:
                desc = TOOL_REGISTRY[t]().description.strip().split('\n')[0]
            except Exception:
                desc = "Нет описания"
            tools_desc.append(f"[{i+1}] {t} - {desc}")
            
        tools_text = "\n".join(tools_desc)
        
        return ChatResponse(
            reply=f"Цель понятна.\nШаг 3: Выберите инструменты (номера через запятую, или 0 если без инструментов):\n{tools_text}"
        )
        
    # State 3: Tools
    elif chat_state["step"] == 3:
        available_tools = list(TOOL_REGISTRY.keys())
        selected = []
        if user_text and user_text != "0":
            for idx_str in user_text.split(","):
                try:
                    idx = int(idx_str.strip()) - 1
                    if 0 <= idx < len(available_tools):
                        selected.append(available_tools[idx])
                except Exception:
                    pass
        chat_state["tools"] = selected
        chat_state["step"] = 4
        
        return ChatResponse(
            reply=f"Инструменты: {', '.join(selected) if selected else 'Нет'}.\nШаг 4: Какую LLM использовать?\n[1] Gemini\n[2] OpenAI\n[3] Mock\n[4] Fallback\n[5] GigaChat\nВведите номер:"
        )
        
    # State 4: LLM and Generation
    elif chat_state["step"] == 4:
        llm_choice = "mock"
        if user_text == "1":
            llm_choice = "gemini"
        elif user_text == "2":
            llm_choice = "openai"
        elif user_text == "3":
            llm_choice = "mock"
        elif user_text == "4":
            llm_choice = "fallback"
        elif user_text == "5":
            llm_choice = "gigachat"
        
        chat_state["llm"] = llm_choice
        
        # Reset state early to handle future messages correctly
        name = chat_state["name"]
        goal = chat_state["goal"]
        tools = chat_state["tools"]
        llm = chat_state["llm"]
        chat_state["step"] = 0
        
        import re
        if not re.fullmatch(r"[\w -]{1,80}", name):
            raise HTTPException(status_code=422, detail="Agent name must contain only letters, numbers, spaces, underscores or hyphens")
        filename = f"{name.lower().replace(' ', '_')}.py"
        full_filepath = os.path.join(PROJECT_ROOT, filename)
        
        logs = [
            f"[System] Начат процесс сборки агента {name}...",
            f"[System] Вызов DialecticalArchitect для LLM: {llm}..."
        ]
        
        try:
            # We skip `_maybe_refine_goal`'s input prompt by using `force_refine=True` 
            # Or if it's "mock", it will auto skip.
            # generate_agent will run DialecticalArchitect, write files, and return (filepath, log)
            filepath, design_log = generate_agent(
                name=name,
                goal=goal,
                selected_tools=tools,
                llm=llm,
                is_python=True,
                filename=full_filepath,
                force_refine=True
            )
            
            logs.append(f"[AgentBuilder] Файл агента сгенерирован: {filepath.name}")
            if design_log:
                logs.append("[Architect] Диалектический лог дизайна успешно создан. Подробности:")
                for line in design_log.split('\n'):
                    if line.strip() and not line.startswith('#') and not line.startswith('*Auto-generated'):
                        # Clean up markdown syntax for the dashboard log
                        clean_line = line.replace('**', '')
                        logs.append(f"[Architect] {clean_line.strip()}")
                
            new_agent = Agent(
                id=str(uuid.uuid4())[:8],
                name=name,
                type="Generated",
                complexity="Dialectical",
                description=goal,
                status="Ready"
            )
            agents = load_agents()
            agents.append(new_agent)
            save_agents(agents)
            
            return ChatResponse(
                reply=f"Агент {name} успешно создан с помощью DialecticalArchitect! Вы можете найти его код в файле {filepath.name} и протестировать в галерее.",
                action="agent_created",
                created_agent=new_agent,
                logs=logs
            )
            
        except Exception as e:
            logs.append(f"[Error] Сборка провалилась: {str(e)}")
            return ChatResponse(
                reply=f"Произошла ошибка при генерации агента: {str(e)}",
                logs=logs
            )

@app.post("/api/agents/{agent_id}/test", response_model=TestResponse)
async def test_agent(agent_id: str, req: TestRequest):
    import asyncio
    agents = load_agents()
    agent = next((a for a in agents if a.id == agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    filename = f"{agent.name.lower().replace(' ', '_')}.py"
    full_filepath = os.path.join(PROJECT_ROOT, filename)
    
    if not os.path.exists(full_filepath):
        return TestResponse(result=f"Ошибка: файл агента {filename} не найден. Возможно, он был сохранен как JSON или удален.")
        
    try:
        sub_env = os.environ.copy()
        sub_env["PYTHONIOENCODING"] = "utf-8"
        if req.provider:
            sub_env["DIALECTIC_LLM_OVERRIDE"] = req.provider.lower().strip()
            
        process = await asyncio.create_subprocess_exec(
            sys.executable, full_filepath,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=sub_env
        )
        
        # Build user turns from history + current prompt
        user_turns = []
        for turn in (req.history or []):
            if turn.role == "user" and turn.content.strip():
                user_turns.append(turn.content.strip())
        if not user_turns or user_turns[-1] != req.prompt.strip():
            user_turns.append(req.prompt.strip())
            
        input_data = ("\n".join(user_turns) + "\nexit\n").encode('utf-8')
        stdout, _ = await process.communicate(input=input_data)
        
        output_str = stdout.decode('utf-8', errors='replace')
        
        import re
        agent_thoughts = []
        clean_response = ""
        
        # In a multi-turn session, isolate the output corresponding to the latest query
        query_sections = output_str.split("[Engine] New message:")
        target_section = query_sections[-1] if len(query_sections) > 1 else output_str
        
        lines = target_section.split('\n')
        for line in lines:
            clean = line.strip()
            if not clean:
                continue
            if (
                clean.startswith("WARNING:")
                or clean.startswith("Initializing agent")
                or clean.startswith("Done! Enter a query")
                or clean.startswith(">>")
                or clean.lower() == "exit"
                or clean.startswith("---")
                or clean == "=" * 60
                or clean == "-" * 40
            ):
                continue
            if clean.startswith("[Engine] New message:"):
                continue
            if (
                clean.startswith("[Iteration")
                or clean.startswith("[SimplestProcess]")
                or clean.startswith("[Plan]")
                or clean.startswith("[Decision]")
                or clean.startswith("[Collision]")
                or clean.startswith("[Observation]")
                or clean.startswith("[Completion]")
                or clean.startswith("[Validation]")
                or clean.startswith("[Engine]")
                or clean.startswith("[Repair]")
            ):
                agent_thoughts.append(clean)
                continue
            if clean.startswith("[Agent Response]:"):
                continue
            if clean.startswith("status="):
                resp_m = re.search(r"response=(?:'([^']*)'|\"([^\"]*)\")", clean)
                if resp_m:
                    clean_response = resp_m.group(1) or resp_m.group(2)
                contra_m = re.search(r"contradiction=(?:'([^']*)'|\"([^\"]*)\")", clean)
                if contra_m and (contra_m.group(1) or contra_m.group(2)):
                    agent_thoughts.append(f"[Contradiction] {contra_m.group(1) or contra_m.group(2)}")
                leap_m = re.search(r"leap=(?:'([^']*)'|\"([^\"]*)\")", clean)
                if leap_m and (leap_m.group(1) or leap_m.group(2)):
                    agent_thoughts.append(f"[Leap] {leap_m.group(1) or leap_m.group(2)}")
                continue
            if clean.startswith("[") and "]" in clean:
                agent_thoughts.append(clean)

        if not clean_response:
            for t in reversed(agent_thoughts):
                if t.startswith("[Completion]"):
                    clean_response = t.replace("[Completion]", "").strip()
                    break
            if not clean_response:
                clean_response = target_section.strip()

        active_provider = (req.provider or ("gigachat" if os.getenv("GIGACHAT_AUTH_KEY") else "mock")).lower().strip()
        tokens = record_token_usage(
            active_provider,
            "\n".join(user_turns),
            clean_response + "\n" + "\n".join(agent_thoughts)
        )

        return TestResponse(result=clean_response, agent_thoughts=agent_thoughts, tokens=TokenMetrics(**tokens))
        
    except Exception:
        import traceback
        tb = traceback.format_exc()
        return TestResponse(result=f"Ошибка при запуске агента:\n{tb}")

@app.post("/api/proposal", response_model=ProposalResponse)
async def get_proposal(req: ProposalRequest):
    return ProposalResponse(
        proposal="Основываясь на возможностях фреймворка, предлагаю создать агента: 'Data Analyst, умеющий писать SQL и строить графики'."
    )

if __name__ == "__main__":
    uvicorn.run("dialectic_ai.api.server:app", host="127.0.0.1", port=8123, reload=True)

