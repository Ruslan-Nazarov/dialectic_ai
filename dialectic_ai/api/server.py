import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
import os
import sys

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

from dialectic_ai.cli.creator import generate_agent
from dialectic_ai.cli.config_parser import TOOL_REGISTRY

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

METRICS_FILE = os.path.join(PROJECT_ROOT, "token_metrics.json")

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
    metrics = load_token_metrics()
    p_tok = max(1, int(len(prompt_text) / 3.5))
    c_tok = max(1, int(len(completion_text) / 3.5))
    t_tok = p_tok + c_tok
    
    metrics["prompt_tokens"] = metrics.get("prompt_tokens", 0) + p_tok
    metrics["completion_tokens"] = metrics.get("completion_tokens", 0) + c_tok
    metrics["total_tokens"] = metrics.get("total_tokens", 0) + t_tok
    metrics["total_calls"] = metrics.get("total_calls", 0) + 1
    
    by_prov = metrics.setdefault("by_provider", {})
    prov_stat = by_prov.setdefault(provider, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0})
    prov_stat["prompt_tokens"] += p_tok
    prov_stat["completion_tokens"] += c_tok
    prov_stat["total_tokens"] += t_tok
    prov_stat["calls"] += 1
    
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
    gemini_avail = bool(os.getenv("GEMINI_API_KEY"))
    groq_avail = bool(os.getenv("GROQ_API_KEY"))
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
            model="gemini-1.5-flash",
            is_default=False if gigachat_avail else gemini_avail
        ),
        ProviderInfo(
            id="groq",
            name="Groq LPU",
            available=groq_avail,
            description="Сверхбыстрый inference LPU для open-source моделей",
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
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
                except:
                    pass
        chat_state["tools"] = selected
        chat_state["step"] = 4
        
        return ChatResponse(
            reply=f"Инструменты: {', '.join(selected) if selected else 'Нет'}.\nШаг 4: Какую LLM использовать?\n[1] Gemini\n[2] OpenAI\n[3] Mock\n[4] Fallback\n[5] GigaChat\nВведите номер:"
        )
        
    # State 4: LLM and Generation
    elif chat_state["step"] == 4:
        llm_choice = "mock"
        if user_text == "1": llm_choice = "gemini"
        elif user_text == "2": llm_choice = "openai"
        elif user_text == "3": llm_choice = "mock"
        elif user_text == "4": llm_choice = "fallback"
        elif user_text == "5": llm_choice = "gigachat"
        
        chat_state["llm"] = llm_choice
        
        # Reset state early to handle future messages correctly
        name = chat_state["name"]
        goal = chat_state["goal"]
        tools = chat_state["tools"]
        llm = chat_state["llm"]
        chat_state["step"] = 0
        
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
                logs.append(f"[Architect] Диалектический лог дизайна успешно создан. Подробности:")
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
                or clean.startswith("[Hypothesis]")
                or clean.startswith("[Plan]")
                or clean.startswith("[Decision]")
                or clean.startswith("[Collision]")
                or clean.startswith("[Observation]")
                or clean.startswith("[Synthesis]")
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
                if t.startswith("[Synthesis]"):
                    clean_response = t.replace("[Synthesis]", "").strip()
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
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return TestResponse(result=f"Ошибка при запуске агента:\n{tb}")

@app.post("/api/proposal", response_model=ProposalResponse)
async def get_proposal(req: ProposalRequest):
    return ProposalResponse(
        proposal="Основываясь на возможностях фреймворка, предлагаю создать агента: 'Data Analyst, умеющий писать SQL и строить графики'."
    )

if __name__ == "__main__":
    uvicorn.run("dialectic_ai.api.server:app", host="0.0.0.0", port=8123, reload=True)
