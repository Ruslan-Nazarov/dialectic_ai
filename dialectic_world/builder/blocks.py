"""The builder's blocks (architecture section 4). Each block is one step of the algorithm: its own prompt
quoting its own clauses, its own input, its own answer schema and form check. The code, not the model,
decides which block runs when; a block's model call does only its own step.

No judge: the code checks only the FORM of an answer (JSON, required fields, a process written as a
transition, references to existing ids, limits). A malformed answer is re-asked with the reason."""
import json
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Union

from dialectic_world.config import Settings
from dialectic_world.llm.base import LLM
from dialectic_world.method import clauses
from dialectic_world.trace import Trace
from dialectic_world.world.model import Comparison, Process, World, new_id


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
    carry: str = ""        # the compressed transfer from the previous block (architecture 2.4)


CARRY_FIELD = '"carry": "передача следующему блоку: 1-3 предложения — сжатое развитие до этого места, включая твой результат"'
TRANSITION_RULE = ('Каждый процесс записывается как переход одного процесса в другой (п. 1.1): "from" — процесс, который '
                   'переходит, "to" — процесс, в который он переходит, "statement" — краткая формулировка перехода.')


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


def transition(data: dict) -> tuple[str, str, str]:
    return _text(data, "from"), _text(data, "to"), _text(data, "statement")


def _ids(data: dict, key: str, allowed: set[str], name: str) -> list[str]:
    values = data.get(key) or []
    if not isinstance(values, list):
        raise FormError(f"{key!r} должен быть списком id")
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise FormError(f"{key!r}: нет таких {name}: {unknown}; допустимы {sorted(allowed)}")
    return [str(v) for v in values]


def _tools_note(ctx: Context) -> str:
    if not ctx.tools:
        return ""
    listed = "\n".join(f"- {name}: {desc}" for name, (desc, _) in ctx.tools.items())
    return ("\nЕсли тебе для этого шага нужны факты, вызови инструмент: верни только "
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
        return f"Инструмент {name!r} завершился ошибкой: {type(exc).__name__}: {exc}"


async def ask(ctx: Context, block: str, prompt: str, parse: Callable[[dict], object], **where):
    """One block call: the prompt, tool calls if the block makes them, the form check with re-asks.
    Returns parse(answer); records every call in the trace."""
    messages = [{"role": "user", "content": prompt + _tools_note(ctx)}]
    tool_calls, form_errors = 0, []
    while True:
        started, before = time.monotonic(), (ctx.llm.usage.prompt_tokens, ctx.llm.usage.completion_tokens)
        text = await ctx.llm.generate(messages)
        tokens = (ctx.llm.usage.prompt_tokens - before[0], ctx.llm.usage.completion_tokens - before[1])
        try:
            data = extract_json(text)
            if "tool" in data and ctx.tools and tool_calls < ctx.settings.tool_calls_max:
                tool_calls += 1
                result = await _run_tool(ctx, data)
                ctx.trace.event("tool", block=block, call=data, result=result[:1000], **where)
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": f"Результат инструмента:\n{result}\nПродолжи шаг."}]
                continue
            result = parse(data)
        except FormError as exc:
            form_errors.append(str(exc))
            ctx.trace.event("block", block=block, ok=False, error=str(exc), answer=text[:2000], tokens=tokens,
                            seconds=round(time.monotonic() - started, 1), **where)
            if len(form_errors) > ctx.settings.form_retries:
                raise BlockFailed(f"{block}: {'; '.join(form_errors)}") from exc
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"Ответ отклонён по форме: {exc}. Верни ответ заново в нужной форме."}]
            continue
        ctx.trace.event("block", block=block, ok=True, answer=data, tokens=tokens,
                        seconds=round(time.monotonic() - started, 1), prompt=prompt, **where)
        if isinstance(data.get("carry"), str) and data["carry"].strip():
            ctx.carry = data["carry"].strip()
        return result


# ---------------------------------------------------------------- FindP0 (А 3, 3.1)

async def find_p0(ctx: Context, world: World, rejected: list[dict]) -> tuple[Process, str]:
    tried = "".join(f"\nУже отвергнуто: «{r['p0']}» — {r['reason']}" for r in rejected)
    prompt = f"""[БЛОК FindP0] Ты выполняешь один шаг диалектического алгоритма: находишь простейший процесс P0 области.
Пункты алгоритма:
{clauses("1", "1.1", "2.1", "3", "3.1", "3.2", "3.3")}

Область: {world.domain}{tried}

Задание: назови простейший процесс P0 этой области. {TRANSITION_RULE} Укажи, разрешением какого противоречия
(каким скачком) получен P0 (п. 3.1). Отвечай на языке описания области.
Верни только JSON: {{"from": "...", "to": "...", "statement": "...", "from_leap": "...", {CARRY_FIELD}}}"""

    def parse(data):
        src, dst, st = transition(data)
        return Process(id="P0", source=src, target=dst, statement=st, role="p0", bundle="p0"), \
            str(data.get("from_leap") or "").strip()
    return await ask(ctx, "FindP0", prompt, parse)


# ---------------------------------------------------------------- NextDeveloping (А 4.1-4.3)

ROOT_LABEL = {"p0": "простейший процесс P0",
              "opposite": "противоположный процесс — он принимается за простейший процесс этого пучка",
              "contradiction": "противоречие — оно принимается за простейший процесс этого пучка"}


async def next_developing(ctx: Context, world: World, bundle: str, root: Process, n: int, got_now: int,
                          changes: str = "", agent_data: str = "") -> tuple[Process, bool]:
    s = ctx.settings
    earlier = world.all_developing(bundle)
    listed = "\n".join(p.line() for p in earlier) or "(пока нет)"
    allowed = {root.id} | {p.id for p in earlier}
    extra = (f"\nЧто меняется на этой итерации (решено при сравнении): {changes}" if changes else "") + \
            (f"\nНовые данные от агента, которые мир должен учесть: {agent_data}" if agent_data else "")
    prompt = f"""[БЛОК NextDeveloping] Ты выполняешь один шаг диалектического алгоритма: находишь ОДИН следующий развивающий процесс.
Пункты алгоритма:
{clauses("2.1", "4", "4.1", "4.2", "4.3", "4.4", "9")}

Корень пучка ({ROOT_LABEL[bundle]}):
{root.line()}
Развивающие процессы, уже полученные (эта и прошлые итерации):
{listed}
Итерация {n}. На этой итерации уже получено новых: {got_now}; всего на итерации нужно от {s.developing_min} до {s.developing_max}.{extra}
Передача от предыдущего блока: {ctx.carry or "(нет)"}

Задание: назови следующий развивающий процесс — он вытекает из корня и уже полученных развивающих процессов
(п. 4.2) и показывает переход, а не рядоположенность (п. 9). {TRANSITION_RULE} В "derived_from" — id, из
которых он вытекает (из списка выше или id корня). "more" — нужен ли на этой итерации ещё один процесс после этого.
Отвечай на языке корня.
Верни только JSON: {{"from": "...", "to": "...", "statement": "...", "derived_from": ["..."], "more": true, {CARRY_FIELD}}}"""

    def parse(data):
        src, dst, st = transition(data)
        derived = _ids(data, "derived_from", allowed, "процессов")
        if not derived:
            raise FormError("'derived_from' пуст: процесс должен из чего-то вытекать (п. 4.2)")
        p = Process(id=new_id("P"), source=src, target=dst, statement=st, role="developing", bundle=bundle,
                    iteration=n, derived_from=derived)
        return p, bool(data.get("more"))
    return await ask(ctx, "NextDeveloping", prompt, parse, bundle=bundle, iteration=n)


# ---------------------------------------------------------------- Internals (А 4.5)

async def internals(ctx: Context, world: World, bundle: str, dev: Process, n: int, previous: list[Process],
                    agent_data: str = "", carry: str = "") -> list[Process]:
    s = ctx.settings
    prev = "\n".join(p.line() for p in previous) or "(прошлой итерации нет)"
    allowed = {p.id for p in previous}
    extra = f"\nНовые данные от агента, которые мир должен учесть: {agent_data}" if agent_data else ""
    prompt = f"""[БЛОК Internals] Ты выполняешь один шаг диалектического алгоритма: находишь внутренние процессы одного развивающего процесса.
Пункты алгоритма:
{clauses("2.1", "4.5", "9")}

Развивающий процесс (принимается за простейший):
{dev.line()}
Его внутренние процессы на прошлой итерации:
{prev}{extra}
Передача от предыдущего блока: {carry or "(нет)"}

Задание: найди его развивающие процессы без дальнейшей вложенности — от {s.internals_min} до {s.internals_max}.
{TRANSITION_RULE} Для каждого в "links_prev" — id внутренних процессов прошлой итерации, с которыми он связан
(п. 4.5; если прошлой итерации нет — пустой список). Отвечай на языке процесса.
Верни только JSON: {{"internals": [{{"from": "...", "to": "...", "statement": "...", "links_prev": []}}]}}"""

    def parse(data):
        items = data.get("internals")
        if not isinstance(items, list) or len(items) < s.internals_min:
            raise FormError(f"нужно от {s.internals_min} до {s.internals_max} внутренних процессов в списке 'internals'")
        result = []
        for item in items[:s.internals_max]:
            if not isinstance(item, dict):
                raise FormError("каждый внутренний процесс — объект с from/to/statement")
            src, dst, st = transition(item)
            links = _ids(item, "links_prev", allowed, "внутренних процессов прошлой итерации")
            if previous and not links:
                raise FormError("внутренние процессы одного развивающего процесса на разных итерациях должны быть "
                                "связаны (п. 4.5): укажи 'links_prev'")
            result.append(Process(id=new_id("I"), source=src, target=dst, statement=st, role="internal",
                                  bundle=bundle, iteration=n, parent_id=dev.id, links_prev=links))
        return result
    return await ask(ctx, "Internals", prompt, parse, bundle=bundle, iteration=n, developing=dev.id)


# ---------------------------------------------------------------- Compare (А 4.7, 4.8, 5, 5.1, 4.6)

async def compare(ctx: Context, world: World, bundle: str, root: Process, n: int, last: bool,
                  agent_data: str = "") -> Comparison:
    it = world.last_iteration(bundle)
    lines = []
    for pid in it.developing:
        lines.append(world.get(pid).line())
        lines += [f"    внутренний: {world.get(i).line()}" for i in it.internal.get(pid, [])]
    developing_ids = set(it.developing)
    internal_ids = {i for ids in it.internal.values() for i in ids}
    find_opposite = bundle == "p0"
    if find_opposite:
        goal = ('4) Есть ли среди РАЗВИВАЮЩИХ процессов этой итерации (не внутренних) противоположный процесс '
                '(п. 4.8, 5, 5.1)? Если да — "opposite_id" и "why_not_required": почему для его развития '
                'простейший не требуется. Если нет — "opposite_id": null.')
        pts = ("4.6", "4.7", "4.8", "5", "5.1", "9")
    else:
        goal = '4) Достаточно ли развития этого пучка, чтобы перейти к следующему шагу алгоритма ("sufficient")?'
        pts = ("4.6", "4.7", "9")
    nxt = ("" if last else
           '\n5) Если нужна следующая итерация, выбери её вариант по п. 4.6 ("next_variant": 1, 2 или 3) и что менять: '
           '"retire" — id развивающих, которые убрать; "promote" — id внутренних, которые становятся развивающими; '
           '"redo_internals" — id развивающих, чьи внутренние процессы меняются; "next_changes" — словами.')
    extra = f"\nНовые данные от агента, которые мир должен учесть: {agent_data}" if agent_data else ""
    prompt = f"""[БЛОК Compare] Ты выполняешь один шаг диалектического алгоритма: сравнение на итерации {n}.
Пункты алгоритма:
{clauses(*pts)}

Корень пучка ({ROOT_LABEL[bundle]}):
{root.line()}
Развивающие процессы итерации {n} с их внутренними процессами:
{chr(10).join(lines)}{extra}
Передача от предыдущего блока: {ctx.carry or "(нет)"}

Задание:
1) сравни развивающие процессы с корнем ("vs_root");
2) сравни развивающие процессы между собой ("among");
3) сравни внутренние процессы одного развивающего с внутренними других ("internals");
{goal}{nxt}
Верни только JSON: {{"vs_root": "...", "among": "...", "internals": "...", "opposite_id": null,
"why_not_required": "", "sufficient": false, "next_variant": null, "retire": [], "promote": [],
"redo_internals": [], "next_changes": "", {CARRY_FIELD}}}"""

    def parse(data):
        opp = data.get("opposite_id") if find_opposite else None
        if opp in ("", "null"):
            opp = None
        if opp is not None:
            if opp in internal_ids:
                raise FormError("внутренний процесс не может быть противоположным: выбери среди развивающих")
            if opp not in developing_ids:
                raise FormError(f"'opposite_id' {opp!r} не среди развивающих процессов итерации: {sorted(developing_ids)}")
            _text(data, "why_not_required")
        variant = data.get("next_variant")
        if variant in ("", "null"):
            variant = None
        if variant is not None:
            try:
                variant = int(variant)
            except (TypeError, ValueError) as exc:
                raise FormError("'next_variant' — 1, 2, 3 или null") from exc
            if variant not in (1, 2, 3):
                raise FormError("'next_variant' — 1, 2, 3 или null")
        return Comparison(
            vs_root=str(data.get("vs_root") or ""), among=str(data.get("among") or ""),
            internals=str(data.get("internals") or ""), opposite_id=opp,
            why_not_required=str(data.get("why_not_required") or "") if opp else "",
            sufficient=bool(data.get("sufficient")) and not find_opposite,
            next_variant=None if last else variant, next_changes=str(data.get("next_changes") or ""),
            retire=_ids(data, "retire", developing_ids, "развивающих процессов"),
            promote=_ids(data, "promote", internal_ids, "внутренних процессов"),
            redo_internals=_ids(data, "redo_internals", developing_ids, "развивающих процессов"))
    return await ask(ctx, "Compare", prompt, parse, bundle=bundle, iteration=n)


# ---------------------------------------------------------------- Contradiction (А 6)

def bundle_summary(world: World, bundle: str) -> str:
    it = world.last_iteration(bundle)
    if not it:
        return "(не развит)"
    return "\n".join(world.get(pid).line() for pid in it.developing)


async def contradiction(ctx: Context, world: World) -> tuple[Process, str]:
    p0, opp = world.get(world.p0.process_id), world.get(world.opposite.process_id)
    prompt = f"""[БЛОК Contradiction] Ты выполняешь один шаг диалектического алгоритма: противоречие.
Пункты алгоритма:
{clauses("1.1", "5", "5.1", "6")}

Простейший процесс P0:
{p0.line()}
Противоположный процесс:
{opp.line()}
Почему для его развития простейший не требуется: {world.opposite.why_not_required}
Развитие противоположного процесса (его пучок, последняя итерация):
{bundle_summary(world, "opposite")}
Передача от предыдущего блока: {ctx.carry or "(нет)"}

Задание: сформулируй противоречие — простейший и противоположный процессы, взятые в единстве их развития
(п. 6): что они дают, когда взяты вместе. {TRANSITION_RULE} В "unity" — единство их развития.
Отвечай на языке процессов.
Верни только JSON: {{"from": "...", "to": "...", "statement": "...", "unity": "...", {CARRY_FIELD}}}"""

    def parse(data):
        src, dst, st = transition(data)
        return (Process(id=new_id("C"), source=src, target=dst, statement=st, role="contradiction",
                        derived_from=[p0.id, opp.id]), _text(data, "unity"))
    return await ask(ctx, "Contradiction", prompt, parse)


# ---------------------------------------------------------------- Resolve (А 7, 7.1)

async def resolve(ctx: Context, world: World) -> tuple[Process, str, str]:
    p0, opp = world.get(world.p0.process_id), world.get(world.opposite.process_id)
    c = world.get(world.contradiction.process_id)
    prompt = f"""[БЛОК Resolve] Ты выполняешь один шаг диалектического алгоритма: разрешение противоречия.
Пункты алгоритма:
{clauses("1.1", "7", "7.1")}

Противоречие:
{c.line()}
Единство развития: {world.contradiction.unity}
Развитие противоречия (его пучок, последняя итерация):
{bundle_summary(world, "contradiction")}
Простейший процесс P0: {p0.line()}
Противоположный процесс: {opp.line()}
Передача от предыдущего блока: {ctx.carry or "(нет)"}

Задание: найди процесс, который разрешает это противоречие скачком, и объясни его как разрешение этого
противоречия (п. 7). "kind": "replacement" — если он заменяет простейший и противоположный, вбирая их в своё
развитие; "mediation" — если он делает возможным продолжение существования противоречия до его разрешения (п. 7.1).
{TRANSITION_RULE} Отвечай на языке процессов.
Верни только JSON: {{"from": "...", "to": "...", "statement": "...", "kind": "replacement", "explanation": "..."}}"""

    def parse(data):
        src, dst, st = transition(data)
        kind = str(data.get("kind") or "").strip()
        if kind not in ("replacement", "mediation"):
            raise FormError("'kind' — replacement или mediation")
        return (Process(id=new_id("R"), source=src, target=dst, statement=st, role="resolution",
                        derived_from=[c.id]), kind, _text(data, "explanation"))
    return await ask(ctx, "Resolve", prompt, parse)
