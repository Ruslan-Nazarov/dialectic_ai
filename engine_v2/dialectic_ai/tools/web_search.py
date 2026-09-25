from dialectic_ai.core.decorators import dialectical_tool


# NOT a real search: this tool does not make a network call. It returns a fixed,
# fabricated string so the *shape* of a "search then reason over results" agent
# can be built and tested without a search API key. Any agent that uses it for
# anything beyond that is being fed made-up text that looks like a real tool
# result -- do not use it as-is for a demo that claims to fetch real information
# (use `dialectic_ai.reality.WebFetchCheck` for a real HTTP GET against a known
# URL, or implement a real search backend here, before relying on this for that).
@dialectical_tool(
    origin="The agent was locked in its training data and did not know current events",
    contradiction="The LLM confidently hallucinates facts if it cannot verify reality",
    resolves="[MOCK -- NOT YET IMPLEMENTED] Would give the agent direct access to "
             "up-to-date information on the internet; currently returns a fixed, "
             "fabricated placeholder string and makes no network call",
)
def web_search(query: str, max_results: int = 3) -> str:
    """
    [MOCK] Placeholder for internet search -- does not call any real search API.
    Returns a fixed, fabricated string. Do not mistake this output for real search
    results; see the module-level comment in tools/web_search.py before using this
    tool anywhere the actual content matters.
    """
    return f"[MOCK web_search] Search results for '{query}': Found {max_results} articles. (No real network call was made.)"
