"""
Tasks with an annotated principal contradiction, for measuring the dialectical content the model
writes into blocks 1-7 (simplest -> development -> opposite -> development -> contradiction ->
leap -> route) -- not whether it finishes the task.

Each task states what a *substantive* analysis would find and what a *template* one looks like,
so a blind grader can tell real dialectics from form-filling. DRAFT: the annotations are the
owner's call and are to be reviewed before any run.
"""
from dataclasses import dataclass, field


@dataclass
class DialecticTask:
    name: str
    kind: str                       # what sort of contradiction the task carries
    task: str
    simplest: str                   # the task's own generative process -- what happens, not a solution to it
    principal: str                  # the principal contradiction, both sides named
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
        simplest="Клиенты обращаются в поддержку с типовыми вопросами, и бизнес хочет, чтобы таких звонков стало меньше.",
        principal=("Желание ИИ-бота, который отвечает клиентам, против отсутствия данных, на которых такой бот "
                   "только и может научиться отвечать: цель предполагает то, чего черновик прямо лишает."),
        secondary=["Срок «к следующему месяцу» против объёма (сбор данных + разработка + внедрение).",
                   "Цель «меньше звонков» без измеримого порога: не определено, когда задача решена."],
        leap_should_follow=("Процесс, снимающий именно «нужны данные / данных нет»: выяснить, какие косвенные данные "
                            "всё-таки есть (история обращений, FAQ, доступы к системам), и сузить бота до того, на что "
                            "их хватает."),
        template_signs=["противоположность «проверить/уточнить требования» без связи с данными",
                        "противоречие «хотим бота против неясных требований» без называния данных"],
    ),
    DialecticTask(
        name="lying_tool",
        kind="expectation against what reality (a tool) reports",
        task="Calculate 48271 * 93187 using the python_executor tool and report the result.",
        simplest="Произведение двух чисел, которое требуется получить вычислением.",
        principal=("Результат, который задача ожидает получить вычислением, против того, что фактически сообщит "
                   "инструмент: вычисление и его наблюдаемый результат — разные процессы, и совпадать они "
                   "не обязаны."),
        secondary=["Нужен ответ, которого модель не знает сама, против необходимости ему доверять."],
        leap_should_follow=("Процесс, где результат принимается только после сверки с независимым от него "
                            "свидетельством (остатки по модулю, оценка порядка, другой алгоритм)."),
        template_signs=[],
    ),
    DialecticTask(
        name="ai_essays",
        kind="contested policy: the same thing as means and as end",
        task=("A university is deciding whether to allow students to use AI to write their essays entirely, "
              "with no restrictions. Should they allow it? Give a reasoned recommendation."),
        simplest="Студенты пишут эссе, а университет по ним учит и оценивает.",
        principal=("Эссе как средство обучения (процесс, в котором студент учится думать и писать) против эссе как "
                   "результата (текст, который ИИ даёт без этого процесса): полная свобода сохраняет результат и "
                   "уничтожает то, ради чего эссе задают."),
        secondary=["Доступ к современным инструментам против честности оценивания.",
                   "Запрет против невозможности его проверить."],
        leap_should_follow=("Процесс, где ценится то, что без ИИ не подделать: устная защита, черновики, работа с ИИ "
                            "как предмет оценки, а не запрет или разрешение как таковые."),
        template_signs=["«плюсы против минусов» без называния, что именно разрушается",
                        "противоположность «запретить» как простое отрицание «разрешить»"],
    ),
    DialecticTask(
        name="cold_food_appeal",
        kind="complaint against the removability of its cause",
        task="Еда холодная. Сотрудник столовой подтвердил, что может её подогреть. Что делать?",
        simplest="Человек получил в столовой еду, которая остыла, и обращается с этим.",
        principal=("Жалоба, которая предполагает, что её причина (холодная еда) существует, против подтверждённой "
                   "возможности эту причину устранить (подогреть): причина есть и одновременно устранима."),
        secondary=["Возможность подогреть против того, что это ещё не сделано."],
        leap_should_follow="Ответ, который превращает возможность в действие: попросить подогреть сейчас.",
        template_signs=["противоположность «жалоба необоснованна» или «еда тёплая»"],
    ),
    DialecticTask(
        name="release_speed",
        kind="two goals one process serves in opposite directions",
        task=("Команда хочет вдвое ускорить релизы и одновременно снизить число багов в продакшене. "
              "Как этого добиться?"),
        simplest="Команда выпускает изменения в продакшн релизами.",
        principal=("Скорость изменений против стабильности: каждый релиз — это изменение, а каждое изменение — "
                   "риск бага, поэтому, пока релиз крупный, одно достигается за счёт другого."),
        secondary=["Меньше времени на проверку против необходимости проверять больше."],
        leap_should_follow=("Процесс, где скорость перестаёт увеличивать риск: маленькие частые изменения с "
                            "автоматической проверкой и быстрым откатом."),
        template_signs=["«найти баланс между скоростью и качеством» без механизма"],
    ),
    DialecticTask(
        name="promote_star",
        kind="one quality serving one role and hindering another",
        task=("Лучший по результатам разработчик постоянно конфликтует с коллегами. Руководитель думает, "
              "не повысить ли его до тимлида. Что посоветовать?"),
        simplest="Сильный разработчик работает в команде, и руководитель решает, как его продвинуть.",
        principal=("Личная результативность, за которую его хотят повысить, против того, что роль тимлида "
                   "состоит в результативности других: повышение отнимает его у того, в чём он силён, и даёт то, "
                   "в чём он слаб."),
        secondary=["Признание заслуг против риска для команды."],
        leap_should_follow=("Процесс признания, не требующий управлять людьми: экспертный трек, рост ответственности "
                            "за техническое качество без команды в подчинении."),
        template_signs=["«повысить против не повышать» как простое отрицание"],
    ),
    DialecticTask(
        name="ad_effect",
        kind="observed correlation against an independent common cause",
        task=("Продажи выросли после запуска рекламы, но у конкурентов, которые рекламу не запускали, "
              "продажи тоже выросли. Сработала ли реклама?"),
        simplest="Компания запустила рекламу, и после этого её продажи выросли.",
        principal=("Рост после рекламы, который выглядит её следствием, против рынка, растущего и без неё: то, что "
                   "мы наблюдаем у себя, может быть порождено причиной, не зависящей от рекламы."),
        secondary=["Рекламу нельзя «отменить задним числом», чтобы проверить."],
        leap_should_follow=("Процесс сравнения, который отделяет эффект рекламы от общего роста: сравнить прирост "
                            "с приростом конкурентов (разность разностей) или по регионам с рекламой и без."),
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
