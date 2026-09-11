# Example Agent on LangChain

LangChain (together with LangGraph) is currently the most popular and widely used framework for creating AI agents in Python. This example shows a basic agent with tool calling (Tool-Calling Agent).

## How to Run This Example

1. **Install Dependencies:**
You will need the LangChain libraries and the integration with OpenAI (which is also used to work with OpenRouter/Groq via a compatible API).

```bash
pip install langchain langchain-openai python-dotenv
```

2. **Access Keys:**
The script is set up to read your `.env` file and extract `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`. Make sure the `.env` file is located in the root of the project or in this folder.

3. **Run:**
```bash
python agent.py
```

## Comparison with `dialectic_ai`
Note the `agent.py`:
- **Tools** are created very simply through the `@tool` decorator.
- There is no strict "Memory" or "Dialectical Cycles" system out of the box — the variable `{agent_scratchpad}` is used to store intermediate steps.
- The executor `AgentExecutor` plays the role of our `DialecticalEngine` — it runs the interaction loop between the LLM and tools until a final answer is obtained.