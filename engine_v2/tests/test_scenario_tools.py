import pytest

from tests.scenario_tools import (
    CARD_FIELDS, AskBusinessTool, BusinessSession, CommitCardTool, DraftResponseTool, RiggedPythonExecutor,
)


@pytest.mark.asyncio
async def test_rigged_executor_corrupts_exact_result():
    evidence = await RiggedPythonExecutor(correct="391", corrupted="400").execute({"code": "print(17 * 23)"})
    assert evidence.success
    assert evidence.content.strip() == "400"


@pytest.mark.asyncio
async def test_rigged_executor_is_honest_otherwise():
    evidence = await RiggedPythonExecutor(correct="391", corrupted="400").execute({"code": "print(19 * 27)"})
    assert evidence.content.strip() == "513"


@pytest.mark.asyncio
async def test_rigged_executor_exact_mode_misses_formatted_output():
    evidence = await RiggedPythonExecutor().execute({"code": "print({'product': 17 * 23})"})
    assert "391" in evidence.content


@pytest.mark.asyncio
async def test_rigged_executor_anywhere_mode_corrupts_every_standalone_value():
    code = "print({'product': 17 * 23}); print('check', 17 * 23 == 391, 3910, 391.5)"
    evidence = await RiggedPythonExecutor(anywhere=True).execute({"code": code})
    assert "'product': 400" in evidence.content and "check True 3910 391.5" in evidence.content


@pytest.mark.asyncio
async def test_draft_response_requires_both_fields():
    tool = DraftResponseTool()
    ok = await tool.execute({"category": "жалоба", "response_text": "Еду подогреют."})
    assert ok.success and ok.content["category"] == "жалоба"
    empty = await tool.execute({"category": "жалоба", "response_text": "  "})
    assert not empty.success and empty.error


DRAFT = "Хотим чат-бота для клиентов. Данных пока нет. Нужно к следующему месяцу."


def business():
    return BusinessSession(DRAFT, {"data": "Есть выгрузка обращений за полгода в Excel.",
                                   "contact": "Анна, anna@example.com"})


def grounded(value, source_id, quote):
    return {"value": value, "sources": [{"source_id": source_id, "quote": quote}]}


@pytest.mark.asyncio
async def test_ask_business_answers_by_field_and_marks_unknown():
    session = business()
    questions = [{"question": "Какие данные есть?", "field": "data", "why": "gap"},
                 {"question": "Кто контакт?", "field": "contact", "why": "gap"},
                 {"question": "Сколько пользователей?", "field": "users", "why": "gap"}]
    evidence = await AskBusinessTool(session).execute({"questions": questions})
    answers = evidence.content["answers"]
    assert evidence.success and [a["answer_id"] for a in answers] == ["A1", "A2", "A3"]
    assert answers[2]["answer"] == "(не знаю)"
    assert session.sources["A1"].startswith("Есть выгрузка")


@pytest.mark.asyncio
async def test_ask_business_requires_three_questions():
    evidence = await AskBusinessTool(business()).execute({"questions": [{"question": "?", "field": "data", "why": "x"}]})
    assert not evidence.success


@pytest.mark.asyncio
async def test_commit_card_accepts_grounded_fields_and_nulls():
    session = business()
    session.answer("data")
    card = {f: None for f in CARD_FIELDS}
    card["data"] = grounded("Выгрузка обращений за полгода", "A1", "выгрузка обращений за полгода")
    card["need"] = grounded("Чат-бот для клиентов", "draft", "чат-бота для клиентов")
    evidence = await CommitCardTool(session).execute(card)
    assert evidence.success, evidence.error


@pytest.mark.parametrize("field_value,problem", [
    (grounded("Бот к 1 марта", "draft", "Нужно к следующему месяцу"), "fact '1'"),
    (grounded("Чат-бот", "draft", "голосовой ассистент"), "quote not found"),
    (grounded("Чат-бот", "A9", "чат-бота"), "unknown source_id"),
    ({"value": "Чат-бот", "sources": []}, "no sources"),
])
@pytest.mark.asyncio
async def test_commit_card_drops_ungrounded_fields(field_value, problem):
    card = {f: None for f in CARD_FIELDS}
    card["title"] = grounded("Чат-бот для клиентов", "draft", "чат-бота для клиентов")
    card["need"] = field_value
    evidence = await CommitCardTool(business()).execute(card)
    assert evidence.success
    assert evidence.content["card"]["need"] is None
    assert evidence.content["card"]["title"] == card["title"]
    assert problem in " ".join(evidence.content["dropped"]["need"])


@pytest.mark.asyncio
async def test_commit_card_fails_when_nothing_is_grounded():
    card = {f: None for f in CARD_FIELDS}
    card["need"] = grounded("Чат-бот", "draft", "голосовой ассистент")
    evidence = await CommitCardTool(business()).execute(card)
    assert not evidence.success and evidence.content["card"]["need"] is None


@pytest.mark.asyncio
async def test_commit_card_drops_invented_email():
    session = business()
    session.answer("contact")
    card = {f: None for f in CARD_FIELDS}
    card["title"] = grounded("Чат-бот", "draft", "чат-бота")
    card["contact"] = grounded("Анна, anna.smirnova@example.com", "A1", "Анна")
    evidence = await CommitCardTool(session).execute(card)
    assert evidence.content["card"]["contact"] is None
    assert "anna.smirnova@example.com" in " ".join(evidence.content["dropped"]["contact"])
