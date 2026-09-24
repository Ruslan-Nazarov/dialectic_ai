"""
dialectic_ai/engine/blocks.py

Block planning: a rigid block structure in which each block performs one element of the
dialectical analysis. The engine, not the model, fixes the order; each block is its own model call.

How a block works:
- it receives the compressed transfer ("carry") from the block before it -- by its nature that carry
  holds the development so far -- plus the items its own element needs;
- it solves its own element and returns the result with a new carry;
- on the way to the next block the result passes the JUDGE, which sees the whole chain built so far
  and the algorithm, and checks the result against both, with tolerance: the chain as a whole finds
  the place of each link, so only a clear violation is rejected. A rejected block is redone with the
  judge's reason.
Only the first block sees the task itself; it restates it as a process (the task's "what to do?"
otherwise got answered in every block).

The flow:
0. the task, stated as a process;
1. simplest: the process out of which the whole situation develops (e.g. "sales automation" for a
   request for an AI chatbot);
2. the simplest's development: a BUNDLE of developing processes, each developed in its own block,
   all toward the task's process;
3. opposite: chosen from that bundle -- an element whose own development does not require the
   simplest; linked to the development it was found in;
4. the opposite's development: its own bundle of processes;
5. contradiction: the simplest and the opposite with its development, in the unity of their
   development;
6. the contradiction's development: its own bundle of processes;
7. resolution: a process that replaces both by taking them in (replacement), or keeps the
   contradiction alive until it is resolved (mediation);
8. route: built by the engine from the resolution.

The simplest may not be found at once: a link's place is found through the whole chain. So the simplest
block first sketches, for its candidates, the whole analysis (development, opposite, contradiction,
resolution) and chooses the candidate whose chain holds; the sketch stays inside that block -- only
the simplest's judge sees it, and it goes to the trace, never to the next blocks. After the
contradiction the judge checks the chain as a whole. A candidate whose chain does not hold (a block or
bundle does not pass the judge, no opposite, no contradiction, or the whole-chain check fails) is
rolled back (the graph restored to before it) and the simplest block is asked for another one, told
which candidates failed and why -- up to SIMPLEST_ATTEMPTS.
The contradiction's development is kept in the chain and the trace, not in the graph: the graph's
development relations run between processes, and a contradiction is not one.
"""
import copy
import json
import re

from dialectic_ai.core.runtime import DesignationRole, MoveType, Proposal

MAX_ATTEMPTS = 3
SIMPLEST_ATTEMPTS = 3   # candidates for the simplest, each checked by whether it reaches a contradiction
NO_OPPOSITE = "no element of its development was independent of it (no opposite)"
BUNDLE_MAX = 5          # elements per bundle: enough to find the opposite, bounded for cost
ELEMENT_STEPS_MAX = 3   # how far one element is developed in its own block

CARRY = ('\nAlso return "carry": the development so far in 2-4 sentences -- compressed from what you received and '
         'ending with your own result. It is all the next block receives.')

METHOD = """- The task is stated as a process; the analysis explains that process by its development.
- Development: a subsequent process arises out of an initial one in which it was contained potentially, and the
  initial one becomes more definite as it arises; abstract to concrete. A transition of one into another, not a
  juxtaposition of one and another (that is change, not development).
- Simplest: connected to the task's process; the processes developing out of it, taken toward their totality,
  describe the task's process; each of them stays connected to it. It may not be found at once.
- The development of the simplest is a bundle of developing processes: an abstract process can pass into several
  concrete ones. The development of the opposite and of the contradiction are bundles of processes too.
- Opposite: found among the developing processes; its development excludes the existence of the simplest -- does
  not require the simplest (which is not the same as destroying it).
- Contradiction: the simplest and the opposite taken in the unity of their development.
- Resolution: a leap, explained as the resolution of this contradiction -- a process that replaces the simplest and
  the opposite by taking them into its own development, or one that lets the contradiction go on existing until it
  is resolved by such a process."""

DUTIES = {
    "SIMPLEST": "the simplest process of the task's process",
    "BUNDLE": "the processes developing out of the given process toward the task's process",
    "ELEMENT": "the development of one element of a bundle: a transition from process to process",
    "OPPOSITE": "the opposite, chosen from the simplest's bundle",
    "CONTRADICTION": "the simplest and the opposite in the unity of their development",
    "RESOLUTION": "the process that resolves the contradiction",
    "CHAIN": ("the chain as a whole, up to the contradiction: the simplest develops toward the task's process, the "
              "opposite is found in that development and does not require the simplest, and the contradiction is "
              "their unity in development"),
}

JUDGE = """You check one block of a dialectical analysis before its result is passed on to the next block.
The analysis follows this algorithm:
{method}

The chain built so far:
{chain}

This block: {block} -- {duty}.
Its result:
{result}

Does the result follow from the chain so far and fulfil this block's element of the algorithm? Allow tolerance:
the chain as a whole finds the place of each link, so reject only a clear violation -- e.g. a solution or a
measure instead of a process, a list of properties instead of a transition, a side topic that has left the
task's process, a choice between two options instead of a contradiction, a compromise or a combination of both
sides instead of a resolution. Say what to correct.
Return only JSON: {{"accepted": true or false, "reason": "..."}}"""

REQUEST = """State this task as a PROCESS: the process the task is ABOUT -- what goes on in the matter itself --
not a question, and not someone asking, deciding, evaluating or handling it. Keep the whole situation the task
states, as it is given, before anything is done about it: do not reduce it to one of its parts, and never put the
answer to the task's question into it. One short sentence; no steps and no plan of what to do.
Examples (other tasks):
- "Pythagoras' theorem" -> "to get the square of the hypotenuse of a right triangle, add the squares of the legs"
- "Should we let our employees work from home?" -> "employees work from home" (not "a company decides whether...")
- "Our website is slow on phones; how do we fix it?" -> "the site loads slowly on phones"
Also say whether the task needs dialectical development at all. A plain question of fact or definition answered
directly (a capital city, 2 + 2, what a word means) does not; answer "needs_development": false only for those.
Task: {task}
Answer in the task's language. Return only JSON: {{"process": "...", "needs_development": true or false}}{feedback}"""

SIMPLEST = """Find the SIMPLEST process for this process: the process out of which the whole of it develops. It is
connected to this process; the processes that develop out of it, taken toward their totality, describe this
process; and each of them stays connected to it. It is simpler than this process -- not this process restated,
not its outcome, not a solution.
Examples: "to get the square of the hypotenuse, add the squares of the legs" -> "a triangle" (a triangle gives a set
of triangles, which gives the squares; the area arises out of the triangle). "a business wants an AI chatbot so
clients call support less" -> "sales automation" (it develops into automating contact with clients, then answering
typical questions automatically, and so into wanting a bot; "clients call support" would not do: the wish for a bot
does not arise out of it).
Before naming it, sketch the whole analysis for two or three candidates: what develops out of each toward this
process, which of those developing processes is its opposite (its development does not require the candidate),
what contradiction they form, and what resolves it. Choose the candidate whose sketch holds together best -- it
develops into this process as a whole and reaches a real contradiction. The sketch is only for your choice: the
carry must not contain it.
Process: {process}{tried}
Answer in the process's language. Return only JSON: {{"sketch": "the candidates and their chains, briefly",
"simplest": "...", "carry": "..."}}{carry_note}{feedback}"""

BUNDLE = """Name the processes through which this process develops toward the target -- the elements of its
development. Each arises out of this process's own content, where it was contained potentially, and as it arises
this process becomes more definite; each is a part of the way to the target, and together they approach the whole
target (as a triangle gives a set of triangles and the squares on the way to the theorem). Processes: not
properties, not side topics, not what someone does to handle it (steps, procedures, measures). 3 to {limit}.
Process: {subject}
Target: {target}
Received from the previous block: {carry}
Same language. Return only JSON: {{"elements": ["...", "..."], "carry": "..."}}{carry_note}{feedback}"""

ELEMENT = """Develop this element of the process's development toward the target: how it arises out of the process,
and what arises out of it in turn, coming closer to the target. 1 to {steps} steps. Each next one arises out of the
previous one's own content, where it was contained (as the squares arise out of a set of triangles), and the
previous one becomes more definite by it -- a transition, not a list. Stay within the matter of the target; not
stages of the same thing becoming more formal or organized, and not phases of a procedure.
Process: {subject}
Element: {element}
Target: {target}
Received from the previous block: {carry}
Same language. Return only JSON: {{"steps": [{{"process": "...", "how_it_arises": "..."}}, ...], "carry": "..."}}{carry_note}{feedback}"""

OPPOSITE = """Here is a simplest process and the bundle of its development. Choose the OPPOSITE from the bundle: an
element whose own development does not require the simplest -- it excludes the simplest's existence without
destroying it (it could go on developing even if the simplest were not there).
Example: simplest "cold food", bundle includes "heating of food" -- heating develops whether or not this food is
cold, so it is the opposite. Not an alternative way to the same goal or another way of handling the situation, not
a negation.
If no element is like that, answer number 0.
Simplest: {simplest}
Bundle (each element with what its block passed on):
{bundle}
Return only JSON: {{"number": n, "independence": "why its development does not require the simplest", "carry": "..."}}{carry_note}{feedback}"""

CONTRADICTION = """State the contradiction: the simplest and its opposite with the bundle of its development, taken in
the unity of their development -- how they develop together while one does not need the other. Not a choice
between two options, and not two approaches to handling the situation (prevention vs reaction, a rule vs a tool).
Simplest: {simplest}
Opposite: {opposite}
Its development:
{opposite_bundle}
Received from the previous block: {carry}
Return only JSON: {{"contradiction": "...", "unity_of_development": "...", "carry": "..."}}{carry_note}{feedback}"""

RESOLUTION = """Resolve this contradiction: find the process that resolves it. Either a process that REPLACES the
simplest and the opposite by taking both into its own development ("replacement"), or a process that lets the
contradiction keep existing until it is resolved ("mediation"). Explain it as the resolution of this
contradiction. Not a compromise or hybrid of two options, not an "integrated system" that merely combines what both
sides do, not a recommendation of what someone should do.
Example: cold food and heating -> "heating of the cold food" (replacement: it takes in both).
Example: a student's essay and AI writing -> "the work can no longer be evaluated as the student's" (replacement).
Contradiction: {contradiction}
Its development:
{contradiction_bundle}
Simplest: {simplest}
Opposite: {opposite}
Received from the previous block: {carry}
Return only JSON: {{"resolution": "...", "how_resolves": "how it takes in both, or keeps them together",
"outcome": "replacement" or "mediation"}}{feedback}"""


def _json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    return json.loads(match.group(0))


def _text(answer: dict, key: str) -> str:
    value = str(answer[key] or "").strip()
    if not value:
        raise ValueError(f"{key} is empty")
    return value


def _carry(answer, default: str) -> str:
    return str((answer or {}).get("carry") or "").strip() or default


class Element:
    """One element of a bundle: its process in the graph (none for the contradiction's bundle), the
    chain it developed into, and what its block passed on."""

    def __init__(self, text, relation_id=None, process_id=None):
        self.text, self.relation_id, self.process_id = text, relation_id, process_id
        self.steps = []           # [(relation_id, process_id, text), ...]
        self.carry = text

    @property
    def relation_ids(self):
        return [r for r in [self.relation_id] + [r for r, _, _ in self.steps] if r]

    def describe(self):
        return self.text + (" -> " + " -> ".join(t for _, _, t in self.steps) if self.steps else "")


class Bundle:
    def __init__(self, elements, carry):
        self.elements, self.carry = elements, carry

    def listed(self, numbered=False):
        return "\n".join(f"{f'{i}.' if numbered else '-'} {e.describe()}" + (f" | {e.carry}" if e.carry != e.text else "")
                         for i, e in enumerate(self.elements, 1))


class BlockPlanner:
    """Runs the blocks in their fixed order; every block's result passes the judge before it is
    passed on, and its moves are committed to the graph (structure only -- the judge has already seen
    the content)."""

    def __init__(self, engine, semantic_validator, goal):
        self.engine = engine
        self.validator = semantic_validator
        self.goal = goal
        self.llm = engine.agent.llm
        self.judge_llm = getattr(semantic_validator, "llm", None)
        self.chain = []

    async def _ask(self, template: str, feedback: str, **fields) -> dict:
        note = f"\n\nYour previous answer was rejected: {feedback}\nCorrect exactly that." if feedback else ""
        reply = await self.llm.generate([{"role": "user", "content": template.format(
            feedback=note, carry_note=CARRY, **fields)}])
        return _json(reply)

    async def _judge(self, block: str, result: str):
        """The judge between blocks: None when the result may pass on, else the reason. With no judge
        model (or when it is unavailable) the result passes."""
        if self.judge_llm is None:
            return None
        prompt = JUDGE.format(method=METHOD, chain="\n".join(self.chain) or "(nothing yet)", block=block,
                              duty=DUTIES[block], result=result)
        try:
            verdict = _json(await self.judge_llm.generate([{"role": "user", "content": prompt}]))
        except Exception as exc:
            await self.engine.logger.trace_event("block_judge_unavailable", {
                "run_id": self.engine.run_id, "block": block, "error": f"{type(exc).__name__}: {exc}"[:300]})
            return None
        if verdict.get("accepted") is False:
            return str(verdict.get("reason") or "rejected by the judge").strip()
        return None

    async def _block(self, block: str, template: str, render, **fields):
        """One block: ask, render the result (raises ValueError on a malformed answer; None means
        "nothing to pass on", e.g. no opposite), pass it through the judge, redo with the reason. `render`
        may return (for_the_judge, for_the_chain) when the judge should see more than goes on.
        Returns (answer, None) when accepted or empty, else (last_answer, reason)."""
        feedback, answer = "", None
        for _ in range(MAX_ATTEMPTS):
            try:
                answer = await self._ask(template, feedback, **fields)
                result = render(answer)
            except (ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
                feedback = f"the answer was not in the required form ({exc})"
                continue
            if result is None:
                return answer, None
            judged, chained = result if isinstance(result, tuple) else (result, result)
            reason = await self._judge(block, judged)
            await self.engine.logger.trace_event("block", {"run_id": self.engine.run_id, "block": block,
                                                           "result": judged, "carry": _carry(answer, ""),
                                                           "judge": reason or "accepted"})
            if reason is None:
                self.chain.append(f"{block}: {chained}")
                return answer, None
            feedback = f"the judge: {reason}"
        return answer, feedback or "no answer"

    @staticmethod
    def _move(move_type, payload, why):
        return Proposal(move_type=move_type, payload=payload, why_this_move_now=why,
                        expected_goal_contribution="One block of the dialectical analysis.")

    async def _commit(self, move_type, payload, why):
        return await self.engine._submit(self._move(move_type, payload, why), None, self.goal, origin="block")

    def _designation(self, role):
        return next((d for d in self.engine.state.get_all_designations() if d.role == role), None)

    async def _develop_step(self, source_id, source_text, text, how):
        result_id, _ = await self._commit(MoveType.DEVELOP_PROCESS, {
            "source_process_id": source_id, "emergent_content": text,
            "potential_containment": f"Contained in: {source_text}", "emergence": how,
            "concretization": text, "new_content": how}, "A process developing out of its source.")
        if not result_id:
            return None
        relation = next(r for r in self.engine.state.get_all_development_relations() if r.emergent_process_id == result_id)
        return relation.id, result_id

    async def _bundle(self, name: str, process_id, subject: str, target: str, carry: str):
        """A bundle of development: the elements (one block), then each element developed in its own
        block. process_id None keeps the bundle out of the graph (the contradiction's development).
        Returns (Bundle, None) or (None, reason)."""
        def render(answer):
            texts = [str(e).strip() for e in answer["elements"] if str(e).strip()][:BUNDLE_MAX]
            if len(texts) < 2:
                raise ValueError("the bundle needs at least 2 elements")
            return f"{name}: {subject} develops into: " + "; ".join(texts)
        answer, reason = await self._block("BUNDLE", BUNDLE, render, subject=subject, target=target, limit=BUNDLE_MAX,
                                           carry=carry)
        if reason:
            return None, f"its development ({name}) did not pass: {reason}"
        texts = [str(e).strip() for e in answer["elements"] if str(e).strip()][:BUNDLE_MAX]
        bundle_carry = _carry(answer, f"{subject} develops into: " + "; ".join(texts))
        elements = []
        for text in texts:
            if process_id is None:
                elements.append(Element(text))
                continue
            committed = await self._develop_step(process_id, subject, text, f"Develops out of: {subject}")
            if committed:
                elements.append(Element(text, *committed))
        for element in elements:
            def render_steps(a, element=element):
                steps = [str(s.get("process", "")).strip() for s in a["steps"][:ELEMENT_STEPS_MAX]]
                if not any(steps):
                    raise ValueError("steps are empty")
                return f"{name}, element '{element.text}': " + " -> ".join([element.text] + [s for s in steps if s])
            steps_answer, reason = await self._block("ELEMENT", ELEMENT, render_steps, subject=subject,
                                                     element=element.text, target=target, carry=bundle_carry,
                                                     steps=ELEMENT_STEPS_MAX)
            if reason:
                continue   # the element stays, undeveloped
            element.carry = _carry(steps_answer, element.text)
            source_id, source_text = element.process_id, element.text
            seen = {subject.casefold(), element.text.casefold()}
            for step in steps_answer["steps"][:ELEMENT_STEPS_MAX]:
                text = str(step.get("process", "")).strip()
                if not text or text.casefold() in seen:   # a repeat is not a development
                    continue
                seen.add(text.casefold())
                if process_id is None:
                    element.steps.append((None, None, text))
                    continue
                committed = await self._develop_step(source_id, source_text, text, str(step.get("how_it_arises") or text))
                if not committed:
                    break
                element.steps.append((*committed, text))
                source_id, source_text = committed[1], text
        if not elements:
            return None, f"its development ({name}) could not be committed"
        return Bundle(elements, bundle_carry), None

    async def plan(self) -> str:
        """Returns "roadmap" (route accepted), "no_contradiction" (hand over for the clear path), or
        "fallback" (a block could not be committed; the regular actor continues from this state)."""
        # 0. The task as a process -- the only block that sees the task itself.
        request, feedback = None, ""
        for _ in range(MAX_ATTEMPTS):
            try:
                request = await self._ask(REQUEST, feedback, task=self.goal.content)
                _text(request, "process")
                break
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                request, feedback = None, f"the answer was not in the required form ({exc})"
        if request is None:
            return "fallback"
        task_process = str(request["process"]).strip()
        plain_question = request.get("needs_development") is False
        await self.engine.logger.trace_event("task_process", {"run_id": self.engine.run_id, "process": task_process,
                                                              "needs_development": not plain_question})

        if plain_question:
            pid, _ = await self.engine._submit(self._move(MoveType.PROPOSE_SIMPLEST, {"content": task_process},
                                                          "A plain question: nothing to develop."),
                                               self.validator, self.goal, origin="block")
            if not pid:
                return "fallback"
            candidate = next(d for d in self.engine.state.get_all_designations() if d.process_id == pid)
            ok, _ = await self.engine._submit(self._move(MoveType.ASSESS_SIMPLEST, {
                "candidate_simplest_id": candidate.id, "approved": True}, "A plain question: nothing to develop."),
                self.validator, self.goal, origin="block")
            return "no_contradiction" if ok else "fallback"

        # Blocks 1-8 per candidate simplest; a candidate that does not reach a contradiction is rolled back.
        tried, reason = [], None
        for attempt in range(1, SIMPLEST_ATTEMPTS + 1):
            saved = copy.deepcopy(self.engine.state)
            outcome, simplest_text, reason = await self._attempt(task_process, tried)
            if outcome is not None:
                return outcome
            tried.append((simplest_text, reason))
            await self.engine.logger.trace_event("simplest_retry", {"run_id": self.engine.run_id, "attempt": attempt,
                                                                    "simplest": simplest_text, "reason": reason})
            if attempt < SIMPLEST_ATTEMPTS:
                self.engine.state = saved
        return "no_contradiction" if reason == NO_OPPOSITE else "fallback"

    async def _attempt(self, task_process, tried):
        """Blocks 1-8 for one candidate simplest. Returns (outcome, None, None) once the analysis reached
        a contradiction or failed for another cause ("roadmap" or "fallback"), or (None, simplest_text,
        reason) when this candidate failed as the simplest."""
        state = self.engine.state
        self.chain = [f"TASK PROCESS: {task_process}"]
        tried_note = "".join(f'\nTried before, not the simplest: "{text}" -- {why}' for text, why in tried)
        if tried_note:
            tried_note += "\nFind a different simplest."

        # 1. Simplest -- receives the task's process; its sketch of the whole chain goes to its judge only.
        def render_simplest(a):
            simplest = _text(a, "simplest")
            sketch = str(a.get("sketch") or "").strip()
            return (f"{simplest}\n(the sketch behind this choice: {sketch})" if sketch else simplest), simplest
        answer, reason = await self._block("SIMPLEST", SIMPLEST, render_simplest, process=task_process,
                                           tried=tried_note)
        simplest_text = str((answer or {}).get("simplest") or "").strip()
        if reason:
            return None, simplest_text, f"it did not pass as the simplest: {reason}"
        pid, _ = await self._commit(MoveType.PROPOSE_SIMPLEST, {"content": simplest_text},
                                    "The process out of which the whole situation develops.")
        if not pid:
            return "fallback", None, None
        candidate = next(d for d in state.get_all_designations() if d.process_id == pid)
        if not (await self._commit(MoveType.ASSESS_SIMPLEST, {"candidate_simplest_id": candidate.id, "approved": True},
                                   "The candidate is the simplest process of the task."))[0]:
            return "fallback", None, None
        simplest = self._designation(DesignationRole.SIMPLEST)
        carry = _carry(answer, simplest_text)

        # 2. The simplest's development -- a bundle toward the task's process.
        bundle, reason = await self._bundle("the simplest's development", simplest.process_id, simplest_text,
                                            task_process, carry)
        if reason:
            return None, simplest_text, reason

        # 3. Opposite -- chosen from the bundle; linked to the development it was found in.
        def render_opposite(a):
            number = int(a["number"])
            if number == 0:
                return None
            if not 1 <= number <= len(bundle.elements):
                raise ValueError(f"number must be 1..{len(bundle.elements)} or 0")
            return (f"opposite: {bundle.elements[number - 1].text} -- its development does not require the simplest: "
                    f"{_text(a, 'independence')}")
        answer, reason = await self._block("OPPOSITE", OPPOSITE, render_opposite, simplest=simplest_text,
                                           bundle=bundle.listed(numbered=True))
        if reason:
            return None, simplest_text, f"no opposite passed in its development: {reason}"
        if int(answer["number"]) == 0:
            return None, simplest_text, NO_OPPOSITE
        element = bundle.elements[int(answer["number"]) - 1]
        opposite_pid, why = await self._commit(MoveType.DESIGNATE_OPPOSITE, {
            "simplest_id": simplest.id, "context_id": element.relation_id, "content": element.text,
            "independence": str(answer["independence"]).strip(),
            "justification": f"An element of the simplest's development: {element.describe()}"},
            "An element of the bundle whose development does not require the simplest.")
        if not opposite_pid:
            return None, simplest_text, f"the opposite could not be committed: {why}"
        opposite = self._designation(DesignationRole.OPPOSITE)
        opposite_text = element.text
        carry = _carry(answer, f"{simplest_text}; its opposite: {opposite_text}")

        # 4. The opposite's development -- its own bundle.
        opposite_bundle, reason = await self._bundle("the opposite's development", opposite.process_id, opposite_text,
                                                     task_process, carry)
        if reason:
            return None, simplest_text, reason

        # 5. Contradiction -- the simplest and the opposite with its development.
        answer, reason = await self._block(
            "CONTRADICTION", CONTRADICTION, lambda a: _text(a, "contradiction"), simplest=simplest_text,
            opposite=opposite_text, opposite_bundle=opposite_bundle.listed(), carry=opposite_bundle.carry)
        if reason:
            return None, simplest_text, f"it and the opposite did not form a contradiction: {reason}"
        contradiction_text = str(answer["contradiction"]).strip()
        contradiction_id, why = await self._commit(MoveType.ESTABLISH_CONTRADICTION, {
            "simplest_id": simplest.id, "opposite_id": opposite.id,
            "simplest_dev_ref_ids": [element.relation_id],
            "opposite_dev_ref_ids": [r for e in opposite_bundle.elements for r in e.relation_ids],
            "unity_justification": contradiction_text,
            "developing_unity_description": str(answer.get("unity_of_development") or contradiction_text)},
            "The simplest and the opposite in the unity of their development.")
        if not contradiction_id:
            return None, simplest_text, f"the contradiction could not be committed: {why}"
        carry = _carry(answer, contradiction_text)

        # The whole chain, up to the contradiction, must hold -- else the simplest was not the simplest.
        reason = await self._judge("CHAIN", "(the chain above)")
        await self.engine.logger.trace_event("block", {"run_id": self.engine.run_id, "block": "CHAIN",
                                                       "result": "", "carry": "", "judge": reason or "accepted"})
        if reason:
            return None, simplest_text, f"the chain built on it does not hold: {reason}"

        # 6. The contradiction's development -- a bundle of processes (kept in the chain, not the graph).
        contradiction_bundle, reason = await self._bundle("the contradiction's development", None, contradiction_text,
                                                          task_process, carry)
        if contradiction_bundle:
            listed, carry = contradiction_bundle.listed(), contradiction_bundle.carry
        else:
            listed = "(not developed)"

        # 7. Resolution -- receives the contradiction with its development.
        def render_resolution(a):
            return (f"resolution ({a.get('outcome')}): {_text(a, 'resolution')} -- {_text(a, 'how_resolves')}")
        answer, reason = await self._block("RESOLUTION", RESOLUTION, render_resolution, contradiction=contradiction_text,
                                           contradiction_bundle=listed, simplest=simplest_text,
                                           opposite=opposite_text, carry=carry)
        if reason:
            return "fallback", None, None
        outcome = answer.get("outcome") if answer.get("outcome") in ("replacement", "mediation") else "replacement"
        leap_pid, _ = await self._commit(MoveType.PROPOSE_LEAP, {
            "contradiction_id": contradiction_id, "how_resolves": str(answer["how_resolves"]).strip(),
            "resolution_content": str(answer["resolution"]).strip(), "resolution_outcome": outcome},
            "The process that resolves the contradiction.")
        if not leap_pid:
            return "fallback", None, None
        leap = next(r for r in state._resolution_relations.values() if r.resolution_process_id == leap_pid)

        # 8. Route -- built by the engine from the resolution (the route itself still goes to the judge).
        route = self._move(MoveType.BEGIN_EXECUTION, {
            "simplest_id": simplest.id, "contradiction_ids": [contradiction_id], "resolution_ids": [leap.id],
            "execution_process_ids": [leap.resolution_process_id]}, "Act on the resolution.")
        accepted = (await self.engine._submit(route, self.validator, self.goal, origin="block"))[0]
        return ("roadmap" if accepted else "fallback"), None, None
