"""
dialectic_ai/core/llm.py

DIALECTICAL DESCRIPTION:
  Origin: The agent's code directly depends on a specific API (OpenAI,
    Gemini). Changing the provider requires rewriting the entire agent logic.
  Contradiction: The agent should think about its task, not the details of HTTP
    requests. A tight coupling to the provider kills portability.
  How it resolves: Introduces the BaseLLM abstraction with a single method generate().
    MockLLM allows developing and testing the entire framework without API keys
    and real costs — confronting reality at the architectural level.
  What it leads to: DialecticalEngine operates only on BaseLLM — it doesn't care
    whether it's Gemini or local Llama. Adding a new provider = one new class.
  Its own contradictions: The abstraction hides the unique capabilities of
    providers (function calling, vision, embeddings). Interface extensions
    or specialized subclasses are needed.
"""
import json
import re
import time
from abc import ABC, abstractmethod

from dialectic_ai.core.dialectical import DialecticalObject, dialectical
from dialectic_ai.core.schema import ModelResult, ModelToolCall, ModelUsage
from typing import Optional


class BaseLLM(ABC, DialecticalObject):
    """Abstraction over any language model."""
    supports_native_tool_calling: bool = False

    def set_usage_callback(self, provider: str, callback) -> None:
        """Attach an optional per-response usage sink without coupling providers to the API."""
        self._usage_provider = provider
        self._usage_callback = callback

    def _record_usage(self, usage: Optional[dict]) -> Optional[ModelUsage]:
        if not usage:
            return None
        parsed = ModelUsage(
            prompt_tokens=int(usage.get("prompt_tokens", usage.get("promptTokenCount", 0)) or 0),
            completion_tokens=int(usage.get("completion_tokens", usage.get("candidatesTokenCount", 0)) or 0),
            total_tokens=int(usage.get("total_tokens", usage.get("totalTokenCount", 0)) or 0),
        )
        if not parsed.total_tokens:
            parsed.total_tokens = parsed.prompt_tokens + parsed.completion_tokens
        callback = getattr(self, "_usage_callback", None)
        if callback:
            callback(getattr(self, "_usage_provider", self.__class__.__name__.lower()), parsed)
        return parsed

    @abstractmethod
    async def generate(self, messages: list[dict], tools: Optional[list[dict]] = None) -> str:
        """
        Generates a response based on the message history.

        Args:
            messages: A list of messages in the format [{"role": "...", "content": "..."}]

        Returns:
            String — the raw response from the model (usually JSON for our agent)
        """
        ...

    async def generate_result(self, messages: list[dict], tools: Optional[list[dict]] = None) -> ModelResult:
        """
        Generates a structured result from the language model, including text and native tool calls.
        
        Args:
            messages: A list of messages in the format [{"role": "...", "content": "..."}]
            tools: Tools to expose to the LLM.
        
        Returns:
            ModelResult
        """
        text = await self.generate(messages, tools)
        return ModelResult(text=text)


_UUID = r"[0-9a-fA-F-]{36}"


@dialectical(
    origin="Need to write and test the framework before obtaining a real API key",
    contradiction="Without LLM, no tests can be run. Circular dependency.",
    resolves="Returns predefined responses. Allows simulating any scenario "
             "of the agent's operation, including errors and edge cases",
    generates="Ability to write a complete test of the engine (engine.py) before connecting a real LLM",
    own_contradictions="Mock does not reflect the real behavior of LLM — hallucinations, delays, "
                       "token limits. Tests on Mock can give a false sense of reliability",
    layer=0,
)
class MockLLM(BaseLLM):
    """
    Test LLM with predefined responses.
    Used during development and in unit tests.

    When no `responses` are given, it drives an "autopilot": a deterministic
    walk through the full dialectical cycle (Simplest -> Development ->
    Action/Observation -> Opposite -> Contradiction -> Leap -> Complete),
    read straight out of the rendered Runtime V2 state summary in the prompt.
    This lets the dashboard demonstrate the whole mechanism with zero API
    keys and zero token cost.
    """

    # The autopilot reads the RUNTIME_JSON snapshot, which prompts omit for real models.
    reads_runtime_json = True

    def __init__(self, responses: Optional[list[str]] = None):
        """
        Args:
            responses: Queue of responses. Returned one at a time for each call.
                       After exhaustion — returns the last response.
                       If omitted, the autopilot described above is used instead.
        """
        self._responses = responses
        self._index = 0
        self._autopilot_step = 0

    async def generate(self, messages: list[dict], tools: Optional[list[dict]] = None) -> str:
        self._record_usage({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        if self._responses:
            response = self._responses[min(self._index, len(self._responses) - 1)]
            self._index += 1
            return response

        prompt = messages[-1]["content"] if messages else ""
        proposal = self._autopilot_proposal(prompt)
        return json.dumps(proposal, ensure_ascii=False)

    async def generate_result(self, messages: list[dict], tools: Optional[list[dict]] = None) -> ModelResult:
        text = await self.generate(messages, tools)
        try:
            args = json.loads(text)
        except json.JSONDecodeError:
            args = None
        tool_calls = [ModelToolCall(name="submit_proposal", arguments=args)] if args else []
        return ModelResult(text=text, tool_calls=tool_calls)

    @staticmethod
    def _section(prompt: str, header: str) -> str:
        """Returns just the text of one '<Header>:\\n...' block, up to the next blank-line-separated block."""
        idx = prompt.find(header)
        if idx == -1:
            return ""
        rest = prompt[idx + len(header):]
        end = rest.find("\n\n")
        return rest if end == -1 else rest[:end]

    def _autopilot_proposal(self, prompt: str) -> dict:
        """Explicit simulation of the protocol, not a solution of the user's task."""
        try:
            data = json.loads(prompt.split("RUNTIME_JSON:\n", 1)[1].split("\nEND_RUNTIME_JSON", 1)[0])
        except (IndexError, json.JSONDecodeError):
            return {}
        def move(name, payload):
            return {"move_type": name, "payload": payload,
                    "why_this_move_now": "[SIMULATION] deterministic protocol example",
                    "expected_goal_contribution": "[SIMULATION] exercise structure, not task quality"}
        def develop(pid):
            return move("DEVELOP_PROCESS", {"source_process_id": pid, "emergent_content": "[SIMULATION] Concrete development",
                "potential_containment": "[SIMULATION] source potential", "emergence": "[SIMULATION] emergence",
                "concretization": "[SIMULATION] more concrete", "new_content": "[SIMULATION] new determination"})
        designations = data['designations']
        candidates = [d for d in designations if d['role'] == 'candidate_simplest']
        simplest = next((d for d in designations if d['role'] == 'simplest'), None)
        if candidates:
            return move('ASSESS_SIMPLEST', {'candidate_simplest_id': candidates[-1]['id'], 'approved': True})
        if not simplest:
            return move('PROPOSE_SIMPLEST', {'content': '[SIMULATION] Task-derived simplest process'})
        development = data['development']
        sdev = next((r for r in development if r['source_process_id'] == simplest['process_id']), None)
        if not sdev:
            return develop(simplest['process_id'])
        opposite = next((d for d in designations if d['role'] == 'opposite'), None)
        if not opposite:
            return move('DESIGNATE_OPPOSITE', {'simplest_id': simplest['id'], 'context_id': sdev['id'],
                 'content': '[SIMULATION] Independently developing process',
                 'caught_from': '[SIMULATION] A determination found in the simplest\'s development',
                 'justification': '[SIMULATION] That determination points to this process'})
        odev = next((r for r in development if r['source_process_id'] == opposite['process_id']), None)
        if not odev:
            return develop(opposite['process_id'])
        if not data['contradictions']:
            return move('ESTABLISH_CONTRADICTION', {'simplest_id': simplest['id'], 'opposite_id': opposite['id'],
                'simplest_dev_ref_ids': [sdev['id']], 'opposite_dev_ref_ids': [odev['id']],
                'unity_justification': '[SIMULATION] Unity of both developments',
                'developing_unity_description': '[SIMULATION] Their developing unity'})
        if not data['resolutions']:
            return move('PROPOSE_LEAP', {'contradiction_id': data['contradictions'][0]['id'],
                'opposite_acting_on_simplest': '[SIMULATION] The opposite acts on the simplest',
                'resolution_content': '[SIMULATION] Resolution from the unity of both processes', 'resolution_outcome': 'replacement'})
        resolution = data['resolutions'][-1]
        if data['phase'] == 'planning':
            return move('BEGIN_EXECUTION', {'simplest_id': simplest['id'],
                'contradiction_ids': [data['contradictions'][0]['id']], 'resolution_ids': [resolution['id']],
                'execution_process_ids': [sdev['emergent_process_id'], resolution['resolution_process_id']]})
        roadmap = data['roadmaps'][-1]
        data['actions'] = [a for a in data['actions'] if a['roadmap_id'] == roadmap['id']]
        action_ids = {a['id'] for a in data['actions']}
        data['observations'] = [o for o in data['observations'] if o['action_id'] in action_ids]
        data['practice'] = [pa for pa in data['practice'] if pa['action_id'] in action_ids]
        if not data['actions']:
            return move('PROPOSE_ACTION', {'tool_name': 'web_search', 'args': {'query': '[SIMULATION] example'},
                'origin_ref': {'type': 'Process', 'id': roadmap['execution_process_ids'][0]},
                'why_now': 'Exercise practice', 'purpose': 'Simulate observation', 'expectation': 'Explicit mock output',
                'relation_to_goal': 'Test protocol only'})
        if not data['practice']:
            obs = data['observations'][-1]
            return move('ASSESS_PRACTICE', {'action_id': obs['action_id'], 'observation_id': obs['id'],
                'expected_actual_relation': 'confirmed' if obs['success'] else 'inconclusive',
                'explanation': '[SIMULATION] Check tool execution only', 'consequence_for_development': 'Assess simulated leap'})
        if not resolution['confirmed_roadmap_id']:
            return move('ASSESS_LEAP', {'resolution_id': resolution['id'],
                'observation_ids': [data['observations'][-1]['id']], 'explanation': '[SIMULATION] Protocol assessment only'})
        return move('COMPLETE', {'final_response': '[SIMULATION] Roadmap protocol completed. This is not an answer to the task.',
            'committed_development_refs': [{'type': 'Process', 'id': resolution['resolution_process_id']}],
            'evidence_observation_ids': [data['observations'][-1]['id']], 'goal_coverage': 'Simulation only',
            'why_further_development_not_needed': 'Protocol example finished'})


import warnings


def __getattr__(name):
    if name == "GeminiLLM":
        warnings.warn("GeminiLLM has been moved to dialectic_ai.integrations.gemini.llm.GeminiLLM", DeprecationWarning, stacklevel=2)
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        return GeminiLLM
    if name == "OpenAILLM":
        warnings.warn("OpenAILLM has been moved to dialectic_ai.integrations.openai.llm.OpenAILLM", DeprecationWarning, stacklevel=2)
        from dialectic_ai.integrations.openai.llm import OpenAILLM
        return OpenAILLM
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


@dialectical(
    origin="Interfaces of external APIs can fail with 503 or 429, which kills the entire agent process",
    contradiction="Binding to a single model makes the architecture fragile. Fault tolerance is needed",
    resolves="Chain of Responsibility pattern: sequentially tries to call models from the list. If one fails — tries the next",
    generates="Highly Available model orchestration system that does not fail due to a single provider",
    own_contradictions="Increases latency if the first models take a long time to return an error. Does not solve the problem when all providers fail",
    layer=0,
)
class FallbackLLM(BaseLLM):
    """
    LLM orchestrator (router / fallback chain).
    Takes a list of providers and attempts to perform generation in sequence.
    If a provider throws an exception, it moves to the next one.
    """

    def __init__(self, providers: list[BaseLLM]):
        if not providers:
            raise ValueError("FallbackLLM requires at least one provider")
        self.providers = providers

    async def generate(self, messages: list[dict], tools: Optional[list[dict]] = None) -> str:
        last_error = None
        for i, provider in enumerate(self.providers):
            provider_name = provider.__class__.__name__
            try:
                text = await provider.generate(messages, tools=tools)
                # An empty reply is an outage, not an answer (GigaChat returns "" under load);
                # returning it would hand the caller nothing while a fallback was available.
                if not (text or "").strip():
                    raise RuntimeError("empty response")
                return text
            except Exception as e:
                print(f"  [FallbackLLM] Provider {provider_name} ({i+1}/{len(self.providers)}) returned an error: {e}")
                last_error = e
                continue
                
        # If no provider worked
        raise RuntimeError(f"All {len(self.providers)} LLM providers are unavailable. Last error: {last_error}")

    async def generate_result(self, messages: list[dict], tools: Optional[list[dict]] = None) -> ModelResult:
        last_error = None
        for i, provider in enumerate(self.providers):
            provider_name = provider.__class__.__name__
            try:
                result = await provider.generate_result(messages, tools=tools)
                if not (result.text or "").strip() and not result.tool_calls:
                    raise RuntimeError("empty response")
                return result
            except Exception as e:
                print(f"  [FallbackLLM] Provider {provider_name} ({i+1}/{len(self.providers)}) returned an error: {e}")
                last_error = e
                continue
                
        # If no provider worked
        raise RuntimeError(f"All {len(self.providers)} LLM providers are unavailable. Last error: {last_error}")


@dialectical(
    origin="A single API provider hits rate limits or introduces bottlenecks",
    contradiction="We have multiple API keys but the agent only uses one, wasting potential throughput",
    resolves="Round-robin load balancer that distributes requests evenly across all available LLM providers",
    generates="Higher overall throughput and speed by parallelizing across rate limits",
    own_contradictions="Different models might have slightly different reasoning capabilities, causing inconsistent agent behavior",
    layer=0,
)
class BalancingLLM(BaseLLM):
    """
    LLM orchestrator (load balancer).
    Takes a list of providers and distributes requests across them in a round-robin fashion.

    A provider that fails with a rate-limit or auth error twice in a row (across
    calls, not just within one) is put on cooldown for the rest of the session
    instead of staying in the rotation and wasting a request every Nth call --
    see development_log.md 2026-09-15 for the live RuntimeError this fixes.
    """
    def __init__(self, providers: list[BaseLLM], cooldown_seconds: float = 300.0):
        if not providers:
            raise ValueError("BalancingLLM requires at least one provider")
        self.providers = providers
        self.cooldown_seconds = cooldown_seconds
        self._index = 0
        self._cooldown_until: dict[int, float] = {}
        self._consecutive_failures: dict[int, int] = {}

    @staticmethod
    def _is_rate_or_auth_error(e: Exception) -> bool:
        err = str(e).lower()
        return any(token in err for token in ("429", "401", "403", "too many requests", "unauthorized", "forbidden"))

    def _available_providers(self) -> list[BaseLLM]:
        now = time.time()
        available = [p for p in self.providers if self._cooldown_until.get(id(p), 0) <= now]
        # If everyone is cooling down, degrade gracefully rather than hard-failing.
        return available or self.providers

    async def preflight_health_check(self):
        working = []
        for provider in self.providers:
            try:
                await provider.generate([{"role": "user", "content": "ping json"}])
                working.append(provider)
            except Exception as e:
                err = str(e).lower()
                if "404" in err or "400" in err or "decommissioned" in err or "not found" in err:
                    print(f"  [BalancingLLM] WARNING: Provider {provider.__class__.__name__} is decommissioned/broken (Error: {e}). Evicting from pool.")
                else:
                    working.append(provider)
                    print(f"  [BalancingLLM] Notice: Provider {provider.__class__.__name__} failed check with {e}, but keeping in pool.")
        self.providers = working
        if not self.providers:
            raise RuntimeError("All LLM providers are unavailable. Please check your .env config.")

    async def _call_with_balancing(self, method_name: str, messages: list[dict], tools: Optional[list[dict]] = None):
        last_error = None
        available = self._available_providers()
        for _ in range(len(available)):
            provider = available[self._index % len(available)]
            self._index += 1
            try:
                result = await getattr(provider, method_name)(messages, tools=tools)
                self._consecutive_failures[id(provider)] = 0
                return result
            except Exception as e:
                print(f"  [BalancingLLM] Provider {provider.__class__.__name__} failed: {e}")
                last_error = e
                if self._is_rate_or_auth_error(e):
                    count = self._consecutive_failures.get(id(provider), 0) + 1
                    self._consecutive_failures[id(provider)] = count
                    if count >= 2:
                        self._cooldown_until[id(provider)] = time.time() + self.cooldown_seconds
                        print(f"  [BalancingLLM] Provider {provider.__class__.__name__} rate/auth-limited "
                              f"{count}x in a row -- cooling down for {self.cooldown_seconds:.0f}s.")
                else:
                    self._consecutive_failures[id(provider)] = 0
                continue
        raise RuntimeError(f"All providers failed in BalancingLLM. Last error: {last_error}")

    async def generate(self, messages: list[dict], tools: Optional[list[dict]] = None) -> str:
        return await self._call_with_balancing("generate", messages, tools)

    async def generate_result(self, messages: list[dict], tools: Optional[list[dict]] = None) -> ModelResult:
        return await self._call_with_balancing("generate_result", messages, tools)

