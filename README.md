# DialecticAI 0.1 🧠⚡

DialecticAI is an architectural framework for building predictable, philosophical, and truly cognitive Multi-Agent systems. It is built strictly on the principles of **Dialectics** (Thesis -> Antithesis -> Synthesis).

Unlike LangChain or other "Lego block" frameworks that let you write spaghetti code, **DialecticAI forces you to think**. 

![Dialectical Cycle](https://img.shields.io/badge/Architecture-Strict-red)
![Version](https://img.shields.io/badge/version-0.1-blue)
![Python](https://img.shields.io/badge/python-3.10+-success)

## Why DialecticAI? (The Problem with LangChain)
Most agent frameworks are just infinite `while` loops with tool calls. They are prone to sycophancy (LLMs agreeing with themselves), hallucinations, and endless loops. 
DialecticAI solves this on an architectural level:
1. **Generative Beginning (Rule 1)**: Every Component (Agent, Tool, Memory) must explicitly declare its dialectical *contradiction* and how it *resolves* it via the `@dialectical` decorator. If you don't, **the code will crash at runtime**. We enforce architecture at the interpreter level.
2. **Collision with Reality (Rule 3)**: Agents cannot just output "thoughts". They are forced by the `DialecticalEngine` to verify their assumptions against tools.
3. **Sublation (Synthesis)**: All conflicts are resolved into a higher-order truth.

## Features 🔥
- 🛠️ **`@dialectical_tool`**: Create strict tools from simple Python functions with auto-schema generation, just like LangChain, but with philosophical enforcement.
- 🧠 **Knowledge Graph Memory**: Stop overflowing your context window with Chat History buffers! Our `SQLiteKnowledgeGraphMemory` stores user concepts in a SQLite Database for O(1) retrieval and infinite agent lifespan.
- 🗣️ **Dialectical Debate Engine**: Multi-agent orchestration where Agent A (Thesis) argues with Agent B (Antithesis), and Agent C (Synthesis) resolves the conflict. This completely destroys LLM sycophancy.
- 📊 **Observability Dashboard (Layer 5)**: Real-time `vis.js` visualization of your Agent's Knowledge Graph and Thought Traces.

## Getting Started
```bash
git clone https://github.com/your-username/DialecticAI.git
cd DialecticAI
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Create a Tool
```python
from dialectic_ai.core.decorators import dialectical_tool

@dialectical_tool(
    origin="Agent is blind to current events",
    contradiction="LLM hallucinates facts without internet access",
    resolves="Provides live DuckDuckGo web search"
)
def search_web(query: str) -> str:
    """Searches the internet for the query."""
    return f"Search results for {query}..."
```

## Dashboard
Run the built-in observability server to watch your agent's brain in real-time:
```bash
python -m dialectic_observability.server
```
Then open `http://localhost:8000` to see the live Knowledge Graph.
