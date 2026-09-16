"""
benchmarks/ablation/scenarios.py

Deliberate-failure-injection scenarios for the ablation comparison (bare loop vs
DialecticalEngine). Each scenario is a self-contained, objectively-gradable unit -- add one at a
time, incrementally, per stage; a scenario added later never needs to touch or invalidate an
earlier one's results (see runner.py's per-stage, append-only report).

Stage 1: `FLAKY_RETRY` -- a tool that fails with a transient error on its first call for a given
argument, then succeeds on any later call with the SAME argument. Correct behavior: retry the
same tool call after seeing the error, not give up. Tests the most basic form of "an incomplete/
erroring tool result is a reason to develop further, not to conclude" (agent/prompt_builder.py,
added 2026-09-15) -- the simplest possible version of that rule, since the fix here is literally
"try the exact same thing again," not even "try something different."
"""
import uuid
from dataclasses import dataclass
from typing import Callable

from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ActionTool

from benchmarks.ablation.bare_agent import BareRunResult


@dialectical(
    origin="Real tool APIs fail transiently (rate limits, network blips) and succeed on retry -- "
           "this needs to be injectable on demand, deterministically, for a controlled comparison.",
    contradiction="A tool that always fails teaches nothing about recovery; a tool that never "
                  "fails never exercises the recovery path being tested at all.",
    resolves="Fails exactly once per distinct argument value, then succeeds on every subsequent "
             "call with that same value -- deterministic, cheap, no real network dependency.",
    generates="An objective, repeatable way to ask 'does this agent loop retry after a transient "
              "failure, or give up?' without needing a real flaky external service.",
    own_contradictions="Only models ONE specific failure shape (transient-then-recovers-on-retry) "
                       "-- later stages should add scenarios modeling different failure shapes "
                       "(a wrong-tool-name error requiring a DIFFERENT tool, a truncated result "
                       "requiring pagination, a malformed-LLM-response requiring repair).",
    layer=2,
)
class FlakyOnceTool(ActionTool):
    """Fails on the first call for each distinct `key`, succeeds on every call after that."""

    def __init__(self):
        self._attempted: set = set()

    @property
    def name(self) -> str:
        return "flaky_lookup"

    @property
    def description(self) -> str:
        return "Looks up a value by key. May fail with a transient error -- if it does, this is not permanent; try again."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "The key to look up."}},
            "required": ["key"],
        }

    async def execute(self, args: dict) -> Evidence:
        key = str(args.get("key", ""))
        if key not in self._attempted:
            self._attempted.add(key)
            return Evidence(
                id=str(uuid.uuid4()), source=self.name, tool_name=self.name, content=None,
                success=False, error="Transient error: service temporarily unavailable. This is not permanent.",
            )
        return Evidence(
            id=str(uuid.uuid4()), source=self.name, tool_name=self.name,
            content=f"Value for '{key}': 42", success=True,
        )


@dialectical(
    origin="Real tasks routinely mix one unconditional, clear action with one part gated on a "
           "check whose answer turns out to be empty/negative -- exactly the shape of the real "
           "GAIA2 'Yoga scenario' incident (development_log.md, 2026-09-13).",
    contradiction="A weaker agent treats the whole task as blocked by the negative check result, "
                  "even the part that was never conditional on it at all.",
    resolves="Always answers 'no tentative events' (deterministic, not an error) -- so the "
             "correct behavior is unambiguous: do the unconditional part regardless, and there is "
             "nothing left to do for the gated part, not something to ask about.",
    generates="An objective test of DECOMPOSITION specifically (does the clear part actually get "
              "executed), not just of general persistence -- distinct from flaky_retry's failure "
              "shape (a transient error, not a genuine branch point).",
    own_contradictions="The check tool never errors and never needs a retry -- this scenario "
                       "tests decomposition in isolation, not decomposition combined with error "
                       "recovery (see flaky_retry for that).",
    layer=2,
)
class SaveNoteTool(ActionTool):
    """Saves a note. Always succeeds -- the unconditional half of the decompose_or_block scenario."""

    @property
    def name(self) -> str:
        return "save_note"

    @property
    def description(self) -> str:
        return "Saves a text note."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "The note content to save."}},
            "required": ["text"],
        }

    async def execute(self, args: dict) -> Evidence:
        text = str(args.get("text", ""))
        return Evidence(id=str(uuid.uuid4()), source=self.name, tool_name=self.name,
                         content=f"Note saved: '{text}'", success=True)


@dialectical(
    origin="The decompose_or_block scenario needs a check whose answer is deterministically "
           "empty/negative -- not an error -- to isolate whether an agent conflates 'nothing "
           "found' with 'the whole task is blocked.'",
    contradiction="A check that sometimes finds events would reintroduce randomness into what "
                  "should be a controlled, always-empty gating condition.",
    resolves="Always reports zero tentative events, deterministically, as a successful (not "
             "erroring) Evidence -- the negative result IS the correct, complete answer.",
    generates="An unambiguous test of whether 'nothing to do here' gets mistaken for 'stop "
              "everything, including the unrelated unconditional part.'",
    own_contradictions="Being unconditionally empty means this tool alone can't test whether an "
                       "agent handles a check that SOMETIMES finds something -- out of scope for "
                       "this scenario by design.",
    layer=2,
)
class CheckTentativeEventsTool(ActionTool):
    """Always reports zero matching events -- a genuine, non-error negative result. The gated
    half of the decompose_or_block scenario: correct behavior on seeing this is 'nothing to do
    here,' not 'the whole task is blocked.'"""

    @property
    def name(self) -> str:
        return "check_tentative_events"

    @property
    def description(self) -> str:
        return "Checks the calendar for events tagged 'tentative'."

    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict) -> Evidence:
        return Evidence(id=str(uuid.uuid4()), source=self.name, tool_name=self.name,
                         content="No events tagged 'tentative' were found.", success=True)


@dialectical(
    origin="An agent that assumes an event exists without checking first needs a real tool to "
           "call, so that assumption produces an observable, gradable error rather than nothing.",
    contradiction="The scenario needs this tool to exist and be callable, but never expects it "
                  "to actually be invoked (CheckTentativeEventsTool always finds nothing).",
    resolves="A real, correctly-erroring delete tool -- present in the tool list so its absence "
             "is never a confound, but always reports 'no such event' since none ever exist here.",
    generates="A way to observe, if it happens, an agent skipping the check and guessing an "
              "event id directly -- a distinct failure mode from the one this scenario targets.",
    own_contradictions="Always erroring means this tool never demonstrates a successful delete -- "
                       "a future scenario testing real deletion would need a variant that succeeds.",
    layer=2,
)
class DeleteEventTool(ActionTool):
    """Deletes an event by id. Not expected to be called in decompose_or_block (the check above
    always finds nothing to delete) -- present so the agent has a real tool available if it
    (incorrectly) assumes an event exists without checking."""

    @property
    def name(self) -> str:
        return "delete_event"

    @property
    def description(self) -> str:
        return "Deletes a calendar event by its id."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"event_id": {"type": "string", "description": "The id of the event to delete."}},
            "required": ["event_id"],
        }

    async def execute(self, args: dict) -> Evidence:
        event_id = str(args.get("event_id", ""))
        return Evidence(id=str(uuid.uuid4()), source=self.name, tool_name=self.name,
                         content=None, success=False,
                         error=f"No event with id '{event_id}' exists (there are no tentative events).")


@dataclass
class Scenario:
    key: str                                  # short id, used in reports/filenames
    description: str                          # what this scenario tests, for humans reading the report
    goal: str                                 # the agent's goal text
    task: str                                 # the user's message
    make_tools: Callable[[], list]            # factory -- fresh tool instances per trial (some hold state)
    check_success: Callable[[BareRunResult], bool]   # objective, scenario-specific pass/fail


def _flaky_retry_success(result: BareRunResult) -> bool:
    return result.status == "completed" and "42" in result.response


def _decompose_or_block_success(result: BareRunResult) -> bool:
    """The objective, action-based check: did the unconditional part actually get EXECUTED (not
    just mentioned in prose)? A response that says 'I saved your note' without a real
    tool_calls_made entry for save_note does not count -- this specifically catches a claim/
    action mismatch, not just a wording pattern."""
    return any(c["name"] == "save_note" and c.get("success") for c in result.tool_calls_made)


SCENARIOS: dict[str, Scenario] = {
    "flaky_retry": Scenario(
        key="flaky_retry",
        description="A tool call fails once (transient error), then succeeds on retry with the "
                     "same argument. Correct behavior: try the SAME call again; do not give up "
                     "after the first error.",
        goal="You are a helpful assistant with access to a lookup tool. Answer the user's question using it.",
        task="Look up the value for key 'alpha' using flaky_lookup, then tell me exactly what the value is.",
        make_tools=lambda: [FlakyOnceTool()],
        check_success=_flaky_retry_success,
    ),
    "decompose_or_block": Scenario(
        key="decompose_or_block",
        description="One unconditional action (save a note) plus one part gated on a check that "
                     "always comes back empty (no tentative events to delete). Correct behavior: "
                     "save the note regardless -- it was never conditional on the calendar check. "
                     "A weaker agent treats the empty check result as blocking the WHOLE task, "
                     "including the unconditional note -- the real 'Yoga scenario' failure shape "
                     "(development_log.md, 2026-09-13). Objectively checks whether the note was "
                     "actually saved (a real tool call), not just whether the agent talked about it.",
        goal="You are a helpful personal assistant with access to note-taking and calendar tools.",
        task="Save a note that says 'Team meeting confirmed for Friday.' Also, check my calendar "
             "for any events tagged 'tentative' and delete them -- let me know if anything about "
             "this is unclear before you do it.",
        make_tools=lambda: [SaveNoteTool(), CheckTentativeEventsTool(), DeleteEventTool()],
        check_success=_decompose_or_block_success,
    ),
}
