"""
Tasks with an annotated principal contradiction, for measuring the dialectical content the model
writes into blocks 1-7 (simplest -> development -> opposite -> development -> contradiction ->
leap -> route) -- not whether it finishes the task.

Each task states what a *substantive* analysis would find and what a *template* one looks like,
so a blind grader can tell real dialectics from form-filling. Annotations follow the owner's method
(memory: dialectical-method-blocks): simplest = the given situation; the opposite is caught from a
determination in the simplest's development; the contradiction is both existing at once; the leap is
the result of the opposite acting on the simplest. cold_food_appeal and ai_essays were analysed by the
owner; the other tasks are drafted by analogy and await the owner's review.
"""
from dataclasses import dataclass, field


@dataclass
class DialecticTask:
    name: str
    kind: str                       # what sort of contradiction the task carries
    task: str
    simplest: str                   # the given situation -- what happens, not a solution to it
    principal: str                  # the principal contradiction: both sides existing at once
    independence: str = ""           # the simplest's determination the opposite is caught from
    opposite: str = ""              # the opposite process caught from it
    secondary: list = field(default_factory=list)
    leap_should_follow: str = ""    # what a leap derived from the principal contradiction looks like
    template_signs: list = field(default_factory=list)  # marks of form-filling for this task
    has_genuine_contradiction: bool = True


TASKS = [
    DialecticTask(
        name="business_draft",
        kind="gap between what the author knows and what the executor needs",
        task=("Хотим чат-бота на ИИ для наших клиентов, чтобы меньше звонили в поддержку. "
              "Данных пока нет. Нужно к следующему месяцу."),
        simplest="Клиенты звонят в поддержку с типовыми вопросами.",
        principal="Клиенты звонят оператору, и на их вопросы можно ответить без оператора — одновременно.",
        independence="Типовой вопрос — вопрос, ответ на который уже известен, значит его можно дать и без оператора.",
        opposite="Ответ на вопрос без оператора.",
        secondary=["Срок «к следующему месяцу» против объёма (сбор данных + разработка + внедрение).",
                   "Цель «меньше звонков» без измеримого порога: не определено, когда задача решена."],
        leap_should_follow="Типовое обращение перестаёт требовать оператора: ответ даётся без звонка.",
        template_signs=["противоположность «проверить/уточнить требования» без связи с данными",
                        "противоречие «хотим бота против неясных требований» без называния данных"],
    ),
    DialecticTask(
        name="lying_tool",
        kind="expectation against what reality (a tool) reports",
        task="Calculate 48271 * 93187 using the python_executor tool and report the result.",
        simplest="Произведение двух чисел, которое требуется получить.",
        principal="Требуемое произведение и то, что сообщает о нём инструмент, существуют одновременно и совпадать не обязаны.",
        independence="Произведение здесь получается вычислением инструмента, то есть известно только как то, что инструмент сообщит.",
        opposite="Сообщение инструмента о результате.",
        secondary=["Нужен ответ, которого модель не знает сама, против необходимости ему доверять."],
        leap_should_follow="Произведение, известное только через сообщение инструмента, нельзя принять без сверки с независимым свидетельством.",
        template_signs=[],
    ),
    DialecticTask(
        name="ai_essays",
        kind="contested policy: the same thing as means and as end",
        task=("A university is deciding whether to allow students to use AI to write their essays entirely, "
              "with no restrictions. Should they allow it? Give a reasoned recommendation."),
        simplest="Эссе студента.",
        principal="Эссе — работа студента, и его может написать ИИ — одновременно.",
        independence="Эссе — то, что пишет студент, а значит и то, что может написать не студент.",
        opposite="Написание текста ИИ.",
        secondary=["Доступ к современным инструментам против честности оценивания.",
                   "Запрет против невозможности его проверить."],
        leap_should_follow="Невозможность оценить работу: эссе теряет то, ради чего существует, — быть свидетельством самого студента.",
        template_signs=["«плюсы против минусов» без называния, что именно разрушается",
                        "противоположность «запретить» как простое отрицание «разрешить»"],
    ),
    DialecticTask(
        name="cold_food_appeal",
        kind="complaint against the removability of its cause",
        task="Еда холодная. Сотрудник столовой подтвердил, что может её подогреть. Что делать?",
        simplest="Холодная еда.",
        principal="Еда холодная, и еду можно подогреть — одновременно.",
        independence="Холодная еда — еда, которую не подогрели, а значит еда, которую можно подогреть.",
        opposite="Подогрев еды.",
        secondary=["Возможность подогреть против того, что это ещё не сделано."],
        leap_should_follow="Подогрев холодной еды (не подогрев еды вообще): противоречие снято.",
        template_signs=["противоположность «жалоба необоснованна» или «еда тёплая»"],
    ),
    DialecticTask(
        name="release_speed",
        kind="two goals one process serves in opposite directions",
        task=("Команда хочет вдвое ускорить релизы и одновременно снизить число багов в продакшене. "
              "Как этого добиться?"),
        simplest="Команда выпускает изменения релизами.",
        principal="Релиз — пачка изменений, и изменение можно выпустить отдельно — одновременно.",
        independence="Релиз — пачка изменений, а значит изменения можно выпускать и не пачкой, а по одному.",
        opposite="Выпуск отдельного изменения.",
        secondary=["Меньше времени на проверку против необходимости проверять больше."],
        leap_should_follow="Релиз из одного изменения: ускорение выпуска перестаёт увеличивать риск.",
        template_signs=["«найти баланс между скоростью и качеством» без механизма"],
    ),
    DialecticTask(
        name="promote_star",
        kind="one quality serving one role and hindering another",
        task=("Лучший по результатам разработчик постоянно конфликтует с коллегами. Руководитель думает, "
              "не повысить ли его до тимлида. Что посоветовать?"),
        simplest="Сильный разработчик, конфликтующий с коллегами, которого думают повысить.",
        principal="Его сила — личная работа, и роль тимлида — работа через других — одновременно.",
        independence="Его сила — личный результат его собственной работы, а тимлид — это результат работы других.",
        opposite="Работа через других (руководство людьми).",
        secondary=["Признание заслуг против риска для команды."],
        leap_should_follow="Повышение делает его силу неприменимой: лучший исполнитель становится слабым руководителем.",
        template_signs=["«повысить против не повышать» как простое отрицание"],
    ),
    DialecticTask(
        name="ad_effect",
        kind="observed correlation against an independent common cause",
        task=("Продажи выросли после запуска рекламы, но у конкурентов, которые рекламу не запускали, "
              "продажи тоже выросли. Сработала ли реклама?"),
        simplest="Продажи компании выросли после запуска рекламы.",
        principal="Наш рост после рекламы, и рынок растёт без рекламы — одновременно.",
        independence="Рост продаж — рост, у которого есть причины, и такой рост есть и у тех, кто не рекламировался.",
        opposite="Рост рынка без рекламы.",
        secondary=["Рекламу нельзя «отменить задним числом», чтобы проверить."],
        leap_should_follow="Рост перестаёт свидетельствовать о рекламе: её эффект — только прирост сверх роста рынка.",
        template_signs=["противоположность «реклама не сработала» как отрицание вывода"],
    ),
    DialecticTask(
        name="capital_city",
        kind="control: no genuine contradiction",
        task="What is the capital city of France?",
        simplest="Вопрос о факте: какая столица у Франции.",
        principal="Настоящего противоречия нет: ответ — общеизвестный факт, роль проверки не требует.",
        leap_should_follow="Нет. Правильно завершить коротким путём, не выдумывая противоположность.",
        template_signs=["противоположность «независимо проверить ответ»", "любое выдуманное противоречие"],
        has_genuine_contradiction=False,
    ),
]
