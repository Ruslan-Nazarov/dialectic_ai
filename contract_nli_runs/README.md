# Прогоны на ContractNLI — не датасет, а результаты

**Это выдержка, а не датасет.** Здесь только собственные результаты прогонов, цитаты из ответов
агента (обрезаны до ≤800 символов) и два полных лога отдельных прогонов движка v2 на одном
реальном договоре. Полного корпуса ContractNLI (607 NDA, разметка, исходные PDF) здесь нет —
он не републикуется, чтобы не дублировать 63 МБ чужих данных, у которых уже есть официальный
источник.

## Атрибуция (условие лицензии CC BY 4.0)

Датасет: **ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts**,
Yuta Koreeda и Christopher D. Manning, *Findings of the Association for Computational
Linguistics: EMNLP 2021*. Официальный источник и полный корпус:
<https://stanfordnlp.github.io/contract-nli/>.

Лицензия: Creative Commons Attribution 4.0 International (CC BY 4.0).
Текст лицензии: <https://creativecommons.org/licenses/by/4.0/>.

Цитаты из текстов договоров в файлах ниже (в `answer`-полях и в двух полных трассах) — часть
этого лицензированного датасета, приводятся в рамках той же лицензии.

## Что здесь лежит

- `run_one.py`, `eval_v3.py`, `plain_scan.py`, `revise_demo.py` — скрипты прогонов.
- `eval_v3.json` / `eval_v3.md` — результаты сравнения «без мира / с миром NDA / контроль»,
  129 пар, по 2 повтора (см. `../ENGINE_V3_RESULTS.md`, раздел 3, и `../ENGINE_V3_RESULTS_INDEX.md`).
- `eval_dry.json` / `eval_dry.md` — пробный (dry-run) прогон перед основным.
- `plain_scan.json` — скан обычной моделью без мира (источник цифры «49 ошибок из 220» в
  `../ENGINE_V2_LESSONS.md`).
- `doc446_nda-7.jsonl`, `doc4_nda-1.jsonl` — два полных лога прогона движка v2 целиком (блоки →
  практика → ответ) на одном реальном договоре каждый; источник цифры «70% токенов на судью»
  (`../ENGINE_V2_LESSONS.md`, раздел 3; см. `../engine_v2/archive/run_logs/INDEX.md`). Каждый
  файл содержит полный текст соответствующего договора один раз — это часть реального промпта
  того прогона, не повторяющаяся выдержка.
- `doc446_nda-7.result.json`, `doc4_nda-1.result.json` — итоговые результаты тех же двух прогонов.
- `fake_world.json` — служебный тестовый мир для проверки без реального прогона.
