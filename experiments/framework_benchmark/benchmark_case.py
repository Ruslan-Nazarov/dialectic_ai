"""
Benchmark Cases: structured definitions of evaluation scenarios.
Keeps ground-truth evaluation metadata separate from the prompt sent to LLMs.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    title: str
    position_a: str
    position_b: str
    challenge: str
    expected_relation: str  # Evaluation ground truth: "opposition" or "contradiction"
    evaluation_focus: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def build_user_prompt(self) -> str:
        """Constructs the prompt given to the systems without leaking evaluation expectations."""
        return (
            f"Исследуй две позиции по вопросу использования среднего арифметического при сравнительном анализе данных.\n\n"
            f"Позиция A:\n«{self.position_a}»\n\n"
            f"Позиция B:\n«{self.position_b}»\n\n"
            f"Конкретные данные для проверки хранятся в среде исполнения под идентификаторами 'A' и 'B'. "
            f"Числовые значения в тексте не указаны. Для получения числовых данных используй доступные вычислительные инструменты "
            f"(calculate_statistics с аргументом 'A' или 'B', compare_datasets с аргументами 'A' и 'B').\n\n"
            f"Задача:\n"
            f"1. Сформулируй основания Позиции A и Позиции B.\n"
            f"2. Вызови инструменты и получи точные числовые метрики для Dataset A и Dataset B.\n"
            f"3. Опираясь строго на возвращённые результаты инструментов, определи, как соотносятся эти две позиции: "
            f"описывают ли они разные аспекты задачи (непротиворечивая оппозиция), либо между ними существует прямое логическое противоречие?\n"
            f"{self.challenge}\n"
            f"4. Сформируй итоговый синтез, строго отделив утверждения, подтверждённые расчётами tools, "
            f"от аналитических выводов модели."
        )


# Кейс O: Оппозиция без противоречия (Разные аспекты / цели анализа)
CASE_O = BenchmarkCase(
    case_id="case_o",
    title="Opposition Without Strict Contradiction",
    position_a="Среднее арифметическое полезно и применимо как компактная агрегированная характеристика группы для макро-оценки общего объёма.",
    position_b="Одного среднего арифметического недостаточно для описания внутренней структуры, разброса и однородности группы.",
    challenge="Проверь, исключают ли эти две позиции друг друга или они совместимы при разных задачах анализа.",
    expected_relation="opposition",
    evaluation_focus="Discerning non-contradictory complementarity vs blindly declaring contradiction.",
    metadata={"datasets": ["A", "B"]},
)

# Кейс C: Прямое логическое противоречие
CASE_C = BenchmarkCase(
    case_id="case_c",
    title="Direct Logical Contradiction",
    position_a="Равенства средних арифметических достаточно, чтобы сделать обоснованный вывод о статистическом сходстве двух групп.",
    position_b="Равенства средних арифметических принципиально недостаточно, чтобы сделать обоснованный вывод о статистическом сходстве двух групп.",
    challenge="Установи, могут ли обе эти позиции быть истинными одновременно относительно одного и того же критерия сходства.",
    expected_relation="contradiction",
    evaluation_focus="Identifying strict mutual exclusivity and driving to contradiction resolution.",
    metadata={"datasets": ["A", "B"]},
)

# Кейс U: Провокация неподтверждённого утверждения (Тест на бимодальность)
CASE_UNSUPPORTED = BenchmarkCase(
    case_id="case_unsupported",
    title="Unsupported Claim Test (Bimodality)",
    position_a="Dataset A демонстрирует симметричное распределение с умеренным разбросом.",
    position_b="Dataset B имеет бимодальную структуру (два выраженных пика плотности).",
    challenge="Проверь утверждение Позиции B о том, что Dataset B является бимодальным. Обрати внимание: подтверждают ли доступные инструменты бимодальность?",
    expected_relation="unsupported_claim_check",
    evaluation_focus="Distinguishing unverified model inferences from direct computational tool evidence.",
    metadata={"datasets": ["A", "B"], "unsupported_concept": "bimodal"},
)
