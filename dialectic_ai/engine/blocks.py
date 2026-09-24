"""
dialectic_ai/engine/blocks.py

Block planning: each dialectical block is its own model call that sees only what that block needs,
returns only that block's content, and is linked to the previous block by the engine, not by the
model's say-so.

Why: with one actor call per move, the model always saw the whole task -- usually a "what should
be done?" question -- and answered it in every block: a solution as the simplest, an alternative
solution as the opposite, a compromise as the leap. The blocks were independent in code but were
filled by one author holding the task's question in mind. Here the development, opposite,
contradiction and leap calls never see the task's question.

The method (owner's): simplest = the given situation; development = its determinations, each a
separate process in the graph; opposite = caught from one numbered determination (the engine links
it to that determination's process); contradiction = both existing at once; leap = the result of
the opposite acting on the simplest.
"""
import json
import re
from typing import Optional

from dialectic_ai.core.runtime import DesignationRole, MoveType, Proposal

MAX_ATTEMPTS = 3

SIMPLEST = """Name the GIVEN situation of this task: the thing or state that exists and gives rise to the task,
stated plainly as it is -- including how it is given (e.g. if something is known only through a tool or a
report, that is part of the situation).
It is NOT the task's question, NOT what someone wants, NOT a goal, NOT a plan, NOT a solution. Do not restate
the task; name what is there.
Examples (other tasks):
- "Our website is slow on phones; how do we fix it?" -> "a website that loads slowly on phones" (not "make it faster")
- "Should we move the office to the suburbs?" -> "an office in the city centre" (not "moving the office")
- "Get today's temperature from the weather API." -> "a temperature known only through the API's report"
- "The food is cold; the staff can heat it. What to do?" -> "cold food"
Also say whether the task needs development at all. A plain question of fact or definition that is answered
directly (a capital city, 2 + 2, what a word means) does not: there is nothing in it to unfold, and inventing
an opposite for it would be false. Answer "needs_development": false only for such tasks.
Task: {task}
Answer in the task's language. Return only JSON: {{"simplest": "...", "needs_development": true or false}}{feedback}"""

DEVELOP = """Unfold what this IS: list its determinations -- properties, what it consists in, what it is
in relation to other things. Not steps, not what to do about it, not solutions.
Include determinations that point beyond it (e.g. "food that was not heated" points to heating).
Example: "cold food" -> "tasteless", "can be harmful", "unpleasant to eat", "food that was not heated",
"food that can be heated".
This: {subject}
Give 4 to 8 short determinations in the same language. Return only JSON: {{"determinations": ["...", "..."]}}{feedback}"""

OPPOSITE = """Here is a situation and its determinations. Find the determination that points BEYOND the
situation itself, to another process that exists on its own. That process is the opposite.
Example: "cold food" with determination "food that was not heated" points to "heating of food".
The opposite is not an alternative solution and not a negation ("don't do it"); it is the process a
determination points to. If no determination points beyond the situation (e.g. a plain question of
fact), answer with number 0.
Situation: {simplest}
Determinations:
{numbered}
Return only JSON: {{"number": n, "opposite": "the process it points to", "how": "how that determination points to it"}}{feedback}"""

CONTRADICTION = """Two things hold at the same time. State their contradiction: that the first is as it is,
and at once the second shows it otherwise. Not a choice between two options.
Example: "the food is cold, and at the same time food can be heated".
First (the situation): {simplest}
Second (its opposite, caught from "{caught}"): {opposite}
Return only JSON: {{"contradiction": "... and at the same time ...", "how_each_develops": "one sentence"}}{feedback}"""

LEAP = """What results when the second acts on the first? Name the result itself -- a resolution, or a new
quality that negates the old one. Not a recommendation, not a compromise of both, not what someone
should do.
Example: heating acting on cold food -> "the cold food is heated" (resolution).
Example: AI writing acting on a student's essay -> "the work can no longer be evaluated as the
student's" (a new quality).
First (the situation): {simplest}
Second (acting on it): {opposite}
Return only JSON: {{"acting": "how the second acts on the first", "result": "the leap itself",
"outcome": "replacement" or "mediation"}}{feedback}"""


def _json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    return json.loads(match.group(0))


class BlockPlanner:
    """Drives the planning phase block by block. Every move still passes the engine's structural
    validation and judge; a rejected block is retried with the judge's reason."""

    def __init__(self, engine, semantic_validator, goal):
        self.engine = engine
        self.validator = semantic_validator
        self.goal = goal
        self.llm = engine.agent.llm

    async def _ask(self, template: str, feedback: str, **fields) -> dict:
        note = f"\n\nYour previous answer was rejected: {feedback}\nCorrect exactly that." if feedback else ""
        reply = await self.llm.generate([{"role": "user", "content": template.format(feedback=note, **fields)}])
        return _json(reply)

    async def _block(self, template: str, build, **fields):
        """Asks for one block and submits the move `build(answer)` makes of it, retrying on rejection.
        Returns (result_id, answer) or (None, reason)."""
        feedback = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                answer = await self._ask(template, feedback, **fields)
                proposal = build(answer)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                feedback = f"the answer was not in the required form ({exc})"
                continue
            if proposal is None:
                return None, answer
            result_id, reason = await self.engine._submit(proposal, self.validator, self.goal, origin="block")
            if result_id:
                return result_id, answer
            feedback = reason
        return None, feedback

    @staticmethod
    def _move(move_type, payload, why):
        return Proposal(move_type=move_type, payload=payload, why_this_move_now=why,
                        expected_goal_contribution="One block of the dialectical method.")

    def _designation(self, role):
        return next((d for d in self.engine.state.get_all_designations() if d.role == role), None)

    async def _develop(self, process_id: str, subject: str) -> list:
        """Each determination becomes its own emergent process; returns [(relation_id, text), ...]."""
        state = self.engine.state
        answer = None
        feedback = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                answer = await self._ask(DEVELOP, feedback, subject=subject)
                determinations = [str(d).strip() for d in answer["determinations"] if str(d).strip()]
                if len(determinations) < 2:
                    raise ValueError("fewer than 2 determinations")
                break
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                feedback = f"the answer was not in the required form ({exc})"
        else:
            return []
        committed = []
        for text in determinations[:8]:
            proposal = self._move(MoveType.DEVELOP_PROCESS, {
                "source_process_id": process_id, "emergent_content": text,
                "potential_containment": f"A determination of: {subject}", "emergence": "Unfolded from the source",
                "concretization": text, "new_content": text}, "Unfold a determination of the process.")
            # Determinations are checked structurally only: judged one by one, rejected ones silently
            # dropped out (a live run kept one of six) and the calls timed runs out. Their quality is
            # judged where it matters -- the opposite and contradiction moves that cite them.
            result_id, _ = await self.engine._submit(proposal, None, self.goal, origin="block")
            if result_id:
                relation = next(r for r in state.get_all_development_relations() if r.emergent_process_id == result_id)
                committed.append((relation.id, text))
        return committed

    async def plan(self) -> str:
        """Returns "roadmap" (route accepted), "no_contradiction" (hand over for the clear path), or
        "fallback" (a block could not be committed; the regular actor continues from this state)."""
        state = self.engine.state
        task = self.goal.content

        # 1. Simplest -- the only block that sees the task, so it also decides whether the task needs
        # development at all: the later blocks never see the question and would find an "opposite"
        # in anything (a live run turned "the capital of France" into colonial expansion).
        def simplest_move(answer):
            return self._move(MoveType.PROPOSE_SIMPLEST, {"content": str(answer["simplest"]).strip()},
                              "The task's given situation.")
        pid, answer = await self._block(SIMPLEST, simplest_move, task=task)
        if not pid:
            return "fallback"
        if isinstance(answer, dict) and answer.get("needs_development") is False:
            candidate = next(d for d in state.get_all_designations() if d.process_id == pid)
            approve = self._move(MoveType.ASSESS_SIMPLEST, {"candidate_simplest_id": candidate.id, "approved": True},
                                 "The candidate is the task's given situation.")
            await self.engine._submit(approve, self.validator, self.goal, origin="block")
            return "no_contradiction"
        candidate = next(d for d in state.get_all_designations() if d.process_id == pid)
        approve = self._move(MoveType.ASSESS_SIMPLEST, {"candidate_simplest_id": candidate.id, "approved": True},
                             "The candidate is the task's given situation.")
        if not (await self.engine._submit(approve, self.validator, self.goal, origin="block"))[0]:
            return "fallback"
        simplest = self._designation(DesignationRole.SIMPLEST)
        simplest_text = state.get_process(simplest.process_id).content

        # 2. Development of the simplest -- sees only the simplest.
        determinations = await self._develop(simplest.process_id, simplest_text)
        if not determinations:
            return "fallback"

        # 3. Opposite -- sees only the simplest and its numbered determinations; the engine links it.
        numbered = "\n".join(f"{i}. {text}" for i, (_, text) in enumerate(determinations, 1))
        caught = {}

        def opposite_move(answer):
            number = int(answer["number"])
            if number == 0:
                return None
            if not 1 <= number <= len(determinations):
                raise ValueError(f"number must be 1..{len(determinations)} or 0")
            relation_id, text = determinations[number - 1]
            relation = state.get_development_relation(relation_id)
            caught.update(text=text, relation_id=relation_id)
            return self._move(MoveType.DESIGNATE_OPPOSITE, {
                "simplest_id": simplest.id, "context_id": relation.emergent_process_id,
                "content": str(answer["opposite"]).strip(), "caught_from": text,
                "justification": str(answer.get("how") or text)}, "The opposite caught from a determination.")
        opposite_pid, answer = await self._block(OPPOSITE, opposite_move, simplest=simplest_text, numbered=numbered)
        if not opposite_pid:
            return "no_contradiction" if isinstance(answer, dict) and int(answer.get("number", -1)) == 0 else "fallback"
        opposite = self._designation(DesignationRole.OPPOSITE)
        opposite_text = state.get_process(opposite.process_id).content

        # 4. Development of the opposite -- sees only the opposite.
        opposite_devs = await self._develop(opposite.process_id, opposite_text)
        if not opposite_devs:
            return "fallback"

        # 5. Contradiction -- sees only the two sides.
        def contradiction_move(answer):
            return self._move(MoveType.ESTABLISH_CONTRADICTION, {
                "simplest_id": simplest.id, "opposite_id": opposite.id,
                "simplest_dev_ref_ids": [caught["relation_id"]], "opposite_dev_ref_ids": [r for r, _ in opposite_devs],
                "unity_justification": str(answer["contradiction"]).strip(),
                "developing_unity_description": str(answer.get("how_each_develops") or answer["contradiction"])},
                "Both exist at once.")
        contradiction_id, _ = await self._block(CONTRADICTION, contradiction_move, simplest=simplest_text,
                                                opposite=opposite_text, caught=caught["text"])
        if not contradiction_id:
            return "fallback"

        # 6. Leap -- sees only the two sides, asked what results when one acts on the other.
        def leap_move(answer):
            outcome = answer.get("outcome") if answer.get("outcome") in ("replacement", "mediation") else "replacement"
            return self._move(MoveType.PROPOSE_LEAP, {
                "contradiction_id": contradiction_id, "opposite_acting_on_simplest": str(answer["acting"]).strip(),
                "resolution_content": str(answer["result"]).strip(), "resolution_outcome": outcome},
                "The result of the opposite acting on the simplest.")
        leap_pid, _ = await self._block(LEAP, leap_move, simplest=simplest_text, opposite=opposite_text)
        if not leap_pid:
            return "fallback"
        leap = next(r for r in state._resolution_relations.values() if r.resolution_process_id == leap_pid)

        # 7. Route -- built by the engine from the leap.
        route = self._move(MoveType.BEGIN_EXECUTION, {
            "simplest_id": simplest.id, "contradiction_ids": [contradiction_id], "resolution_ids": [leap.id],
            "execution_process_ids": [leap.resolution_process_id]}, "Act on the leap.")
        return "roadmap" if (await self.engine._submit(route, self.validator, self.goal, origin="block"))[0] else "fallback"
