# Индекс архива прогонов v2

121 файл — сырые логи, трассы и результаты прогонов версии 2, перенесённые сюда из корня `engine_v2/`
(где они были вперемешку с кодом пакета). Ничего не удалено, ничего не пересчитано заново — файлы лежат
как есть, для воспроизводимости чисел, на которые ссылаются `ENGINE_V2_LESSONS.md`, `ENGINE_V3_RESULTS.md`
и `RESEARCH_HISTORY_AND_PROGRAM.md`.

Полный построчный разбор этих файлов (и параллельно — файлов `live_runs/`, которые в архив не входят,
см. корневой `.gitignore`) уже сделан в `../../../RESEARCH_HISTORY_AND_PROGRAM.md`. Этот индекс не
дублирует тот разбор, а указывает точные пути для каждой цифры, встречающейся в отчётах.

## Цифры → источники

| Цифра / заявление | Где встречается | Файл-источник | Примечание |
|---|---|---|---|
| «Лживый инструмент `deceive_unknowable`: агент обманут 3 из 3, движок 0 из 3» | `ENGINE_V2_LESSONS.md`, п. 2 | `live_runs/ablation/deceive_unknowable_full.log` (+ `deceive_unknowable_auto.log`) | **Не** `hardcore_deceive_gross_v*` в этом архиве — те про другой тест, см. ниже |
| «`deceive_persistent`: движок 3 из 3 честно сообщил о неразрешённом противоречии» | `ENGINE_V2_LESSONS.md`, п. 2 | `live_runs/ablation/deceive_persistent_full.log` (+ `deceive_persistent_auto.log`) | То же: раунд 2, после появления `REPORT_CONTRADICTION`; раунд 1 (`live_runs/compare_unknowable/`, `live_runs/deceive_persistent/`) даёт другие, худшие числа — см. `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.2 |
| «Абляция: устойчивость даёт практика, а не планирование, дешевле в 1,5–3 раза» | `ENGINE_V2_LESSONS.md`, п. 2 | `live_runs/ablation/*_auto.log` против `*_full.log` | 35% дешевле на unknowable, 64% дешевле на persistent — см. таблицу в `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.2 |
| «Судья стоил 70% токенов (200 тыс. из 286 тыс. на одном договоре)» | `ENGINE_V2_LESSONS.md`, п. 3 | `live_runs/contract_nli/run_one.py`, файл `doc446_nda-7` | Точно: актёр 86 064 / судья 200 829 из 286 893 = 70,0% |
| «Узкий атомарный семантический вызов устойчив на 92–100%» (Stage 14) | `RESEARCH_HISTORY_AND_PROGRAM.md`, §1 (эра B), §2.1 | `stage14c_binary_results.jsonl`, `stage14c_ternary_results.jsonl`, `stage14c2_binary_results.jsonl`, `stage14c2_ternary_results.jsonl`, `stage14c2_calibration_binary_results.jsonl` (все — в этом каталоге) | Несовпадения по группам «кейс×критерий»: 8,3% / 6,2% / 0% / 0% / 4,4% → совпадение 91,7–100% |
| «ContractNLI: обычная модель — 49 ошибок из 220 пар с эталоном „противоречит“» | `ENGINE_V2_LESSONS.md`, п. 2 | `live_runs/contract_nli/` (сам прогон-скан) | Датасет CC BY 4.0, см. отдельную проверку лицензии (п. 5 общего плана) |
| «`hardcore_deceive_gross` v1→v8: 0/23 обмана, но только 3/23 (13%) завершились» | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.2 | `hardcore_deceive_gross_1.jsonl`…`hardcore_deceive_gross_v8_3.jsonl` (все версии — в этом каталоге) | **Другой харнесс**, чем `deceive_unknowable`/`deceive_persistent` выше: 14-ходовой протокол, ещё до `REPORT_CONTRADICTION`, тема — грубая арифметическая ложь (400 вместо 391), а не business-card. Улучшения от v1 к v8 не видно — это серия попыток нащупать формат, а не последовательное улучшение результата |
| «`hardcore_deceive_subtle`: тонкая ложь проходит всегда, 3/3» | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.2 | `hardcore_deceive_subtle_1.jsonl`, `hardcore_deceive_subtle_2.jsonl`, `hardcore_deceive_subtle_3.jsonl` | Тот же харнесс, что и gross выше |
| «`deception_matrix`: движок против агента, честное сравнение, 0/6 успешно» | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.2 | `deception_matrix_results.json`, `deception_matrix_log.txt`, `matrix_gross_400_{1,2,3}.jsonl`, `matrix_subtle_390_{1,2,3}.jsonl` | 4/6 не дошли до вызова инструмента — совпадает с реальным исчерпанием суточной квоты OpenAI, сравнение не чистое |
| «`batball_run{1,2,3}`: 0/3 завершений» | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.3 | `batball_run1.jsonl`, `batball_run2.jsonl`, `batball_run3.jsonl` | Модель предлагает ходы, не разрешённые резолвером на этом шаге |
| «`rigged_run1` vs `rigged_run2`: одна и та же настройка, разный исход» | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.3 | `rigged_run1.jsonl`, `rigged_run2.jsonl` | Иллюстрация высокой дисперсии между прогонами — единичный прогон не доказателен |
| «Разрешение-склейка: „интегрированная система“ вместо разрешения» | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.4 | `mega_genuine_tension_1.jsonl` | Прошло судью без замечаний — конкретный датированный пример |
| Диагностика судьи, отвергающего верный ход 5 раз подряд | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.1 | `diag_h1.txt` | |
| Три взаимоисключающих определения «противоположности» для одной задачи | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.1 | `diag_h6.txt`, `diag_h7.txt`, `diag_h8.txt` | Сняты с разницей в минуты |
| Модель трижды повторяет идентичный отклонённый ход | `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.3 | `diag_rigged1.txt`, `diag_v8.txt` | |

## Прочие файлы в этом каталоге (не процитированы напрямую в отчётах, но входят в общий массив прогонов v2)

`appeal_run{1,2,3}.jsonl`, `canary_cerebras_judge.jsonl`, `canary_full_out{,2}.txt`, `clear_path.jsonl`,
`diag_appeal{,2}.txt`, `diag_bb1.txt`, `diag_bb23.txt`, `diag_coin1.txt`, `diag_hard{,2}.txt`, `diag_v2_2.txt`,
`final_results.json`…`final_results6.json`, `fixed_results.json`, `fixed_results2.json`,
`hard_arith_{1,2}.jsonl`, `hard_batball_{1,2}.jsonl`, `hardcore_appeal_{1,2}.jsonl`,
`hardcore_batball_{1,2}.jsonl`, `hardcore_coin_puzzle_{1,2}.jsonl`, `hardcore_coin_puzzle_v2_{1,2}.jsonl`,
`hardcore_results.json`, `hardcore_results_v2.json`, `mega_appeal_{1,2}.jsonl`, `mega_arithmetic_{1,2}.jsonl`,
`mega_batball_{1,2}.jsonl`, `mega_clear_*.jsonl`, `mega_coin_puzzle_{1,2}.jsonl`,
`mega_deceive_{gross,subtle}*.jsonl`, `mega_results.json`, `meta_output{,2}.txt`, `meta_run.jsonl`,
`stage14c2_calibration_cases.json`, `stage14c2_case1{,_binary}.json{,l}`, `stage14c2_heldout_cases.json`,
`token_metrics.json`, `trace.jsonl`.

Эти файлы упоминаются в `RESEARCH_HISTORY_AND_PROGRAM.md` менее адресно (как часть временной шкалы или
общего массива) либо не разобраны построчно — статус «не проверено индивидуально» относится к ним, а не к
таблице выше.

## Важное предупреждение (см. `RESEARCH_HISTORY_AND_PROGRAM.md`, §2.2, строки 145–148)

Имена кейсов `deceive_unknowable` и `deceive_persistent` встречаются **дважды** в проекте: один раз в
`live_runs/` (раунд после `REPORT_CONTRADICTION`, это и есть источник чисел в `ENGINE_V2_LESSONS.md`) и один
раз здесь, в этом архиве, под именем `hardcore_deceive_gross`/`hardcore_deceive_subtle` (более ранний,
структурно другой харнесс, 22 сентября, ещё без `REPORT_CONTRADICTION`). Это не одно и то же измерение —
сравнивать их напрямую как «до/после» нельзя.
