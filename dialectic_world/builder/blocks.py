"""The builder's blocks, one per owner prompt (prompts/prompt_1.md .. prompt_6.md). Each block sends
its prompt file, filled with the world's current state, as a single user message; the code checks only
the FORM of the answer (JSON, required fields, enums, id cross-references) and re-asks on a violation,
up to `Settings.form_retries` -- no separate judge model anywhere in this chain."""
import json
import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Union

from dialectic_world.builder.prompts import load_prompt
from dialectic_world.config import Settings
from dialectic_world.llm.base import LLM
from dialectic_world.trace import Trace
from dialectic_world.world.model import (Contradiction, IterationRecord, OppositionCheck, Process,
                                         ComparisonRecord, Resolution, World, new_id)


class FormError(ValueError):
    """The answer does not have the form the block requires."""


class BlockFailed(RuntimeError):
    """A block got no well-formed answer within its retries."""


Tool = Callable[..., Union[str, Awaitable[str]]]


@dataclass
class Context:
    llm: LLM
    settings: Settings = field(default_factory=Settings)
    trace: Trace = field(default_factory=Trace)
    tools: dict[str, tuple[str, Tool]] = field(default_factory=dict)   # name -> (description, function)
    on_event: Optional[Callable[[str, dict], Awaitable[None]]] = None   # streaming hook, see A4


ABSENT = {"ru": "(не задан)", "en": "(none)"}

LABELS = {
    "ru": {
        "practical_link": "Практическая связь с предметом анализа",
        "why_initial": "Почему выбран исходным",
        "resolution_trace": "Признак предшествующего разрешения",
        "development_potential": "Потенциал дальнейшего развития",
        "rejected_header": "Уже отвергнутые кандидаты на P0",
        "transition": "Переход",
    },
    "en": {
        "practical_link": "Practical link to the subject of analysis",
        "why_initial": "Why chosen as initial",
        "resolution_trace": "Mark of a preceding resolution",
        "development_potential": "Potential for further development",
        "rejected_header": "Candidates for P0 already rejected",
        "transition": "Transition",
    },
}

LANGUAGE_NAMES = {"en": "English", "ru": "Russian"}


def _lang(ctx: Context) -> str:
    return ctx.settings.prompt_language if ctx.settings.prompt_language in LABELS else "ru"


def p0_text(p0: Process, lang: str = "ru") -> str:
    return f"{LABELS[lang]['transition']}: «{p0.source}» → «{p0.target}». {p0.statement}"


def p0_explanation_text(exp: dict, lang: str) -> str:
    lbl = LABELS[lang]
    return "\n".join(f"{lbl[k]}: {exp.get(k, '')}" for k in
                     ("practical_link", "why_initial", "resolution_trace", "development_potential"))


def opposite_text(opp: Process, explanation: dict) -> str:
    parts = [f"Переход: «{opp.source}» → «{opp.target}». {opp.statement}"]
    for key, label in (("shared_content_with_p0", "Общее с P0"), ("difference_from_p0", "Отличие от P0"),
                       ("replacement_of_p0", "Замещение P0"), ("exclusion_of_p0", "Исключение необходимости P0")):
        if explanation.get(key):
            parts.append(f"{label}: {explanation[key]}")
    return "\n".join(parts)


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise FormError("в ответе нет JSON-объекта")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise FormError(f"JSON не разбирается: {exc}") from exc
    if not isinstance(data, dict):
        raise FormError("ответ должен быть JSON-объектом")
    return data


def _text(data: dict, key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise FormError(f"поле {key!r} пустое или отсутствует")
    return value


def _tools_note(ctx: Context) -> str:
    if not ctx.tools:
        return ""
    listed = "\n".join(f"- {name}: {desc}" for name, (desc, _) in ctx.tools.items())
    return ("\n\nЕсли тебе для этого шага нужны факты, вызови инструмент: верни только "
            '{"tool": "<имя>", "args": {...}} — результат придёт следующим сообщением. Инструменты:\n' + listed)


async def _run_tool(ctx: Context, data: dict) -> str:
    name = str(data.get("tool"))
    if name not in ctx.tools:
        return f"Инструмента {name!r} нет. Доступны: {sorted(ctx.tools)}"
    fn = ctx.tools[name][1]
    try:
        result = fn(**(data.get("args") or {}))
        if hasattr(result, "__await__"):
            result = await result
        return str(result)[:6000]
    except Exception as exc:  # noqa: BLE001 -- a failing tool is reported to the block, not raised
        return f"Инструмента {name!r} завершился ошибкой: {type(exc).__name__}: {exc}"


def _language_directive(ctx: Context) -> str:
    lang = ctx.settings.output_language
    if not lang:
        return ""
    return f"\n\nAnswer in {LANGUAGE_NAMES.get(lang, lang)}."


async def ask(ctx: Context, block: str, prompt: str, parse: Callable[[dict], object], **where):
    """One block call: the prompt, tool calls if the block makes them, the form check with re-asks.
    Returns parse(answer); records every call in the trace; fires `ctx.on_event` on success."""
    content = f"[BLOCK {block}]\n\n" + prompt + _tools_note(ctx) + _language_directive(ctx)
    messages = [{"role": "user", "content": content}]
    tool_calls, form_errors = 0, []
    while True:
        started = time.monotonic()
        text = await ctx.llm.generate(messages)
        tokens = ctx.llm.last_call_usage
        try:
            data = extract_json(text)
            if "tool" in data and ctx.tools and tool_calls < ctx.settings.tool_calls_max:
                tool_calls += 1
                ctx.trace.event("block", block=block, ok=True, action="tool_call", answer=data, tokens=tokens,
                                model=ctx.llm.model, request_sha256=hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
                                seconds=round(time.monotonic() - started, 1), **where)
                result = await _run_tool(ctx, data)
                ctx.trace.event("tool", block=block, call=data, result=result[:1000], **where)
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": f"Результат инструмента:\n{result}\nПродолжи шаг."}]
                continue
            result = parse(data)
        except FormError as exc:
            form_errors.append(str(exc))
            ctx.trace.event("block", block=block, ok=False, error=str(exc), answer=text[:2000], tokens=tokens,
                            model=ctx.llm.model, request_sha256=hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
                            seconds=round(time.monotonic() - started, 1), **where)
            if len(form_errors) > ctx.settings.form_retries:
                raise BlockFailed(f"{block}: {'; '.join(form_errors)}") from exc
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"Ответ отклонён по форме: {exc}. Верни ответ заново в нужной форме."}]
            continue
        ctx.trace.event("block", block=block, ok=True, answer=data, tokens=tokens,
                        model=ctx.llm.model, request_sha256=hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
                        seconds=round(time.monotonic() - started, 1), **where)
        if ctx.on_event:
            await ctx.on_event(block, data)
        return result


# ---------------------------------------------------------------- FindP0 (prompt_1)

async def find_p0(ctx: Context, world: World, rejected: list[dict], extra_context: str = "") -> tuple[Process, dict, str, str]:
    """Returns (process, explanation, verdict, rejection_reason). Caller decides what to do with a
    "not_suitable" verdict -- this block does not retry on its own (economy: only one call)."""
    lang = _lang(ctx)
    parts = []
    if rejected:
        tried = "\n".join(f"- «{r['p0']}»: {r['reason']}" for r in rejected)
        parts.append(f"{LABELS[lang]['rejected_header']}:\n{tried}")
    if extra_context:
        parts.append(extra_context)
    context = "\n\n".join(parts) or ABSENT[lang]
    prompt = load_prompt("1", lang, subject=world.domain, context=context)

    def parse(data: dict):
        src, dst, st = _text(data, "from"), _text(data, "to"), _text(data, "statement")
        verdict = str(data.get("verdict") or "").strip()
        if verdict not in ("candidate", "not_suitable"):
            raise FormError(f"'verdict' — 'candidate' или 'not_suitable', получено {verdict!r}")
        explanation = {k: _text(data, k) for k in
                       ("practical_link", "why_initial", "resolution_trace", "development_potential")}
        reason = str(data.get("rejection_reason") or "").strip()
        if verdict == "not_suitable" and not reason:
            raise FormError("verdict='not_suitable', но 'rejection_reason' пуст")
        process = Process(id="P0", source=src, target=dst, statement=st, role="p0")
        return process, explanation, verdict, reason
    return await ask(ctx, "FindP0", prompt, parse)


# ---------------------------------------------------------------- BuildIteration (prompt_2)

def _expected_current(procs: list[dict], i: int) -> list[str]:
    return [p["id"] for p in procs[:i]]


async def build_iteration(ctx: Context, world: World, n: int, previous: Optional[IterationRecord],
                          extra_context: str = "") -> IterationRecord:
    lang = _lang(ctx)
    s = ctx.settings
    prev_text = ABSENT[lang] if n == 1 else json.dumps(previous.raw, ensure_ascii=False, indent=2)
    prompt = load_prompt("2", lang, subject=world.domain, p0=p0_text(world.p0, lang),
                         p0_explanation=p0_explanation_text(world.p0_explanation, lang),
                         iteration_number=str(n), previous_iteration=prev_text,
                         context=extra_context or ABSENT[lang])

    def parse(data: dict):
        if data.get("iteration") != n:
            raise FormError(f"'iteration' = {data.get('iteration')!r}, ожидалось {n}")
        expect_based_on = None if n == 1 else n - 1
        if data.get("based_on_iteration") != expect_based_on:
            raise FormError(f"'based_on_iteration' = {data.get('based_on_iteration')!r}, ожидалось {expect_based_on!r}")
        status = str(data.get("status") or "")
        if status not in ("ITERATION_BUILT", "DEVELOPMENT_FAILED"):
            raise FormError(f"недопустимый 'status': {status!r}")
        if status == "DEVELOPMENT_FAILED":
            raise FormError(f"DEVELOPMENT_FAILED: {data.get('failure_reason') or '(без объяснения)'}")
        procs = data.get("developing_processes")
        if not isinstance(procs, list) or not (s.developing_min <= len(procs) <= s.developing_max):
            got = len(procs) if isinstance(procs, list) else type(procs).__name__
            raise FormError(f"'developing_processes' должен быть списком из {s.developing_min}..{s.developing_max}, получено {got}")
        ids = []
        for i, p in enumerate(procs):
            expected_id = f"P{i + 1}"
            if not isinstance(p, dict) or p.get("id") != expected_id:
                raise FormError(f"процесс #{i}: id={p.get('id') if isinstance(p, dict) else p!r} != {expected_id!r}")
            for field_name in ("process", "development_relation", "reveals", "practical_significance", "relation_type"):
                if not str(p.get(field_name) or "").strip():
                    raise FormError(f"{expected_id}: поле {field_name!r} пустое или отсутствует")
            basis = p.get("basis") or {}
            if basis.get("p0") is not True:
                raise FormError(f"{expected_id}: 'basis.p0' должен быть true")
            expected_cur = _expected_current(procs, i)
            if basis.get("current_iteration_processes") != expected_cur:
                raise FormError(f"{expected_id}: 'basis.current_iteration_processes'={basis.get('current_iteration_processes')!r}, "
                                f"ожидалось {expected_cur!r}")
            expected_prev_whole = n > 1
            if bool(basis.get("previous_iteration_as_whole")) is not expected_prev_whole:
                raise FormError(f"{expected_id}: 'basis.previous_iteration_as_whole'={basis.get('previous_iteration_as_whole')!r}, "
                                f"ожидалось {expected_prev_whole!r} для итерации {n}")
            ids.append(expected_id)
        chain = data.get("development_chain")
        if chain != ["P0"] + ids:
            raise FormError(f"'development_chain'={chain!r} != {['P0'] + ids!r}")
        if not str(data.get("p0_revealed_content") or "").strip():
            raise FormError("'p0_revealed_content' пусто")
        if not str(data.get("iteration_practical_integrity") or "").strip():
            raise FormError("'iteration_practical_integrity' пусто")

        # prompt_2's developing processes carry a single "process" string, not a from/to pair like
        # prompt_1/5/6 -- unlike the old scheme, this prompt does not ask the model for an explicit
        # transition per Pi. `source`/`target` are left empty; `statement` holds the full text.
        pids = []
        for i, p in enumerate(procs):
            gid = new_id("P")
            derived = [world.p0.id] + pids[:i]
            if n > 1 and previous:
                derived += list(previous.developing)
            process = Process(id=gid, source="", target="", statement=p["process"], role="developing",
                              iteration=n, derived_from=derived)
            world.add(process)
            pids.append(gid)
        record = IterationRecord(n=n, based_on_iteration=expect_based_on, developing=pids,
                                 p0_revealed_content=data["p0_revealed_content"],
                                 iteration_practical_integrity=data["iteration_practical_integrity"], raw=data)
        return record
    return await ask(ctx, "BuildIteration", prompt, parse, iteration=n)


# ---------------------------------------------------------------- CompareDevelopment (prompt_3)

def _process_refs(world: World) -> set[str]:
    return {f"I{it.n}.P{k}" for it in world.iterations for k in range(1, len(it.developing) + 1)}

async def compare_development(ctx: Context, world: World, extra_context: str = "") -> ComparisonRecord:
    lang = _lang(ctx)
    iterations_text = "\n\n".join(
        f"Итерация {it.n}:\n{json.dumps(it.raw, ensure_ascii=False, indent=2)}" for it in world.iterations)
    prompt = load_prompt("3", lang, subject=world.domain, p0=p0_text(world.p0, lang),
                         p0_explanation=p0_explanation_text(world.p0_explanation, lang),
                         iterations=iterations_text, context=extra_context or ABSENT[lang])

    def parse(data: dict):
        status = str(data.get("status") or "")
        if status not in ("COMPARISON_COMPLETED", "COMPARISON_FAILED"):
            raise FormError(f"недопустимый 'status': {status!r}")
        if status == "COMPARISON_FAILED":
            raise FormError(f"COMPARISON_FAILED: {data.get('failure_reason') or '(без объяснения)'}")
        candidates = data.get("opposition_candidates")
        if not isinstance(candidates, list):
            raise FormError("'opposition_candidates' должен быть списком (может быть пустым)")
        for c in candidates:
            if not isinstance(c, dict) or not c.get("process_ref") or c.get("not_yet_proven") is not True:
                raise FormError(f"opposition_candidates: некорректный элемент {c!r} (нужен process_ref и not_yet_proven=true)")
            if c["process_ref"] not in _process_refs(world):
                raise FormError(f"неизвестный process_ref: {c['process_ref']!r}")
        return ComparisonRecord(iterations_analyzed=list(data.get("iterations_analyzed") or []),
                                opposition_candidates=candidates,
                                overall_development_pattern=str(data.get("overall_development_pattern") or ""),
                                raw=data)
    return await ask(ctx, "CompareDevelopment", prompt, parse, iteration=world.iterations[-1].n)


# ---------------------------------------------------------------- CheckOpposition (prompt_4)

async def check_opposition(ctx: Context, world: World, candidates: list[dict], extra_context: str = "") -> OppositionCheck:
    lang = _lang(ctx)
    iterations_text = "\n\n".join(
        f"Итерация {it.n}:\n{json.dumps(it.raw, ensure_ascii=False, indent=2)}" for it in world.iterations)
    comparison = world.comparisons[-1].raw if world.comparisons else {}
    prompt = load_prompt("4", lang, subject=world.domain, p0=p0_text(world.p0, lang),
                         p0_explanation=p0_explanation_text(world.p0_explanation, lang),
                         iterations=iterations_text, comparison=json.dumps(comparison, ensure_ascii=False, indent=2),
                         opposition_candidates=json.dumps(candidates, ensure_ascii=False, indent=2),
                         context=extra_context or ABSENT[lang])
    input_refs = {c["process_ref"] for c in candidates}

    def parse(data: dict):
        status = str(data.get("status") or "")
        if status not in ("OPPOSITION_CHECK_COMPLETED", "NO_OPPOSITION_CANDIDATES", "OPPOSITION_CHECK_FAILED"):
            raise FormError(f"недопустимый 'status': {status!r}")
        if status == "OPPOSITION_CHECK_FAILED":
            raise FormError(f"OPPOSITION_CHECK_FAILED: {data.get('failure_reason') or '(без объяснения)'}")
        checks = data.get("candidate_checks")
        if not isinstance(checks, list):
            raise FormError("'candidate_checks' должен быть списком")
        if not all(isinstance(c, dict) for c in checks):
            raise FormError("candidate_checks должен содержать объекты")
        checked_refs = {c.get("process_ref") for c in checks}
        if checked_refs != input_refs:
            raise FormError(f"candidate_checks покрывает {checked_refs}, а не входные кандидаты {input_refs}")
        for c in checks:
            result = c.get("result")
            if result not in ("OPPOSITE", "NOT_OPPOSITE", "UNDETERMINED"):
                raise FormError(f"{c.get('process_ref')}: недопустимый 'result' {result!r}")
            for section in ("shared_content", "difference", "exclusion_of_p0"):
                st = (c.get(section) or {}).get("status")
                if st not in ("ESTABLISHED", "NOT_ESTABLISHED", "UNCERTAIN"):
                    raise FormError(f"{c.get('process_ref')}.{section}.status недопустим: {st!r}")
            if result == "OPPOSITE":
                if (c.get("replacement") or {}).get("p0_still_required") is not False:
                    raise FormError(f"{c.get('process_ref')}: result=OPPOSITE, но replacement.p0_still_required != false")
                for section in ("shared_content", "difference", "exclusion_of_p0"):
                    if (c.get(section) or {}).get("status") != "ESTABLISHED":
                        raise FormError(f"{c.get('process_ref')}: result=OPPOSITE, но {section}.status != ESTABLISHED")
        confirmed = data.get("confirmed_opposites")
        if not isinstance(confirmed, list):
            raise FormError("'confirmed_opposites' должен быть списком")
        if not all(isinstance(c, dict) for c in confirmed):
            raise FormError("confirmed_opposites должен содержать объекты")
        confirmed_refs = {c.get("process_ref") for c in confirmed}
        opposite_refs = {c.get("process_ref") for c in checks if c.get("result") == "OPPOSITE"}
        if confirmed_refs != opposite_refs:
            raise FormError(f"'confirmed_opposites' {confirmed_refs} != кандидатов с result=OPPOSITE {opposite_refs}")
        return OppositionCheck(candidate_checks=checks, confirmed_opposites=confirmed, raw=data)
    return await ask(ctx, "CheckOpposition", prompt, parse)


# ---------------------------------------------------------------- FormContradiction (prompt_5)

async def form_contradiction(ctx: Context, world: World, opposite: Process, opposite_explanation: dict,
                             extra_context: str = "") -> Optional[Contradiction]:
    """Only called once a confirmed opposite exists -- code, not the prompt's own NO_CONFIRMED_OPPOSITES
    guard clause, is the primary control for "nothing to do here" (economy)."""
    lang = _lang(ctx)
    iterations_text = "\n\n".join(
        f"Итерация {it.n}:\n{json.dumps(it.raw, ensure_ascii=False, indent=2)}" for it in world.iterations)
    comparison = world.comparisons[-1].raw if world.comparisons else {}
    opposition_result = world.opposition_checks[-1].raw if world.opposition_checks else {}
    confirmed = [opposite_explanation]
    prompt = load_prompt("5", lang, subject=world.domain, p0=p0_text(world.p0, lang),
                         p0_explanation=p0_explanation_text(world.p0_explanation, lang),
                         iterations=iterations_text, comparison=json.dumps(comparison, ensure_ascii=False, indent=2),
                         opposition_result=json.dumps(opposition_result, ensure_ascii=False, indent=2),
                         confirmed_opposites=json.dumps(confirmed, ensure_ascii=False, indent=2),
                         context=extra_context or ABSENT[lang])

    def parse(data: dict):
        status = str(data.get("status") or "")
        if status not in ("CONTRADICTIONS_FORMED", "NO_CONFIRMED_OPPOSITES", "CONTRADICTION_FORMATION_FAILED"):
            raise FormError(f"недопустимый 'status': {status!r}")
        if status != "CONTRADICTIONS_FORMED":
            raise FormError(f"{status}: {data.get('failure_reason') or '(без объяснения)'}")
        contradictions = data.get("contradictions")
        if not isinstance(contradictions, list) or not contradictions:
            raise FormError("'contradictions' должен быть непустым списком при status=CONTRADICTIONS_FORMED")
        c = contradictions[0]
        if c.get("status") != "CONTRADICTION_FORMED":
            raise FormError(f"contradictions[0].status={c.get('status')!r} != CONTRADICTION_FORMED")
        statement = _text(c, "contradiction")
        unity = (c.get("unity") or {}).get("shared_content") or ""
        process = Process(id=new_id("C"), source=world.p0.statement, target=opposite.statement,
                          statement=statement, role="contradiction", derived_from=[world.p0.id, opposite.id])
        world.add(process)
        return Contradiction(process_id=process.id, unity=unity, raw=c)
    try:
        return await ask(ctx, "FormContradiction", prompt, parse)
    except BlockFailed:
        return None


# ---------------------------------------------------------------- ResolveLeap (prompt_6)

async def resolve_leap(ctx: Context, world: World, opposite: Process, opposite_explanation: dict,
                       extra_context: str = "") -> Optional[Resolution]:
    lang = _lang(ctx)
    iterations_text = "\n\n".join(
        f"Итерация {it.n}:\n{json.dumps(it.raw, ensure_ascii=False, indent=2)}" for it in world.iterations)
    previous_results = json.dumps({
        "comparison": world.comparisons[-1].overall_development_pattern if world.comparisons else "",
        "opposition_check": world.opposition_checks[-1].raw if world.opposition_checks else {},
    }, ensure_ascii=False, indent=2)
    prompt = load_prompt("6", lang, subject=world.domain, p0=p0_text(world.p0, lang), iterations=iterations_text,
                         opposite=opposite_text(opposite, opposite_explanation),
                         contradiction=json.dumps(world.contradiction.raw, ensure_ascii=False, indent=2),
                         previous_results=previous_results, context=extra_context or ABSENT[lang])

    def parse(data: dict):
        status = str(data.get("status") or "")
        if status not in ("CONTRADICTION_RESOLVED", "CONTRADICTION_MEDIATED", "LEAP_NOT_FOUND", "NO_CONTRADICTION"):
            raise FormError(f"недопустимый 'status': {status!r}")
        if status in ("LEAP_NOT_FOUND", "NO_CONTRADICTION"):
            return None
        leap = data.get("leap") or {}
        leap_type = leap.get("type")
        if status == "CONTRADICTION_RESOLVED":
            if leap_type != "REPLACEMENT":
                raise FormError(f"status=CONTRADICTION_RESOLVED, но leap.type={leap_type!r} != REPLACEMENT")
            if data.get("previous_p0_status") != "CONFIRMED_P0":
                raise FormError("REPLACEMENT найден, но 'previous_p0_status' != CONFIRMED_P0")
            kind = "replacement"
        else:
            if leap_type != "MEDIATION":
                raise FormError(f"status=CONTRADICTION_MEDIATED, но leap.type={leap_type!r} != MEDIATION")
            kind = "mediation"
        process_text = _text(leap, "process")
        explanation = leap.get("practical_basis") or leap.get("emerges_from_contradiction") or ""
        process = Process(id=new_id("R"), source=world.p0.statement, target=opposite.statement,
                          statement=process_text, role="resolution", derived_from=[world.contradiction.process_id])
        world.add(process)
        return Resolution(process_id=process.id, kind=kind, explanation=explanation, raw=data)
    return await ask(ctx, "ResolveLeap", prompt, parse)
