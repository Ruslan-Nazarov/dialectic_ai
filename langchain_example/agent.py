import os
from langchain_openai import ChatOpenAI
from langchain.agents import tool, AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

# To allow the script to pick up keys from your .env file (we will need python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =====================================================================
# Step 1: Creating a Tool
# In LangChain, tools are created very easily using the @tool decorator.
# The function name, arguments, and docstring automatically become a JSON schema.
# =====================================================================
@tool
def get_weather(city: str) -> str:
    """Returns the current weather for the specified city."""
    return f"In the city {city} it is currently +22 degrees, sunny."

@tool
def search_ai_news(query: str) -> str:
    """Searches for the latest news about Artificial Intelligence on the internet based on the given query."""
    # In reality, there would be a call to Google Search API or Tavily here
    return f"Latest news for the query '{query}': A new model from OpenAI has been released that can solve Olympiad problems."

# =====================================================================
# Step 2: Initializing the Language Model (LLM)
# =====================================================================
api_key = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY"))
base_url = os.getenv("OPENROUTER_BASE_URL", "https://api.openai.com/v1")

llm = ChatOpenAI(
    model="meta-llama/llama-3.1-8b-instruct",
    api_key=api_key,
    base_url=base_url,
    temperature=0
)

# =====================================================================
# Step 3: System Prompt
# =====================================================================
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an AI journalist and web researcher (like Laos). Your task is to gather facts and news about AI using tools."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# =====================================================================
# Step 4: Assembling the Agent and Orchestrator
# In LangChain, concepts are separated: there is agent logic and an executor (AgentExecutor)
# =====================================================================
tools = [get_weather, search_ai_news]

# Creating the agent logic itself (tool selection)
agent = create_tool_calling_agent(llm, tools, prompt)

# Wrapping it in an orchestrator that runs a while loop (like DialecticalEngine)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# =====================================================================
# Launch
# =====================================================================
if __name__ == "__main__":
    print("--- LAUNCHING LANGCHAIN AGENT ---\n")
    
    user_input = "Hello! Find me the latest news about AI."
    print(f"You: {user_input}\n")
    
    # The invoke method starts the working loop
    response = agent_executor.invoke({"input": user_input})
    
    print("\n--- RESULT ---")
    print(f"Agent: {response['output']}")