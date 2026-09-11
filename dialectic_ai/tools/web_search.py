from dialectic_ai.core.decorators import dialectical_tool

@dialectical_tool(
    origin="The agent was locked in its training data and did not know current events",
    contradiction="The LLM confidently hallucinates facts if it cannot verify reality",
    resolves="Gives the agent direct access to up-to-date information on the internet",
)
def web_search(query: str, max_results: int = 3) -> str:
    """
    Searches for information on the internet based on the given query.
    """
    return f"Search results for '{query}': Found {max_results} articles. (Mock implementation)"