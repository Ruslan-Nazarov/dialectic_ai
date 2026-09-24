"""
dialectic_ai/engine/blocks.py

Block planning: a rigid block structure in which each block performs one element of the
dialectical analysis. The engine, not the model, fixes the order; each block is its own model call
that sees only the results of the blocks before it and returns only its own element; the engine
links each result into the graph.

Why: with one actor call per move, the model chose the moves itself and always saw the whole task --
usually a "what should be done?" question -- so it answered that question in every block. Here only
the first block sees the task; it restates the task as a process, and every later block works from
that process and the blocks before it.

The blocks, in order:
0. the task as a process;
1. simplest: the process from which the whole situation develops (e.g. "sales automation" for a
   request for an AI chatbot), not a piece of the situation and not a solution;
2. development: a chain from the simplest toward the task's process, each process contained in the
   previous one -- a transition, not a list of properties; each link is its own process in the graph,
   developed from the link before it;
3. opposite: found among the developing processes -- one whose own development does not require the
   simplest; the engine links it to that process;
4. the opposite's own development;
5. contradiction: simplest and opposite in the unity of their development;
6. resolution: a process replacing both by taking them in (replacement), or keeping the contradiction
   alive until it is resolved (mediation);
7. route: built by the engine from the resolution.
"""
import json
import re

from dialectic_ai.core.runtime import DesignationRole, MoveType, Proposal

MAX_ATTEMPTS = 3

REQUEST = """State this task as a PROCESS -- what is happening or being done -- not as a question.
Examples (other tasks):
- "Pythagoras' theorem" -> "to get the square of the hypotenuse of a right triangle, add the squares of the legs"
- "Our website is slow on phones; how do we fix it?" -> "a company is trying to make its site load fast on phones"
Also say whether the task needs dialectical development at all. A plain question of fact or definition answered
directly (a capital city, 2 + 2, what a word means) does not; answer "needs_development": false only for those.
Task: {task}
Answer in the task's language. Return only JSON: {{"process": "...", "needs_development": true or false}}{feedback}"""

SIMPLEST = """Find the SIMPLEST process for this process: the process from which the whole of it develops.
It must be connected to this process; the processes that develop out of it must approach this process as a
whole; and each of them must stay connected to it. It is not a piece of the situation and not a solution.
Examples: "a business wants an AI chatbot so clients call support less" -> "sales automation" (it develops into
automating contact with clients, then answering typical questions automatically, and so into wanting a bot).
"to get the square of the hypotenuse, add the squares of the legs" -> "a triangle".
Process: {process}
Answer in the process's language. Return only JSON: {{"simplest": "..."}}{feedback}"""

DEVELOP = """Develop this process toward the target, from abstract to concrete. Give a CHAIN in which each next
process is contained in the previous one potentially and, as it arises, makes the previous one more definite.
Show how each turns into the next -- a list of properties is change, not development. Stop when the chain
reaches the target, or after 6 steps.
Example: "sales automation" toward "a business wants an AI chatbot so clients call support less" ->
"automating contact with clients", "answering clients' typical questions automatically", "wanting an AI chatbot
that answers clients instead of the support line".
Process: {subject}
Target: {target}
Same language. Return only JSON: {{"chain": [{{"process": "...", "how_it_arises": "..."}}, ...]}}{feedback}"""

DEVELOP_OPPOSITE = """Develop this process in its own right, from abstract to concrete: a CHAIN in which each next
process is contained in the previous one and makes it more definite. 2 to 4 steps, transitions not a list.
Process: {subject}
Same language. Return only JSON: {{"chain": [{{"process": "...", "how_it_arises": "..."}}, ...]}}{feedback}"""

OPPOSITE = """Here is a simplest process and the chain of processes that developed out of it. Find the OPPOSITE
among them: a process whose own development does not require the simplest -- it excludes the simplest's
existence without destroying it (it could go on developing even if the simplest were not there).
Example: simplest "cold food", chain includes "heating of food" -- heating develops whether or not this food is
cold, so it is the opposite. Not an alternative way to the same goal, not a negation.
If none of them is like that, answer number 0.
Simplest: {simplest}
Developing processes:
{numbered}
Return only JSON: {{"number": n, "independence": "why its development does not require the simplest"}}{feedback}"""

CONTRADICTION = """State the contradiction: the simplest and its opposite taken in the unity of their development --
how each develops and how their development holds together while one does not need the other. Not a choice
between two options.
Simplest: {simplest} (developing as: {simplest_chain})
Opposite: {opposite} (developing as: {opposite_chain})
Return only JSON: {{"contradiction": "...", "unity_of_development": "..."}}{feedback}"""

RESOLUTION = """Find the process that resolves this contradiction. Either a process that REPLACES the simplest and the
opposite by taking both into its own development ("replacement"), or a process that lets the contradiction keep
existing until it is resolved ("mediation"). Explain it as the resolution of this contradiction.
Not a compromise or hybrid of two options, not a recommendation of what someone should do.
Example: cold food and heating -> "heating of the cold food" (replacement: it takes in both).
Example: a student's essay and AI writing -> "the work can no longer be evaluated as the student's" (replacement).
Simplest: {simplest}
Opposite: {opposite}
Contradiction: {contradiction}
Return only JSON: {{"resolution": "...", "how_resolves": "how it takes in both, or keeps them together",
"outcome": "replacement" or "mediation"}}{feedback}"""


def _json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    return json.loads(match.group(0))


def _nonempty(value, name):
    if not str(value or "").strip():
        raise ValueError(f"{name} is empty")


class BlockPlanner:
    """Runs the blocks in their fixed order. Every block's move still passes the engine's structural
    validation and, except the development links, the judge; a rejected block is retried with the
    reason."""

    def __init__(self, engine, semantic_validator, goal):
        self.engine = engine
        self.validator = semantic_validator
        self.goal = goal
        self.llm = engine.agent.llm

    async def _ask(self, template: str, feedback: str, **fields) -> dict:
        note = f"\n\nYour previous answer was rejected: {feedback}\nCorrect exactly that." if feedback else ""
        reply = await self.llm.generate([{"role": "user", "content": template.format(feedback=note, **fields)}])
        return _json(reply)

    async def _answer(self, template: str, check, **fields):
        """Asks until `check(answer)` accepts the shape; returns the answer or None."""
        feedback = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                answer = await self._ask(template, feedback, **fields)
                check(answer)
                return answer
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                feedback = f"the answer was not in the required form ({exc})"
        return None

    async def _block(self, template: str, build, **fields):
        """Asks for one block and submits the move `build(answer)` makes of it, retrying on rejection.
        Returns (result_id, answer) or (None, answer_or_reason)."""
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
                        expected_goal_contribution="One block of the dialectical analysis.")

    def _designation(self, role):
        return next((d for d in self.engine.state.get_all_designations() if d.role == role), None)

    @staticmethod
    def _chain_shape(answer):
        chain = [c for c in answer["chain"] if str(c.get("process", "")).strip()]
        if len(chain) < 2:
            raise ValueError("the chain needs at least 2 processes")

    async def _develop(self, process_id: str, template: str, **fields) -> list:
        """Commits the chain link by link, each developed from the link before it (a transition, not a
        list hung off one node). Links are checked structurally; the judge sees them through the moves
        that cite them. Returns [(relation_id, emergent_process_id, text), ...]."""
        state = self.engine.state
        answer = await self._answer(template, self._chain_shape, **fields)
        if answer is None:
            return []
        links, source, source_text = [], process_id, fields.get("subject", "")
        for step in answer["chain"][:6]:
            text = str(step.get("process", "")).strip()
            if not text:
                continue
            how = str(step.get("how_it_arises") or text)
            proposal = self._move(MoveType.DEVELOP_PROCESS, {
                "source_process_id": source, "emergent_content": text,
                "potential_containment": f"Contained in: {source_text}", "emergence": how,
                "concretization": text, "new_content": how}, "The next, more concrete process.")
            result_id, _ = await self.engine._submit(proposal, None, self.goal, origin="block")
            if not result_id:
                break
            relation = next(r for r in state.get_all_development_relations() if r.emergent_process_id == result_id)
            links.append((relation.id, result_id, text))
            source, source_text = result_id, text
        return links

    async def plan(self) -> str:
        """Returns "roadmap" (route accepted), "no_contradiction" (hand over for the clear path), or
        "fallback" (a block could not be committed; the regular actor continues from this state)."""
        state = self.engine.state

        # 0. The task as a process -- the only block that sees the task itself.
        request = await self._answer(REQUEST, lambda a: _nonempty(a["process"], "process"), task=self.goal.content)
        if request is None:
            return "fallback"
        task_process = str(request["process"]).strip()
        plain_question = request.get("needs_development") is False
        await self.engine.logger.trace_event("task_process", {"run_id": self.engine.run_id, "process": task_process,
                                                              "needs_development": not plain_question})

        # 1. Simplest -- sees only the task's process. A plain question has nothing to develop.
        if plain_question:
            simplest_proposal = self._move(MoveType.PROPOSE_SIMPLEST, {"content": task_process},
                                           "A plain question: nothing to develop.")
            pid, _ = await self.engine._submit(simplest_proposal, self.validator, self.goal, origin="block")
        else:
            def simplest_move(answer):
                _nonempty(answer["simplest"], "simplest")
                return self._move(MoveType.PROPOSE_SIMPLEST, {"content": str(answer["simplest"]).strip()},
                                  "The process from which the whole situation develops.")
            pid, _ = await self._block(SIMPLEST, simplest_move, process=task_process)
        if not pid:
            return "fallback"
        candidate = next(d for d in state.get_all_designations() if d.process_id == pid)
        approve = self._move(MoveType.ASSESS_SIMPLEST, {"candidate_simplest_id": candidate.id, "approved": True},
                             "The candidate is the simplest process of the task.")
        if not (await self.engine._submit(approve, self.validator, self.goal, origin="block"))[0]:
            return "fallback"
        if plain_question:
            return "no_contradiction"
        simplest = self._designation(DesignationRole.SIMPLEST)
        simplest_text = state.get_process(simplest.process_id).content

        # 2. Development toward the task's process -- sees the simplest and its target.
        chain = await self._develop(simplest.process_id, DEVELOP, subject=simplest_text, target=task_process)
        if not chain:
            return "fallback"

        # 3. Opposite -- found among the developing processes; the engine links it to that process.
        numbered = "\n".join(f"{i}. {text}" for i, (_, _, text) in enumerate(chain, 1))
        found = {}

        def opposite_move(answer):
            number = int(answer["number"])
            if number == 0:
                return None
            if not 1 <= number <= len(chain):
                raise ValueError(f"number must be 1..{len(chain)} or 0")
            _nonempty(answer.get("independence"), "independence")
            relation_id, process_id, text = chain[number - 1]
            found.update(index=number - 1)
            return self._move(MoveType.DESIGNATE_OPPOSITE, {
                "simplest_id": simplest.id, "context_id": process_id, "content": text,
                "independence": str(answer["independence"]).strip(),
                "justification": f"Developing process {number} of the simplest: {text}"},
                "A developing process whose development does not require the simplest.")
        opposite_pid, answer = await self._block(OPPOSITE, opposite_move, simplest=simplest_text, numbered=numbered)
        if not opposite_pid:
            return "no_contradiction" if isinstance(answer, dict) and str(answer.get("number")) == "0" else "fallback"
        opposite = self._designation(DesignationRole.OPPOSITE)
        opposite_text = state.get_process(opposite.process_id).content

        # 4. The opposite's own development -- sees only the opposite.
        opposite_chain = await self._develop(opposite.process_id, DEVELOP_OPPOSITE, subject=opposite_text)
        if not opposite_chain:
            return "fallback"

        # 5. Contradiction -- the two sides in the unity of their development.
        simplest_refs = [relation_id for relation_id, _, _ in chain[:found["index"] + 1]]

        def contradiction_move(answer):
            _nonempty(answer["contradiction"], "contradiction")
            return self._move(MoveType.ESTABLISH_CONTRADICTION, {
                "simplest_id": simplest.id, "opposite_id": opposite.id,
                "simplest_dev_ref_ids": simplest_refs, "opposite_dev_ref_ids": [r for r, _, _ in opposite_chain],
                "unity_justification": str(answer["contradiction"]).strip(),
                "developing_unity_description": str(answer.get("unity_of_development") or answer["contradiction"])},
                "The simplest and the opposite in the unity of their development.")
        contradiction_id, _ = await self._block(
            CONTRADICTION, contradiction_move, simplest=simplest_text, opposite=opposite_text,
            simplest_chain=" -> ".join(t for _, _, t in chain), opposite_chain=" -> ".join(t for _, _, t in opposite_chain))
        if not contradiction_id:
            return "fallback"
        contradiction_text = state.get_contradiction(contradiction_id).unity_justification

        # 6. Resolution -- sees the two sides and their contradiction.
        def resolution_move(answer):
            _nonempty(answer["resolution"], "resolution")
            _nonempty(answer.get("how_resolves"), "how_resolves")
            outcome = answer.get("outcome") if answer.get("outcome") in ("replacement", "mediation") else "replacement"
            return self._move(MoveType.PROPOSE_LEAP, {
                "contradiction_id": contradiction_id, "how_resolves": str(answer["how_resolves"]).strip(),
                "resolution_content": str(answer["resolution"]).strip(), "resolution_outcome": outcome},
                "The process that resolves the contradiction.")
        leap_pid, _ = await self._block(RESOLUTION, resolution_move, simplest=simplest_text, opposite=opposite_text,
                                        contradiction=contradiction_text)
        if not leap_pid:
            return "fallback"
        leap = next(r for r in state._resolution_relations.values() if r.resolution_process_id == leap_pid)

        # 7. Route -- built by the engine from the resolution.
        route = self._move(MoveType.BEGIN_EXECUTION, {
            "simplest_id": simplest.id, "contradiction_ids": [contradiction_id], "resolution_ids": [leap.id],
            "execution_process_ids": [leap.resolution_process_id]}, "Act on the resolution.")
        return "roadmap" if (await self.engine._submit(route, self.validator, self.goal, origin="block"))[0] else "fallback"
