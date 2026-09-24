"""
dialectic_ai/engine/blocks.py

Block planning: a rigid block structure in which each block performs one element of the
dialectical analysis. The engine, not the model, fixes the order; each block is its own model call
that sees only the results passed to it and returns only its own element; the engine links each
result into the graph.

Why: with one actor call per move, the model chose the moves itself and always saw the whole task --
usually a "what should be done?" question -- so it answered that question in every block. Here only
the first block sees the task; it restates the task as a process, and every later block works from
what the blocks before it pass on.

The flow:
0. the task, stated as a process;
1. simplest: the process from which the whole situation develops (e.g. "sales automation" for a
   request for an AI chatbot), not a piece of the situation and not a solution;
2. the simplest's development is a BUNDLE: the simplest yields its developing elements, and each
   element is developed in its own block (abstract -> concrete, a transition, not a list);
3. opposite: chosen from that bundle -- an element whose own development does not require the
   simplest; the engine links it to that element;
4. the opposite's development: its own bundle, each element in its own block;
5. contradiction: the simplest itself (without its bundle -- the bundle served to find the opposite)
   and the opposite with its bundle, in the unity of their development;
6. resolution of the contradiction: a process replacing both by taking them in (replacement), or
   keeping the contradiction alive until it is resolved (mediation);
7. route: built by the engine from the resolution.
"""
import json
import re

from dialectic_ai.core.runtime import DesignationRole, MoveType, Proposal

MAX_ATTEMPTS = 3
BUNDLE_MAX = 5          # elements per bundle: enough to find the opposite, bounded for cost
ELEMENT_STEPS_MAX = 3   # how far one element is developed in its own block

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

BUNDLE = """Name the processes that develop out of this process -- the elements of its development. Each is
contained in it potentially and, arising, makes it more definite; together they move toward the target.
Processes, not properties and not steps of a solution. 3 to {limit} of them.
Example: "cold food" -> "food that was not heated", "food losing its taste", "heating of food", ...
Process: {subject}{target}
Same language. Return only JSON: {{"elements": ["...", "..."]}}{feedback}"""

ELEMENT = """Develop this element of the process's development: how it arises out of the process, and what it
becomes as it grows more concrete. 1 to {steps} steps, each next contained in the previous one and making it more
definite -- a transition, not a list.
Process: {subject}
Element: {element}
Same language. Return only JSON: {{"steps": [{{"process": "...", "how_it_arises": "..."}}, ...]}}{feedback}"""

OPPOSITE = """Here is a simplest process and the bundle of its development. Choose the OPPOSITE from the bundle: an
element whose own development does not require the simplest -- it excludes the simplest's existence without
destroying it (it could go on developing even if the simplest were not there).
Example: simplest "cold food", bundle includes "heating of food" -- heating develops whether or not this food is
cold, so it is the opposite. Not an alternative way to the same goal, not a negation.
If no element is like that, answer number 0.
Simplest: {simplest}
Bundle:
{bundle}
Return only JSON: {{"number": n, "independence": "why its development does not require the simplest"}}{feedback}"""

CONTRADICTION = """State the contradiction: the simplest and its opposite with the bundle of its development, taken in
the unity of their development -- how they develop together while one does not need the other. Not a choice
between two options.
Simplest: {simplest}
Opposite: {opposite}
Its development:
{opposite_bundle}
Return only JSON: {{"contradiction": "...", "unity_of_development": "..."}}{feedback}"""

RESOLUTION = """Resolve this contradiction: find the process that resolves it. Either a process that REPLACES the
simplest and the opposite by taking both into its own development ("replacement"), or a process that lets the
contradiction keep existing until it is resolved ("mediation"). Explain it as the resolution of this
contradiction. Not a compromise or hybrid of two options, not a recommendation of what someone should do.
Example: cold food and heating -> "heating of the cold food" (replacement: it takes in both).
Example: a student's essay and AI writing -> "the work can no longer be evaluated as the student's" (replacement).
Contradiction: {contradiction}
Simplest: {simplest}
Opposite: {opposite}
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


class Element:
    """One element of a bundle: its process in the graph, and the chain it developed into."""

    def __init__(self, text, relation_id, process_id):
        self.text, self.relation_id, self.process_id = text, relation_id, process_id
        self.steps = []           # [(relation_id, process_id, text), ...]

    @property
    def relation_ids(self):
        return [self.relation_id] + [r for r, _, _ in self.steps]

    def describe(self):
        return self.text + (" -> " + " -> ".join(t for _, _, t in self.steps) if self.steps else "")


class BlockPlanner:
    """Runs the blocks in their fixed order. Every block's move still passes the engine's structural
    validation and, except the development moves, the judge; a rejected block is retried with the
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

    async def _develop_step(self, source_id, source_text, text, how):
        """Commits one development move (structure only: the judge sees development through the
        opposite and contradiction moves that cite it)."""
        proposal = self._move(MoveType.DEVELOP_PROCESS, {
            "source_process_id": source_id, "emergent_content": text,
            "potential_containment": f"Contained in: {source_text}", "emergence": how,
            "concretization": text, "new_content": how}, "A process developing out of its source.")
        result_id, _ = await self.engine._submit(proposal, None, self.goal, origin="block")
        if not result_id:
            return None
        relation = next(r for r in self.engine.state.get_all_development_relations() if r.emergent_process_id == result_id)
        return relation.id, result_id

    async def _bundle(self, process_id: str, subject: str, target: str = "") -> list:
        """The development of a process as a bundle: its elements, then each element developed in its
        own block. Returns [Element, ...]."""
        def shape(answer):
            if len([e for e in answer["elements"] if str(e).strip()]) < 2:
                raise ValueError("the bundle needs at least 2 elements")
        answer = await self._answer(BUNDLE, shape, subject=subject, limit=BUNDLE_MAX,
                                    target=f"\nTarget: {target}" if target else "")
        if answer is None:
            return []
        elements = []
        for text in [str(e).strip() for e in answer["elements"] if str(e).strip()][:BUNDLE_MAX]:
            committed = await self._develop_step(process_id, subject, text, f"Develops out of: {subject}")
            if committed:
                elements.append(Element(text, *committed))
        for element in elements:
            steps = await self._answer(ELEMENT, lambda a: _nonempty(a["steps"] and a["steps"][0].get("process"), "steps"),
                                       subject=subject, element=element.text, steps=ELEMENT_STEPS_MAX)
            source_id, source_text = element.process_id, element.text
            for step in (steps or {}).get("steps", [])[:ELEMENT_STEPS_MAX]:
                text = str(step.get("process", "")).strip()
                if not text:
                    continue
                committed = await self._develop_step(source_id, source_text, text, str(step.get("how_it_arises") or text))
                if not committed:
                    break
                element.steps.append((*committed, text))
                source_id, source_text = committed[1], text
        return elements

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

        # 1. Simplest -- receives the task's process. A plain question has nothing to develop.
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

        # 2. The simplest's development -- a bundle; receives the simplest (and the task's process as target).
        bundle = await self._bundle(simplest.process_id, simplest_text, target=task_process)
        if not bundle:
            return "fallback"

        # 3. Opposite -- chosen from the bundle; the engine links it to that element.
        listed = "\n".join(f"{i}. {e.describe()}" for i, e in enumerate(bundle, 1))
        chosen = {}

        def opposite_move(answer):
            number = int(answer["number"])
            if number == 0:
                return None
            if not 1 <= number <= len(bundle):
                raise ValueError(f"number must be 1..{len(bundle)} or 0")
            _nonempty(answer.get("independence"), "independence")
            element = bundle[number - 1]
            chosen["element"] = element
            return self._move(MoveType.DESIGNATE_OPPOSITE, {
                "simplest_id": simplest.id, "context_id": element.process_id, "content": element.text,
                "independence": str(answer["independence"]).strip(),
                "justification": f"Element {number} of the simplest's development: {element.describe()}"},
                "An element of the bundle whose development does not require the simplest.")
        opposite_pid, answer = await self._block(OPPOSITE, opposite_move, simplest=simplest_text, bundle=listed)
        if not opposite_pid:
            return "no_contradiction" if isinstance(answer, dict) and str(answer.get("number")) == "0" else "fallback"
        opposite = self._designation(DesignationRole.OPPOSITE)
        opposite_text = state.get_process(opposite.process_id).content

        # 4. The opposite's development -- its own bundle; receives the opposite.
        opposite_bundle = await self._bundle(opposite.process_id, opposite_text)
        if not opposite_bundle:
            return "fallback"

        # 5. Contradiction -- receives the simplest (without its bundle) and the opposite with its bundle.
        # In the graph the simplest's side is the development the opposite was found in.
        simplest_refs = [chosen["element"].relation_id]
        opposite_refs = [r for e in opposite_bundle for r in e.relation_ids]

        def contradiction_move(answer):
            _nonempty(answer["contradiction"], "contradiction")
            return self._move(MoveType.ESTABLISH_CONTRADICTION, {
                "simplest_id": simplest.id, "opposite_id": opposite.id,
                "simplest_dev_ref_ids": simplest_refs, "opposite_dev_ref_ids": opposite_refs,
                "unity_justification": str(answer["contradiction"]).strip(),
                "developing_unity_description": str(answer.get("unity_of_development") or answer["contradiction"])},
                "The simplest and the opposite in the unity of their development.")
        contradiction_id, _ = await self._block(
            CONTRADICTION, contradiction_move, simplest=simplest_text, opposite=opposite_text,
            opposite_bundle="\n".join(f"- {e.describe()}" for e in opposite_bundle))
        if not contradiction_id:
            return "fallback"
        contradiction_text = state.get_contradiction(contradiction_id).unity_justification

        # 6. Resolution -- receives the contradiction (with its two sides).
        def resolution_move(answer):
            _nonempty(answer["resolution"], "resolution")
            _nonempty(answer.get("how_resolves"), "how_resolves")
            outcome = answer.get("outcome") if answer.get("outcome") in ("replacement", "mediation") else "replacement"
            return self._move(MoveType.PROPOSE_LEAP, {
                "contradiction_id": contradiction_id, "how_resolves": str(answer["how_resolves"]).strip(),
                "resolution_content": str(answer["resolution"]).strip(), "resolution_outcome": outcome},
                "The process that resolves the contradiction.")
        leap_pid, _ = await self._block(RESOLUTION, resolution_move, contradiction=contradiction_text,
                                        simplest=simplest_text, opposite=opposite_text)
        if not leap_pid:
            return "fallback"
        leap = next(r for r in state._resolution_relations.values() if r.resolution_process_id == leap_pid)

        # 7. Route -- built by the engine from the resolution.
        route = self._move(MoveType.BEGIN_EXECUTION, {
            "simplest_id": simplest.id, "contradiction_ids": [contradiction_id], "resolution_ids": [leap.id],
            "execution_process_ids": [leap.resolution_process_id]}, "Act on the resolution.")
        return "roadmap" if (await self.engine._submit(route, self.validator, self.goal, origin="block"))[0] else "fallback"
