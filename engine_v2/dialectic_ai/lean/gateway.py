"""Provider-agnostic structured-output gateway for the lean dialectical runtime.

Deliberately NOT built on the OpenAI Agents SDK (the rehearsal's own gateway,
`rehearsal/model.py`, was). Codex being required for *development* on
hackathon day does not require the *solution* to depend on OpenAI's SDK, and
the exact set of provider API keys available is only announced at 12:30 on
23.09 -- so this wraps `dialectic_ai.core.llm.BaseLLM`, the same thin,
already-multi-provider abstraction the rest of this framework uses (GigaChat,
Gemini, OpenAI-compatible endpoints, Cerebras, Groq, ...). Swapping providers
is a `build_llm(name)` call, not a rewrite.
"""
import json
import re

from pydantic import BaseModel


class ModelGatewayError(RuntimeError):
    """A technical generation failure, never evidence of a contradiction."""


class _NullLog:
    def emit(self, event: str, **data):
        pass


_FENCED_JSON = re.compile(r"\s*```(?:json)?[ \t]*\r?\n(.*?)\r?\n```\s*", re.DOTALL | re.IGNORECASE)


class LeanGateway:
    """Wraps any `BaseLLM` to satisfy the `graph.py` gateway contract:
    `await gateway.generate(instructions, payload, output_type, stage) -> BaseModel`.

    Retry/backoff on transient provider errors is already handled inside each
    `BaseLLM` subclass (see `core/retry.py`) -- this class does not duplicate
    that. It only handles turning a schema + payload into a prompt and
    parsing the response back into the requested pydantic model.
    """

    def __init__(self, llm, log=None):
        self.llm = llm
        self.log = log or _NullLog()

    async def generate(self, instructions: str, payload: dict,
                        output_type: type[BaseModel], stage: str) -> BaseModel:
        schema = output_type.model_json_schema()
        prompt = (
            instructions.strip()
            + "\n\nRespond with exactly ONE JSON object matching this schema, and nothing else "
              "(no Markdown fence, no prose before or after):\n"
            + json.dumps(schema, ensure_ascii=False)
            + "\n\nDATA:\n" + json.dumps(payload, ensure_ascii=False)
        )
        # A rejection buried inside the DATA blob, alongside everything else, was
        # observed to be ignored: the model repeated the exact same invalid enum
        # value verbatim on its one allowed retry even though the correct feedback
        # was present in payload["rejection"]. Put it first, in its own sentence,
        # the way the full Runtime V2 engine's anti-repeat nudge does (same lesson,
        # same day, different engine).
        rejection = payload.get("rejection")
        if rejection:
            prompt = (
                f"STOP. Your previous proposal for this exact step was rejected: {rejection}\n"
                f"Fix specifically that before proposing again. Do not repeat the same value.\n\n"
            ) + prompt
        self.log.emit("model_request", stage=stage, output_schema=schema, payload=payload)
        try:
            raw = await self.llm.generate([{"role": "user", "content": prompt}])
        except Exception as exc:
            self.log.emit("model_error", stage=stage, error_type=type(exc).__name__)
            raise ModelGatewayError(f"{stage}: {type(exc).__name__}: {exc}") from exc

        self.log.emit("model_output", stage=stage, output=raw)
        text = raw
        fenced = _FENCED_JSON.fullmatch(text)
        if fenced:
            text = fenced.group(1)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # Not valid JSON at all -- a transport/formatting failure, not a
            # content mistake a revision retry could meaningfully fix with
            # the same feedback path graph.accept() uses. Keep this one as
            # ModelGatewayError (uncaught by the per-stage retry loop).
            self.log.emit("model_error", stage=stage, error_type=type(exc).__name__)
            raise ModelGatewayError(f"{stage}: response was not valid JSON: {exc}") from exc
        # A schema-invalid but well-formed proposal (e.g. an enum value the
        # model got slightly wrong) is exactly the kind of mistake a revision
        # retry with feedback should catch -- so let pydantic's own
        # ValidationError propagate unwrapped here. ScratchRuntime.run()
        # explicitly catches `(MoveRejected, ValidationError)` per stage and
        # retries once with feedback; wrapping this in ModelGatewayError
        # (as the rehearsal's own OpenAI-Agents-SDK gateway did) skips that
        # retry entirely and kills the whole run on one fixable slip --
        # confirmed live: a `basis` value one word off ended a run outright.
        output = output_type.model_validate(data)
        self.log.emit("model_success", stage=stage)
        return output
