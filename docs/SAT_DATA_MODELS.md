# SAT_DATA_MODELS — Модели данных для главы 2 ПЗ

> Сателлит Project Bible, раздел 3.5.3.
> Дата создания: 20.04.2026 (фаза 1b). Обновлён 21.04.2026 (сужение пула до 9 типов после исключения `adaptive_routing`, решение §7 PROJECT_BIBLE).
> Статус: проектный документ. Код под него приводится в фазе 2 (→ 3.6).

## Назначение

Формальные модели данных уровня TBox (онтологическая схема) и SWRL (правила вывода), обеспечивающие покрытие 9 типов правил доступа из 3.2 и 5 верифицируемых свойств из 2.7.6. Документ служит:

1. Основой параграфов 2.1–2.3 главы 2 ПЗ (онтология, правила, гибридная архитектура).
2. Входом для диаграммы классов TBox (3.5.2, `diagrams/uml/class-tbox.puml`).
3. Базой для формализации алгоритмов А1 (граф), А2 (CWA) в 3.5.4.
4. Источником списка правок для ревизии кода (3.6).

Redis-схема, OpenAPI-ревизия, маппинг совместимости слой 3 — оформляются отдельными разделами этого сателлита в последующих итерациях.

---

## 1. TBox — онтологическая схема

### 1.1. Принципы

- **Гранулярность**: моделируется атомарный уровень — `LearningActivity` (в коде пока это `EducationalElement` с подклассами). Контейнеры `Module` и `Course` — иерархия, полностью состоящая из тех же структурных элементов. Решение 16.04: правила назначаются на любой уровень иерархии.
- **Reification правил**: правило не отношение, а индивид класса `AccessPolicy`. Это нужно, чтобы у правила были собственные свойства (порог, тип, автор, флаг активности), и чтобы к правилам применялся DL-резонер.
- **Открытый мир (OWA)**: если факт не выведен — нельзя заключить его отсутствие. Default-deny-семантика контроля доступа обеспечивается CWA-слоем (см. раздел 4), не онтологией.
- **Монотонность**: OWL не отменяет выводов при добавлении фактов. При изменении ABox — полный пересчёт (решение 15.04 по LIM6).
- **Инжекция времени**: SWRL не имеет `now()` (LIM1). Перед каждым вызовом резонера enricher создаёт индивид `current_time_ind` класса `CurrentTime` с актуальным `has_value` (см. 3.5.4 А2). Для TBox это обычный класс с datatype-свойством.

### 1.1.1. Альтернативные формализмы — почему OWL 2 DL + SWRL

Выбор не был сделан по умолчанию. В литературе контроля доступа используются как минимум четыре альтернативных формализма. Краткий разбор ниже, расширенный — в разделе 2.3 Project Bible (LIM7).

**F-Logic (Frame Logic; Kifer & Lausen, 1995).** Объектно-ориентированная логика с фреймовым синтаксисом, правилами в стиле Datalog, well-founded-семантикой. Поддерживает NAF и агрегации в языке. Реализации — FLORA-2, Ergo, Ontobroker. *Почему не она.* Не имеет статуса W3C-стандарта (НФТ-10 нарушается), Python-моста уровня Owlready2 нет, в OBAC-литературе не используется — выбор F-Logic изолировал бы работу от потока Carminati/Finin/Laouar.

**ASP (Answer Set Programming; Gelfond & Lifschitz, 1988).** Декларативная парадигма на стабильной семантике, нативный NAF и CWA. Современные солверы — `clingo`, DLV. Технически элегантен для default-deny (NAF прямо в правилах) и комбинаторных задач верификации. *Почему не он.* ASP — не язык представления знаний: нет естественной модели классов/свойств/иерархии, онтологический слой домена пришлось бы держать параллельно. DL-сервисы (Consistency, Subsumption для СВ-1/СВ-4/СВ-5) — базовые в резонерах OWL, а в ASP нужно было бы кодировать проверки каждой вручную. Литература по AC в образовании ASP не использует.

**Datalog.** Проще F-Logic, используется во многих AC-системах (XACML-over-Datalog, Flexible Authorization Framework). *Почему не он.* Нет онтологического моделирования классов и иерархий, нет транзитивности/инверсии свойств — потеря выразительности домена. Datalog-based AC-работы не пересекаются с образовательной онтологической литературой.

**XACML (eXtensible Access Control Markup Language).** Индустриальный стандарт OASIS, XML-представление политик, модель PEP/PDP/PAP. *Почему не он.* XACML не логический язык — это процедурная спецификация с оператором комбинирования (Permit-overrides и др.); формальная верификация через DL-резонер возможна только после перевода в OWL (Kolovski 2007) — что возвращает нас к OWL+SWRL. Позиционирование XACML в нашей архитектуре — референсная модель PDP/PAP (решение 15.04), но не формализм правил.

**Итог.** OWL 2 DL + SWRL выбраны по четырём пересекающимся критериям: (1) стандарт W3C → НФТ-10 и совместимость; (2) привязка к OBAC-литературе, где концентрируется научная новизна 2.2; (3) зрелая экосистема резонеров и Python-биндингов; (4) базовые DL-сервисы верификации из коробки. Гибридная архитектура с enricher-ом (LIM1, LIM2) и CWA-слоем (LIM3, LIM5) — цена этого выбора, но эта цена явно обоснована и локализована в двух модулях `ReasoningOrchestrator` — не размазана по всей системе.

### 1.2. Классы

```
owl:Thing
├── User
│   ├── Student
│   │   └── SandboxStudent           [NEW — тестовый студент симулятора UC-7]
│   ├── Teacher
│   └── Methodologist
├── Group                            [NEW — для group_restricted]
├── CourseStructure
│   ├── Course
│   ├── Module
│   └── LearningActivity             [переименование EducationalElement — см. 4.1]
│       ├── Lecture
│       ├── Test
│       ├── Assignment
│       └── Practice
├── ProgressRecord
├── Competency
├── Status                           (enum-класс: status_viewed, status_completed, status_failed, status_passed)
├── AccessPolicy
├── CurrentTime                      [NEW — обёртка над now() для SWRL]
└── AggregateFact                    [NEW — обёртка над LIM2 для aggregate_required]
```

**Обоснование добавлений.**

- `Group` — носитель группового ограничения (rule 8). Альтернатива через `belongs_to` на строке — хуже: теряется возможность назначить свойства самой группе (название, описание), что понадобится в UI симулятора UC-7c.
- `CurrentTime` — единственный индивид этого класса `current_time_ind` создаётся enricher-ом перед каждым reasoning-прогоном. Класс нужен в TBox, чтобы SWRL-правила на дату могли обращаться к нему типобезопасно.
- `AggregateFact` — реификация вычисленного агрегата (среднего/суммы/количества) по (студент × политика × набор элементов). Множественный класс: enricher создаёт по одному индивиду на каждую пару (студент, политика `aggregate_required`), заполняя `for_student`, `for_policy`, `computed_value`. Аналог `CurrentTime` для LIM2 (SWRL не имеет агрегаций) — но не singleton, а семейство фактов, пересоздаваемое перед каждым прогоном reasoner-а. Подробнее — раздел 2.3 шаблон 9.
- `SandboxStudent` — подкласс `Student` для тестового студента в симуляторе UC-7. Все SWRL-правила работают прозрачно (наследование от `Student` сохраняет полную семантику), разделение нужно только на уровне API: `SandboxService` оперирует SandboxStudent-индивидами, `ProgressService` — реальными `Student`. Это защищает прогресс реальных студентов от мутаций при «прогонке сценария» методиста.

**Переименование `EducationalElement → LearningActivity`.** Текущее имя в коде смешивает контейнер (Module) и содержимое. По терминологии L1 (обзор 5 СДО) «activity» — устоявшийся термин атомарного элемента (Moodle), «item» (Canvas), «unit» (Open edX), «step» (Stepik). `LearningActivity` точнее и консистентнее с документацией платформ. Для 3.6.

### 1.3. Объектные свойства

Организованы по назначению. `inv` — обратное свойство (если определено).

| Свойство | Domain | Range | inv | Семантика | Статус |
|---|---|---|---|---|---|
| `has_module` | Course | Module | `is_contained_in_course` | Содержание курса | ✅ есть |
| `is_contained_in_course` | Module | Course | `has_module` | — | ✅ есть |
| `contains_activity` | Module | LearningActivity | `is_contained_in_module` | Содержание модуля | 🔁 переименовать `contains_element` |
| `is_contained_in_module` | LearningActivity | Module | `contains_activity` | — | ✅ есть |
| `has_access_policy` | CourseStructure | AccessPolicy | — | Элемент защищён политикой | ✅ есть |
| `targets_element` | AccessPolicy | CourseStructure | — | Политика ссылается на элемент-пререквизит | ✅ есть |
| `has_author` | AccessPolicy | Methodologist | — | Автор политики | ✅ есть |
| `has_subpolicy` | AccessPolicy | AccessPolicy | — | Связь композиции для AND/OR | 🆕 NEW |
| `targets_competency` | AccessPolicy | Competency | — | Требуемая компетенция | ✅ есть (дубль в 2_rules_setup убрать) |
| `restricted_to_group` | AccessPolicy | Group | — | Ограничение на группу | 🆕 NEW |
| `has_progress_record` | Student | ProgressRecord | `refers_to_student` | Записи прогресса студента | ✅ есть |
| `refers_to_student` | ProgressRecord | Student | `has_progress_record` | — | ✅ есть |
| `refers_to_element` | ProgressRecord | CourseStructure | — | К чему запись | ✅ есть |
| `has_status` | ProgressRecord | Status | — | Текущий статус записи | ✅ есть (сделать Functional) |
| `assesses` | LearningActivity | Competency | — | Активность проверяет компетенцию | ✅ есть |
| `has_competency` | Student | Competency | — | Компетенция студента | ✅ есть (дубль в 2_rules_setup убрать) |
| `is_subcompetency_of` | Competency | Competency | — | Иерархия компетенций (Transitive) | ✅ есть |
| `belongs_to_group` | Student | Group | — | Членство в группе (multi-valued: студент в нескольких группах) | 🆕 NEW |
| `is_subgroup_of` | Group | Group | — | Иерархия групп (Transitive); поток → подгруппа → проектная команда | 🆕 NEW |
| `aggregate_elements` | AccessPolicy | CourseStructure | — | Набор элементов, по grade которых считается агрегат (multi-valued) | 🆕 NEW |
| `for_student` | AggregateFact | Student | — | Для какого студента посчитан агрегат (Functional) | 🆕 NEW |
| `for_policy` | AggregateFact | AccessPolicy | — | К какой политике относится агрегат (Functional) | 🆕 NEW |
| `satisfies` | Student | AccessPolicy | — | Условие политики выполнено (выводится SWRL) | 🆕 NEW |
| `is_available_for` | CourseStructure | Student | — | Элемент доступен студенту (выводится SWRL) | ✅ есть |

**Почему `satisfies` — новое ключевое свойство.** Текущий код выводит `is_available_for` напрямую каждым SWRL-правилом типа `grade_required`, `completion_required` и т.д. Это работает для атомарных типов, но не масштабируется на `and_combination` / `or_combination`: чтобы выразить «элемент доступен, если сработали обе подполитики» или «хотя бы одна», нужна промежуточная ступень — «подполитика выполнена для студента». `satisfies(student, policy)` и есть эта ступень. См. раздел 2.1.

### 1.4. Атрибутивные свойства

| Свойство | Domain | Range | Functional | Семантика | Статус |
|---|---|---|---|---|---|
| `is_active` | AccessPolicy | boolean | ✓ | Политика применяется в reasoning | ✅ есть |
| `is_mandatory` | CourseStructure | boolean | ✓ | Элемент обязателен для roll-up (ФТ-8) | 🔁 переименовать `is_required` |
| `order_index` | CourseStructure | int | ✓ | Порядок в иерархии | ✅ есть |
| `rule_type` | AccessPolicy | string (enum) | ✓ | Один из 9 типов | ✅ есть |
| `passing_threshold` | AccessPolicy | float | ✓ | Нижняя граница оценки | ✅ есть |
| `valid_from` | AccessPolicy | dateTime | ✓ | Начало окна (date_restricted) | 🆕 NEW |
| `valid_until` | AccessPolicy | dateTime | ✓ | Конец окна (date_restricted) | 🆕 NEW |
| `has_grade` | ProgressRecord | float | ✓ | Оценка за элемент | ✅ есть |
| `failed_attempts_count` | ProgressRecord | int | ✓ | Неудачные попытки (перспектива F6) | ✅ есть, пока не используется |
| `started_at` | ProgressRecord | dateTime | ✓ | Начало прохождения | ✅ есть |
| `completed_at` | ProgressRecord | dateTime | ✓ | Завершение | ✅ есть |
| `has_value` | CurrentTime | dateTime | ✓ | Инжектируемое значение now() | 🆕 NEW |
| `aggregate_function` | AccessPolicy | string (enum: AVG / SUM / COUNT) | ✓ | Функция агрегации для aggregate_required | 🆕 NEW |
| `computed_value` | AggregateFact | float | ✓ | Вычисленный enricher-ом агрегат | 🆕 NEW |

**Почему `is_mandatory`, а не `is_required`.** Текущее имя путает с термином «required» из `grade_required`, `completion_required` (типы правил). `is_mandatory` однозначно про обязательность элемента в roll-up. Для 3.6.

**Почему enum `rule_type: string`, а не подклассы `AccessPolicy`.** Подклассы дали бы более типобезопасный TBox, но ценой раздутия иерархии (9 подклассов только под типы + их композиции). Паттерн с дискриминатором — стандартный в онтологическом моделировании AC (Carminati et al., 2011). Допустимые значения перечислены как константы в коде, на уровне TBox — свободный `string`.

### 1.5. Аксиомы

- **Дизъюнктность** (классы не пересекаются):
  - `Student ⊓ Teacher ⊓ Methodologist ⊑ ⊥` (попарно)
  - `Course ⊓ Module ⊓ LearningActivity ⊑ ⊥`
  - `Lecture ⊓ Test ⊓ Assignment ⊓ Practice ⊑ ⊥`
  - `User ⊓ CourseStructure ⊓ Group ⊓ ProgressRecord ⊓ Competency ⊓ AccessPolicy ⊓ Status ⊓ CurrentTime ⊓ AggregateFact ⊑ ⊥` (все корневые — попарно)
- **Functional** (одно значение на индивид):
  - DataProperty: `is_active`, `is_mandatory`, `rule_type`, `passing_threshold`, `valid_from`, `valid_until`, `has_grade`, `started_at`, `completed_at`, `has_value`, `order_index`, `aggregate_function`, `computed_value`.
  - ObjectProperty: `has_status`, `targets_element` (одна атомарная политика = один пререквизит; композитные AND/OR используют `has_subpolicy`, не `targets_element`), `has_author`, `restricted_to_group` (одна group_restricted-политика = одна группа), `refers_to_student`, `refers_to_element`, `for_student`, `for_policy`.
- **Transitive**: `is_subcompetency_of` (уже есть), `is_subgroup_of` (новое, для иерархии групп — раскрывается H-3 inheritance, см. §2.2).
- **Inverse** (пары): `has_module ≡ is_contained_in_course⁻`, `contains_activity ≡ is_contained_in_module⁻`, `has_progress_record ≡ refers_to_student⁻`.

**Почему `has_status` functional.** В ABox одновременно у записи прогресса — ровно один статус. Переходы статуса обрабатываются заменой, не добавлением (LIM6 монотонность OWL — добавить второй статус нельзя, пришлось бы удалять предыдущий). Функциональность делает это формальным ограничением.

**Почему `targets_element` functional.** Атомарное правило ссылается на один пререквизит. Композиция нескольких пререквизитов — через `and_combination` / `or_combination` с `has_subpolicy`, а не через несколько `targets_element` у одной политики. Функциональность блокирует ошибочное моделирование AND-семантики через перегрузку `targets_element`.

### 1.6. Инварианты enricher-а (контракты, не выраженные в TBox)

В TBox невозможно формально ограничить кардинальность класса (OWL оперирует аксиомами на свойствах, не на количестве экземпляров класса). Два инварианта обеспечиваются enricher-ом.

**Инвариант 1 — singleton `CurrentTime`:**

```
# перед каждым reasoning-прогоном
destroy_all_individuals_of(CurrentTime)
now_ind = CurrentTime("current_time_ind")
now_ind.has_value = [datetime.utcnow()]
```

Если enricher не выполнит очистку, в ABox окажется несколько индивидов `CurrentTime` с разными `has_value` → SWRL-правило 5 (date_restricted) сработает для любого из них, что нарушит семантику «текущее время».

**Инвариант 2 — семейство `AggregateFact` per (student, policy):**

```
# перед каждым reasoning-прогоном
destroy_all_individuals_of(AggregateFact)
for policy in all_active_policies_with_rule_type("aggregate_required"):
    elements = policy.aggregate_elements
    fn = policy.aggregate_function          # "AVG" | "SUM" | "COUNT"
    for student in all_students:
        grades = [pr.has_grade for pr in student.has_progress_record
                                if pr.refers_to_element in elements
                                and pr.has_grade is not None]
        if not grades and fn != "COUNT":    # пустой набор → факт не создаётся
            continue
        value = apply_agg(fn, grades)       # AVG — среднее, SUM — сумма, COUNT — длина
        fact = AggregateFact(f"agg_{student.name}_{policy.name}")
        fact.for_student   = [student]
        fact.for_policy    = [policy]
        fact.computed_value = [value]
```

**Почему не держать агрегат как DataProperty на Policy.** Агрегат зависит от студента; свойство на Policy было бы одним значением для всех, что неверно. Альтернатива — DataProperty `computed_aggregate_for(student)` с reified triple — запрещено OWL 2 DL (нельзя навешивать свойство на triple). `AggregateFact` — реификация per-student-policy, чистое DL-решение.

**Почему пустой набор не создаёт факт для AVG/SUM.** Семантика «среднее пусто» нестрого определена. Если у студента нет ни одной оценки по aggregate_elements, политика для него не срабатывает — это корректное поведение (нет данных → нет разрешения, default-deny через CWA). Для COUNT пустой набор = 0 → факт с `computed_value=0`, что осмысленно (можно требовать «выполнено ≥ 3 заданий»).

Оба инварианта — **инженерные**, контролируются тестами в фазе 2 и упоминаются в алгоритме А2 (3.5.4).

### 1.6. Что не моделируется в TBox и почему

- **Прогресс как булева функция**. Состояние «completed/viewed/failed/passed» кодируется связью с `Status`-индивидами, а не как булевы атрибуты `is_completed` / `is_viewed`. Причина: один механизм переключения для всех типов завершения, один functional-property контроль.
- **Временные версии правил**. Правило либо активно (`is_active=true`), либо нет. История изменений — в журнале аудита (вне онтологии), не в TBox. Если понадобится темпоральный анализ «что было доступно вчера» — это перспектива, не ядро.
- **Roll-up-статус на контейнере**. `Module` и `Course` не имеют `has_status` — их завершённость не хранится, а вычисляется алгоритмом А3 по завершённости обязательных потомков (решение 16.04). Это следствие OWL-ограничения: универсальная квантификация «для всех обязательных потомков» невыразима в SWRL.
- **Данные СДО**: исходные Moodle-записи (mdl_user, grade_grades) — не в онтологии. Онтология содержит только нормализованный слой; конверсию делает `IntegrationService` (3.5.3 слой 3, отдельная итерация).

---

## 2. SWRL — каталог правил

### 2.1. Двухуровневая семантика

Ключевое проектное решение. SWRL-правила работают в **двух ступенях**:

**Ступень 1** — для каждого из 10 атомарных и композитных типов собственный шаблон выводит
`satisfies(student, policy)` — «условие данной политики выполнено для данного студента».

**Ступень 2** — единое мета-правило:

```swrl
CourseStructure(?el), has_access_policy(?el, ?p), is_active(?p, true),
Student(?s), satisfies(?s, ?p)
-> is_available_for(?el, ?s)
```

То есть «элемент доступен, если существует активная политика на элементе и студент её удовлетворяет». CWA-слой в application layer доопределяет default-deny для случая, когда ни одна политика не выполнена (раздел 4).

**Что это даёт.**

1. Семантика AND/OR выражается коротко — через `has_subpolicy` без дублирования тел атомарных правил.
2. `rule_type` инкапсулирован в ступени 1 — ступень 2 не знает о типах.
3. Трассировка блокировки (UC-9) имеет один источник правды: «какие `satisfies` сработали, а какие нет». Проще генерировать объяснение.
4. Соответствует логике XACML: Rule → `Permit` → Policy evaluation (Permit-overrides). `satisfies` = Rule-level Permit, `is_available_for` = Policy-level.

**Цена.** Одно дополнительное object-свойство (`satisfies`) и одно мета-правило. Производительность reasoning не страдает — `satisfies` используется только в композитных правилах и в ступени 2; DL-safety сохраняется (все переменные связаны с named individuals).

### 2.2. Вспомогательные правила

**H-1. Наследование компетенций** (уже есть в коде, оставляем без изменений):

```swrl
Student(?s), has_competency(?s, ?sub), is_subcompetency_of(?sub, ?parent)
-> has_competency(?s, ?parent)
```

Работает за счёт `TransitiveProperty is_subcompetency_of` + явного правила на перенос `has_competency` по цепочке. Без явного правила транзитивность `is_subcompetency_of` не распространится на `has_competency` (это разные свойства).

**H-2. Выдача компетенции при завершении оценивающего элемента** (добавлено решением 23.04):

```swrl
Student(?s), has_progress_record(?s, ?pr),
refers_to_element(?pr, ?el), has_status(?pr, status_completed),
assesses(?el, ?c)
-> has_competency(?s, ?c)
```

После завершения элемента, оценивающего компетенцию `?c`, студент её получает. H-1 затем транзитивно поднимает родительские компетенции. Без H-2 студент мог бы быть вынужден иметь `has_competency` *до* прохождения курса (что осмысленно для перезачёта, но не для штатного сценария).

**H-3. Наследование членства в группе по `is_subgroup_of`** (добавлено вместе с поддержкой групповой иерархии):

```swrl
Student(?s), belongs_to_group(?s, ?g), is_subgroup_of(?g, ?parent)
-> belongs_to_group(?s, ?parent)
```

Аналог H-1, но для групп: членство в подгруппе автоматически даёт членство в родительской. Транзитивность `is_subgroup_of` сама по себе не распространяет членство (это разные свойства), правило явное.

### 2.3. Атомарные шаблоны (rule 1–5, 8, 9)

Шаблоны пронумерованы по порядку из §3.2 PROJECT_BIBLE (актуальная нумерация после решения 21.04: 1 completion, 2 grade, 3 viewed, 4 competency, 5 date, 6 and, 7 or, 8 group, 9 aggregate). Все выводят `satisfies`.

**Шаблон 1 — `completion_required`.**

*Смысл.* Политика требует, чтобы студент завершил целевой элемент.

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "completion_required"),
targets_element(?p, ?target),
Student(?s), has_progress_record(?s, ?pr),
refers_to_element(?pr, ?target), has_status(?pr, status_completed)
-> satisfies(?s, ?p)
```

*Пример срабатывания.* Политика `p_module2_requires_m1` требует `completion_required` для `target=module_1`. Студент `ivanov` имеет запись `pr1` с `refers_to_element=module_1`, `has_status=status_completed` → `satisfies(ivanov, p_module2_requires_m1)`.

**Шаблон 2 — `grade_required`.**

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "grade_required"),
targets_element(?p, ?target), passing_threshold(?p, ?th),
Student(?s), has_progress_record(?s, ?pr),
refers_to_element(?pr, ?target), has_grade(?pr, ?g),
swrlb:greaterThanOrEqual(?g, ?th)
-> satisfies(?s, ?p)
```

*Пример.* Политика требует `grade ≥ 75` за `test_1`. Студент получил 80 → условие выполнено.

**Шаблон 3 — `viewed_required`.**

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "viewed_required"),
targets_element(?p, ?target),
Student(?s), has_progress_record(?s, ?pr),
refers_to_element(?pr, ?target), has_status(?pr, status_viewed)
-> satisfies(?s, ?p)
```

*Замечание по Moodle.* В Moodle «viewed» и «completed» — разные состояния activity completion. `viewed_required` допускает более мягкое условие (достаточно открыть элемент), используется для лекций.

**Шаблон 3b — `viewed_via_completed` (расширение семантики).**

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "viewed_required"),
targets_element(?p, ?target),
Student(?s), has_progress_record(?s, ?pr),
refers_to_element(?pr, ?target), has_status(?pr, status_completed)
-> satisfies(?s, ?p)
```

Второе правило с той же головой `satisfies` даёт дизъюнкцию: «viewed через `status_viewed`» ∨ «viewed через `status_completed`». Семантика «completed ⊇ viewed» — кто прошёл элемент, тем более его «видел». Без 3b студент с `status_completed` (но без явного `status_viewed`) не удовлетворял бы `viewed_required` правилу, что контринтуитивно. Это правило закрыло пункт §6.8.1.3 (расхождение happy_path).

**Шаблон 4 — `competency_required` (с иерархией).**

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "competency_required"),
targets_competency(?p, ?req_comp),
Student(?s), has_competency(?s, ?req_comp)
-> satisfies(?s, ?p)
```

*Связь с H-1.* Правило H-1 распространяет `has_competency` вверх по иерархии подкомпетенций. Если студент владеет `comp_basic_syntax`, а `is_subcompetency_of(comp_basic_syntax, comp_python)`, то H-1 выведет `has_competency(ivanov, comp_python)`, и шаблон 4 сработает для политики, требующей `comp_python`.

**Шаблон 5 — `date_restricted`.**

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "date_restricted"),
valid_from(?p, ?from), valid_until(?p, ?until),
CurrentTime(?now_ind), has_value(?now_ind, ?now),
swrlb:greaterThanOrEqual(?now, ?from), swrlb:lessThanOrEqual(?now, ?until),
Student(?s)
-> satisfies(?s, ?p)
```

*Ключевая особенность.* Условие не зависит от индивидуальных фактов студента, но Student в теле нужен — иначе `satisfies` не связан ни с одной парой (student, policy) и ступень 2 не сработает. Связывание `?s` через `Student(?s)` означает: правило срабатывает для всех студентов в ABox одновременно. Это корректно: временное окно универсально.

*Инжекция `current_time_ind`.* Перед reasoning enricher:

1. Удаляет все предыдущие индивиды `CurrentTime`.
2. Создаёт `current_time_ind` с `has_value = datetime.utcnow()`.
3. Запускает reasoner.

Формальная спецификация этого шага — часть алгоритма А2 (3.5.4).

**Шаблон 8 — `group_restricted`.**

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "group_restricted"),
restricted_to_group(?p, ?g),
Student(?s), belongs_to_group(?s, ?g)
-> satisfies(?s, ?p)
```

*Пример.* Политика `p_advanced_only` с `restricted_to_group = grp_advanced`. Студенты из `grp_advanced` удовлетворяют политике, остальные — нет. CWA-слой доопределит недоступность.

**Шаблон 9 — `aggregate_required`.**

*Смысл.* Среднее/сумма/количество оценок студента по заданному набору элементов удовлетворяет порогу.

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "aggregate_required"),
passing_threshold(?p, ?th),
AggregateFact(?f), for_policy(?f, ?p), for_student(?f, ?s), computed_value(?f, ?val),
swrlb:greaterThanOrEqual(?val, ?th)
-> satisfies(?s, ?p)
```

*Гибридная архитектура (LIM2).* SWRL не умеет агрегаций. Enricher перед каждым reasoning-прогоном (а) удаляет все старые `AggregateFact`, (б) для каждой активной политики типа `aggregate_required` и каждого студента вычисляет `computed_value = apply(aggregate_function, grades over aggregate_elements)`, (в) создаёт `AggregateFact` индивид с `for_student`, `for_policy`, `computed_value`. Контракт enricher-а — §1.6 инвариант 2. Pellet затем обрабатывает шаблон 10 обычным Horn-резолвером, не зная об агрегате как таковом.

*Пример.* Политика «доступ к итоговому тесту, если средний балл по модулю 1 ≥ 70».
- `p_final = AccessPolicy("p_final")`
- `p_final.rule_type = "aggregate_required"`
- `p_final.aggregate_function = "AVG"`
- `p_final.aggregate_elements = [quiz_1, quiz_2, quiz_3]`
- `p_final.passing_threshold = 70.0`
- `final_exam.has_access_policy = [p_final]`

Студент Иванов получил `[60, 80, 90]` → `AVG = 76.67`. Enricher создаёт `AggregateFact("agg_ivanov_p_final", for_student=ivanov, for_policy=p_final, computed_value=76.67)`. Шаблон 9 матчит, `76.67 ≥ 70 → satisfies(ivanov, p_final)`. Ступень 2 даёт `is_available_for(final_exam, ivanov)`.

Студент Петров получил `[50, 55, 60]` → `AVG = 55`. `AggregateFact.computed_value = 55`. `55 ≥ 70` ложно → `satisfies` не выводится → CWA-слой даёт default-deny для `final_exam` Петрову.

*Покрытие в СДО.* Moodle gradebook categories (aggregation Mean/Sum/Min/Max), Blackboard weighted grade columns, Open edX subsection grading policy. 3 из 5 платформ штатно; Stepik и Canvas — через ручной расчёт в UI.

*Почему это не `grade_required` с множественными target-ами.* `grade_required` смотрит на одну оценку одного элемента. `aggregate_required` — на функцию от множества оценок. Разная семантика и разный шаблон SWRL.

### 2.4. Композитные шаблоны (rule 6, 7)

Используют `has_subpolicy`. Подполитики — индивиды `AccessPolicy` с собственными `rule_type` (атомарными или композитными).

**Шаблон 7 — `or_combination`.**

Хотя бы одна подполитика выполнена → композитная выполнена.

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "or_combination"),
has_subpolicy(?p, ?sub),
Student(?s), satisfies(?s, ?sub)
-> satisfies(?s, ?p)
```

*Пример.* Политика «доступ к итоговому тесту, если завершил лекцию ИЛИ практикум». Главная политика `p_or` с `has_subpolicy = {p_lecture_done, p_practice_done}`. Каждая подполитика — атомарная `completion_required`. Если студент завершил лекцию → `satisfies(s, p_lecture_done)` → `satisfies(s, p_or)`.

**Шаблон 6 — `and_combination` (бинарный).**

Обе подполитики выполнены → композитная выполнена.

```swrl
AccessPolicy(?p), is_active(?p, true), rule_type(?p, "and_combination"),
has_subpolicy(?p, ?sub1), has_subpolicy(?p, ?sub2), DifferentFrom(?sub1, ?sub2),
Student(?s), satisfies(?s, ?sub1), satisfies(?s, ?sub2)
-> satisfies(?s, ?p)
```

*Ограничение шаблона — два операнда.* SWRL Horn-правила проверяют конкретное число атомов. Для 3 операндов — отдельный шаблон (три `has_subpolicy`, два `DifferentFrom`). Для n операндов либо n шаблонов, либо композиция: `AND(a, b, c) := AND(a, AND(b, c))`.

*Решение (24.04) — жёсткое ограничение AND до арности 3.* В каталоге оставлены только шаблоны 6 (2-арный) и 6b (3-арный); композиция AND-в-AND в явной форме выше 3-го уровня через SWRL не прокидывается из-за запрета вложенных композитов (`validate_by_rule_type` в `PolicyCreate`). Обоснование: (1) 4+ операнда в AND — редкий сценарий для образовательных правил доступа (большинство политик 2–3 условия); (2) расширение N-арности требует либо N шаблонов на каждую арность, либо промежуточного класса `PartialSatisfaction` — последнее ломает двухуровневую семантику `satisfies → is_available_for`, зафиксированную 20.04; (3) ограничение синхронизировано с фронтом (PrimeVue MultiSelect `selectionLimit=3`, CompositePolicyEditor `canAddChild`=false после 3-го условия) и backend-валидацией (Pydantic отклоняет AND с `total>3`). Для случаев с большим числом условий методист оформляет несколько AND-правил и связывает их AND-правилом верхнего уровня — это правомочно, но пока делается вручную. В перспективе — либо UI-сахар над композицией AND-в-AND, либо отдельные N-арные шаблоны для 4/5 операндов.

*Почему `DifferentFrom` обязательно.* SWRL допускает унификацию разных переменных с одним индивидом, если это не запрещено. Без `DifferentFrom(?sub1, ?sub2)` правило сработает для любой подполитики, унифицируя `?sub1 = ?sub2`, — что эквивалентно требованию одной подполитики (семантика OR). `DifferentFrom` форсирует инъективность.

*NAF (отрицание отсутствия)* не поддерживается, поэтому «все подполитики выполнены» нельзя выразить через универсальную квантификацию. Явное перечисление — единственный вариант в Horn-логике. Это формальное ограничение SWRL (LIM3), и ответ на вопрос «почему не произвольная арность» — честный: её нет в самом языке.

### 2.5. Итоговая сводка

| # | Тип | Шаблон | Ступень | Требует новых в TBox |
|---|---|---|---|---|
| 1 | completion_required | Шаблон 1 | satisfies | — |
| 2 | grade_required | Шаблон 2 | satisfies | — |
| 3 | viewed_required | Шаблон 3 + 3b | satisfies | — |
| 4 | competency_required | Шаблон 4 (+ H-1, H-2) | satisfies | — |
| 5 | date_restricted | Шаблон 5 | satisfies | CurrentTime, has_value, valid_from, valid_until |
| 6 | and_combination | Шаблон 6 (2-арный) + 6b (3-арный) | satisfies | has_subpolicy |
| 7 | or_combination | Шаблон 7 | satisfies | has_subpolicy |
| 8 | group_restricted | Шаблон 8 (+ H-3) | satisfies | Group, belongs_to_group, restricted_to_group, is_subgroup_of |
| 9 | aggregate_required | Шаблон 9 | satisfies | AggregateFact, aggregate_function, aggregate_elements, for_student, for_policy, computed_value |
| — | Мета-правило | Ступень 2 | is_available_for | satisfies |

Общее число SWRL-правил в каталоге: **15** (9 атомарных/композитных шаблонов + дополнение 3b + 6b ternary AND + 3 вспомогательных H-1/H-2/H-3 + 1 мета-правило ступени 2). Точный список и грань между атомарными/композитными/вспомогательными зафиксированы в [code/onto/scripts/2_rules_setup.py](../code/onto/scripts/2_rules_setup.py).

**Гибридная архитектура (системное решение).** Два типа (5 date_restricted, 9 aggregate_required) используют одну и ту же схему: enricher инжектирует факт (singleton `CurrentTime` или семейство `AggregateFact`), SWRL сравнивает предвычисленное значение с порогом. Это не ad-hoc обход двух разных ограничений, а единый паттерн обхода класса ограничений SWRL, касающихся внешних/производных значений (LIM1, LIM2). Pattern reuse усиливает обоснование выбора OWL+SWRL: альтернативы F-Logic/ASP умеют `now()` и агрегации из коробки, но цена — уход от стандарта и литературы (§1.1.1).

---

## 3. Связь с верифицируемыми свойствами (СВ-1…СВ-5)

Модель рассчитана так, чтобы все пять свойств выражались на ней стандартными процедурами.

- **СВ-1 Consistency.** Дизъюнктность классов + functional properties + инжекция конкретных фактов в ABox → Pellet выполняет `consistent()` над всей онтологией. Противоречия типа «A требует grade≥80, B требует grade≤50, оба обязательны» обнаруживаются: у резонера не получается построить модель ABox, где свободный студент имел бы одновременно grade в двух непересекающихся интервалах.
- **СВ-2 Acyclicity.** Строится split-node DiGraph из пар `has_access_policy(dst, p) ∧ targets_element(p, src)` → дуга `src → dst`. Косвенные цепочки через `group_restricted` (Group назначается по правилу, правило ссылается на элемент) тоже попадают в граф — `restricted_to_group` разворачивается в дуги через политики назначения групп (формализация А1 в 3.5.4).
- **СВ-3 Reachability.** Для каждого элемента с политиками — поиск модели через резонер с синтетическим студентом. Если не существует набора фактов, при котором `is_available_for(el, synthetic_student) = true`, элемент недостижим.
- **СВ-4 Redundancy и СВ-5 Subsumption.** Используют DL subsumption check на уровне условий правил — сравнивается логическое содержание политик. Двухуровневая семантика с `satisfies` упрощает формулировку: «R1 subsumes R2, если из satisfies_R2 следует satisfies_R1».

Детальная формализация проверок — в 3.5.4 (алгоритмы А1, А4) и 3.6 (имплементация в VerificationService).

---

## 4. CWA-enforcement — место в архитектуре

OWL работает в OWA: отсутствие `is_available_for(el, s)` не означает `¬is_available_for(el, s)`. Для AC нужна дополнительная интерпретация — default-deny. Post-processing шаг (алгоритм А2):

1. Reasoner выводит `is_available_for` для всех пар, где хотя бы одна политика на элементе удовлетворена студентом.
2. CWA-слой принимает решение о доступе как бинарную функцию:
   - Если у элемента нет `has_access_policy` → доступ **разрешён** (default-allow для свободного контента).
   - Если у элемента есть `has_access_policy`, но `is_available_for(el, s)` не выведено → доступ **запрещён** (default-deny для защищённого контента).
   - Если `is_available_for(el, s)` выведено → доступ **разрешён**.

Это стандартный паттерн SWRL-based AC систем (Carminati et al., 2011; Laouar et al., 2025). Формальная спецификация CWA-слоя — часть алгоритма А2 (3.5.4), его позиция в pipeline — часть архитектуры `ReasoningOrchestrator` (C4 решение 19.04).

**Почему CWA не внутри онтологии.** NAF (`not has_access_policy(...)`, `not satisfies(...)`) в SWRL отсутствует из-за OWA — это формальное ограничение Horn-логики с open world, а не упущение. Добавление NAF потребовало бы выхода за OWL 2 DL (в F-Logic или ASP) — см. LIM5. Гибридная архитектура — принятое решение 15.04.

---

## 5. Диф с текущим кодом (вход в раздел 3.6)

Перечень правок, требуемых для приведения кода в соответствие с этой моделью. Приоритет:
- 🔴 блокирует реализацию композитных правил и верификацию
- 🟡 улучшает согласованность, не блокирует
- 🟢 косметика

### 5.1. TBox (`1_ontology_builder.py`)

| # | Правка | Приоритет | Обоснование |
|---|---|---|---|
| T1 | Добавить класс `Group` | 🔴 | Rule 9 group_restricted |
| T2 | Добавить класс `CurrentTime` + DataProperty `has_value` | 🔴 | Rule 5 date_restricted, enricher контракт |
| T3 | Добавить ObjectProperty `has_subpolicy` | 🔴 | Rule 6/7 and/or_combination |
| T4 | Добавить ObjectProperty `belongs_to_group`, `restricted_to_group` | 🔴 | Rule 8 |
| T5 | Добавить ObjectProperty `satisfies` (Student → AccessPolicy) | 🔴 | Двухуровневая семантика |
| T6 | Добавить DataProperty `valid_from`, `valid_until` | 🔴 | Rule 5 |
| T7 | Сделать functional: `has_status`, `is_active`, `has_value`, `passing_threshold`, `valid_from`, `valid_until`, `rule_type` и прочие однозначные | 🟡 | Аксиоматическая корректность + СВ-1 |
| T8 | Добавить дизъюнктность: `Student/Teacher/Methodologist`, `Course/Module/LearningActivity`, `Lecture/Test/Assignment/Practice` | 🟡 | Без дизъюнктности часть ошибок не ловится СВ-1 |
| T9 | Переименовать `EducationalElement → LearningActivity` | 🟢 | Терминологическое выравнивание с L1 |
| T10 | Переименовать `contains_element → contains_activity`, `is_required → is_mandatory` | 🟢 | Устранение путаницы с терминами типов правил |
| T11 | Перенести определение `is_available_for` из `2_rules_setup.py` в `1_ontology_builder.py` | 🟢 | Свойство — часть онтологической схемы (TBox), а не правил вывода. Сейчас разнесено по двум файлам |
| T12 | Сделать `targets_element`, `restricted_to_group`, `has_status`, `has_author` functional | 🟡 | Формализация семантических ограничений, защита СВ-1 от некорректных ABox |
| T13 | Добавить класс `AggregateFact` + ObjectProperty `aggregate_elements` (multi-valued), `for_student` (Functional), `for_policy` (Functional); DataProperty `aggregate_function` (Functional), `computed_value` (Functional) | 🔴 | Rule 9 aggregate_required |

### 5.2. SWRL (`2_rules_setup.py`)

| # | Правка | Приоритет | Обоснование |
|---|---|---|---|
| S1 | Убрать дубли `has_competency`, `targets_competency`, `is_subcompetency_of` (уже определены в builder) | 🟡 | Чистка |
| S2 | Переделать существующие 4 правила (rule 1–4) на вывод `satisfies`, а не `is_available_for` | 🔴 | Двухуровневая семантика |
| S3 | Добавить мета-правило ступени 2 (satisfies → is_available_for) | 🔴 | Интеграция всех шаблонов |
| S4 | Добавить 5 недостающих шаблонов: date_restricted (5), and_combination (6), or_combination (7), group_restricted (8), aggregate_required (9) | 🔴 | Покрытие всех 9 типов из 3.2 |
| S5 | Явно обозначить H-1 (competency inheritance) как вспомогательное правило (комментарием и именованием) | 🟢 | Документирование |
| S6 | Шаблон 9 aggregate_required использует промежуточную реификацию `AggregateFact` — документировать связь enricher-контракта (R4) и SWRL-шаблона | 🟡 | Диагностируемость: разрыв между Python-слоем и SWRL важно показать тестом |

### 5.3. Seed demo (`3_seed_demo_data.py`)

| # | Правка | Приоритет | Обоснование |
|---|---|---|---|
| D1 | Текущий демо — только grade_required; расширить до покрытия всех 9 типов | 🟡 | Нужно для EXP1 (точность вывода), EXP3 (полнота обнаружения конфликтов) |
| D2 | Добавить 3 группы (Group) и членства (belongs_to_group) | 🟡 | Для rule 8 |
| D3 | Добавить `current_time_ind` создание (шаг enricher-а в демо-скрипте) | 🟡 | Для rule 5 |
| D4 | Добавить политику `aggregate_required` с 3 элементами + вычисление `AggregateFact` для каждого демо-студента | 🟡 | Для rule 9 |

### 5.4. Reasoner service (`4_reasoner_service.py`)

| # | Правка | Приоритет | Обоснование |
|---|---|---|---|
| R1 | Вынести Java/Jena → OWLAPI patch в отдельный helper-модуль | 🟢 | Дублируется в любом скрипте reasoning |
| R2 | Перед reasoning — шаг enricher-а: (а) удалить старые `CurrentTime`, (б) создать новый `current_time_ind` с `has_value=utcnow`, (в) затем `sync_reasoner_pellet` | 🔴 | Требование контракта rule 5 |
| R3 | После reasoning — шаг CWA-enforcement (default-deny для элементов с has_access_policy, где нет is_available_for) | 🔴 | Алгоритм А2, решение 15.04 |
| R4 | Перед reasoning — шаг enricher-а по агрегатам: удалить старые `AggregateFact`; для каждой активной политики `aggregate_required` и каждого студента вычислить `computed_value` по `aggregate_function` над `aggregate_elements` и создать `AggregateFact` | 🔴 | Требование контракта rule 9. См. §1.6 инвариант 2 |

Все пункты 🔴 — обязательны для фазы 2. Итоговая таблица правок войдёт в раздел 3.6 PROJECT_BIBLE.md после аналогичного анализа backend-кода.

### 5.5. Статус реализации (23.04)

Раздел 5 — вход в фазу 2. Фаза 2 закрыта 22.04, DI-рефакторинг — 23.04. Сводка фактических статусов по блокам.

**TBox ([1_ontology_builder.py](../code/onto/scripts/1_ontology_builder.py)):** 20 классов / 24 object properties / 14 data properties (после добавления `SandboxStudent`, `is_subgroup_of` и `has_subpolicy`; grep 25.04).

| Пункт | Статус | Примечание |
|---|---|---|
| T1 `Group` | ✅ Блок 1, 21.04 | Класс создан, `belongs_to_group`/`restricted_to_group` подключены |
| T2 `CurrentTime` + `has_value` | ✅ Блок 1 | Singleton `current_time_ind`, enricher инжектирует перед каждым reasoning |
| T3 `has_subpolicy` | ✅ Блок 1 | ObjectProperty, используется в AND/OR, SUB1-эвристике |
| T4 `belongs_to_group`, `restricted_to_group` | ✅ Блок 1 | `restricted_to_group` помечен Functional |
| T5 `satisfies` | ✅ Блок 1 | Двухуровневая семантика (решение 20.04) |
| T6 `valid_from`, `valid_until` | ✅ Блок 1 | Functional DataProperty |
| T7 Functional-декларации | ✅ Блок 1 | `has_status`, `is_active`, `has_value`, `passing_threshold`, `valid_from`, `valid_until`, `rule_type`, `has_grade`, `failed_attempts_count`, `started_at`, `completed_at`, `aggregate_function`, `computed_value` — все Functional |
| T8 Дизъюнктность | ✅ Блок 1 | `AllDisjoint(Student, Teacher, Methodologist)`, `AllDisjoint(Course, Module, LearningActivity)`, `AllDisjoint(Lecture, Test, Assignment, Practice)` |
| T9 `EducationalElement → LearningActivity` | ✅ 20.04 | Переименовано |
| T10 `contains_element → contains_activity`, `is_required → is_mandatory` | ✅ 20.04 | Переименовано, rollup_service обновлён |
| T11 Перенос `is_available_for` в builder | ✅ Блок 1 | Свойство в TBox, не в `2_rules_setup.py` |
| T12 Functional object-properties | ✅ Блок 1 | `targets_element`, `has_author`, `refers_to_student`, `refers_to_element`, `has_status`, `for_student`, `for_policy` |
| T13 `AggregateFact` + `aggregate_elements/for_student/for_policy/aggregate_function/computed_value` | ✅ Блок 1 | Класс + 5 свойств |

**SWRL ([2_rules_setup.py](../code/onto/scripts/2_rules_setup.py)):** 15 правил через `Imp()` (10 шаблонов ступени 1 — включая 3b и 6b — + 3 вспомогательных H-1/H-2/H-3 + 1 мета-правило ступени 2 + правило 3b как отдельный `Imp()`; точный счёт по конструктору `Imp()` в файле).

| Пункт | Статус | Примечание |
|---|---|---|
| S1 Убрать дубли `has_competency`/`targets_competency`/`is_subcompetency_of` | ✅ | Определяются только в builder |
| S2 Атомарные правила выводят `satisfies` | ✅ Блок 1 | 7 шаблонов переведены + `rule_viewed_via_completed` (3b, 23.04) |
| S3 Мета-правило `satisfies → is_available_for` | ✅ Блок 1 | `rule_meta_available` |
| S4 5 новых шаблонов (date, and, or, group, aggregate) | ✅ Блоки 1/3 | date, group, aggregate — Блок 1; AND-2, AND-3, OR — Блок 3. AND арность ≤3 зафиксирована решением 24.04 |
| S5 H-1 competency inheritance | ✅ Блок 1 | `rule_competency_inheritance` + комментарий |
| S6 Документирование связи `AggregateFact` ↔ enricher | ✅ Блок 1 | Комментарий в шаблоне 9 + тест `test_aggregate_required_avg_pass` |

Дополнительно (решение 23.04 + поддержка иерархии групп): **H-2** `rule_competency_from_progress` — завершение элемента с `assesses=C` выдаёт студенту `has_competency=C`; **H-3** `rule_group_inheritance` — членство в подгруппе автоматически даёт членство в родительской через `is_subgroup_of`; **шаблон 3b** `rule_viewed_via_completed` — `viewed_required` срабатывает и при `status_completed`, не только `status_viewed`. Все три — отражены в §2.2 и §2.3 как отдельные правила каталога.

**Seed ([3_seed_demo_data.py](../code/onto/scripts/3_seed_demo_data.py) + [scenarios/happy_path.py](../code/onto/scenarios/happy_path.py)):** тонкая обёртка над `happy_path.build_and_save()`.

| Пункт | Статус | Примечание |
|---|---|---|
| D1 9 типов в демо | ✅ Блок 3 | `policy_workshop_window` (date), `policy_extra_advanced_only` (group), `policy_final_avg` (aggregate AVG ≥ 70), AND/OR/остальные типы собраны в 9 политик |
| D2 3 группы + `belongs_to_group` | ✅ Блок 2 | `group_standard`, `group_advanced` + членство |
| D3 `current_time_ind` в seed | ✅ Блок 2 | Маркер, перезаписывается enricher-ом |
| D4 Политика `aggregate_required` + `AggregateFact` на демо-студентов | ✅ Блок 3 | `policy_final_avg` + second test/progress |

**Reasoner helper ([services/reasoning/](../code/backend/src/services/reasoning/)):** выделен в подпакет DI-рефакторингом 23.04.

| Пункт | Статус | Примечание |
|---|---|---|
| R1 Java/Jena→OWLAPI patch как helper | ✅ 23.04 | `_patched_sync_reasoner` в `orchestrator.py` |
| R2 Enricher `CurrentTime` | ✅ Блок 1 | `_enricher.py::ensure_current_time` |
| R3 CWA-enforcement | ✅ Блок 2 | В [services/access/service.py](../code/backend/src/services/access/service.py), не в reasoning — при CWA-default-deny нужна элементная политика, а это уровень AccessService |
| R4 Enricher `AggregateFact` | ✅ Блок 1 | `_enricher.py::materialize_aggregates` |

**Итого:** 27 пунктов из 27 закрыты. Сверх перечня раздела 5 в коде также появились (не блокеры, расширения семантики): класс `SandboxStudent` (изоляция симулятора UC-7), свойство `is_subgroup_of` + правило H-3 (иерархия групп), правило 3b (`viewed_required` ⊇ `status_completed`). Отклонения ABox happy-path от §6.3/§6.7 (нюансы a/б/в) зафиксированы в §6.8.1.

---

## 6. ABox демо-курса

### 6.1. Назначение

ABox — конкретный набор индивидов, по которому проверяется: (1) все 9 SWRL-шаблонов действительно срабатывают на реальных данных, (2) каждое из 5 верифицируемых свойств может быть обнаружено алгоритмами А1, А4, А6 на специально подготовленных нарушениях. Документ служит трём целям:

1. Спецификация для seed-скрипта `3_seed_demo_data.py` после его расширения (D1–D4 в §5.3).
2. Иллюстративный пример для главы 2 ПЗ §2.3 (как работают правила).
3. Ground-truth для EXP1 (Precision/Recall верификации), EXP3 (accuracy вывода по 9 типам), EXP6 (демо-сценарий).

Выделяется два слоя: **основной happy-path** — один курс на 4 студента, все 9 типов правил срабатывают корректно; **негативные мини-ABox** — отдельные фрагменты, каждый ломает одно свойство СВ-1…СВ-5 ровно в одном месте.

### 6.2. Принципы построения

- **Минимальность**: ровно столько индивидов, чтобы каждый шаблон срабатывал **и** положительно, **и** отрицательно хотя бы на одном студенте.
- **Независимость типов**: разные типы правил навешаны на разные элементы. Две политики на одном элементе — только там, где это намеренно (мини-ABox `bad_sv4_redundant_policies`).
- **Реалистичность курса**: содержательная структура на Python — узнаваемая для читателя ПЗ, не абстрактное «Module A → Module B».
- **Имена индивидов**: `snake_case`, без дефисов, совместимость с Owlready2 и Pellet.
- **Даты**: все датные диапазоны относительны 21.04.2026 — сегодняшняя дата. При реальном запуске `current_time_ind.has_value` инжектируется enricher-ом, и окна пересчитываются относительно `datetime.utcnow()`.

### 6.3. Структура курса `course_python_basics`

```
course_python_basics (Course)
├── module_0_intro (Module, is_mandatory=false)
│   └── lecture_0_welcome (Lecture)
├── module_1_syntax (Module, is_mandatory=true)
│   ├── lecture_1_variables (Lecture, is_mandatory=true)
│   ├── lecture_2_operators (Lecture, is_mandatory=true)    ← p1
│   ├── quiz_1 (Test, is_mandatory=true)                    ← p3, assesses=comp_basic_syntax
│   └── practice_1 (Practice, is_mandatory=true)            assesses=comp_basic_syntax
├── module_2_functions (Module, is_mandatory=true)          ← p2
│   ├── lecture_3_functions (Lecture, is_mandatory=true)
│   ├── quiz_2 (Test, is_mandatory=true)                    assesses=comp_functions
│   └── practice_2 (Practice, is_mandatory=true)            assesses=comp_functions
├── module_3_oop (Module, is_mandatory=true)                ← p4
│   ├── lecture_4_classes (Lecture, is_mandatory=true)
│   ├── quiz_3 (Test, is_mandatory=true)                    ← p7, assesses=comp_oop
│   └── practice_3 (Practice, is_mandatory=true)            ← p6, assesses=comp_oop
├── seasonal_workshop (Lecture, is_mandatory=false)         ← p5
├── extra_material (Lecture, is_mandatory=false)            ← p8
└── final_exam (Test, is_mandatory=true)                    ← p9
```

Символом ` ← pN` помечены элементы, на которых висит политика типа N (см. §6.5).

### 6.4. Пользователи, группы, компетенции

**Группы:** `grp_standard`, `grp_advanced`, `grp_remote` (экземпляры класса `Group`) + проектная подгруппа `grp_advanced_alpha`, у которой `is_subgroup_of = [grp_advanced]`. После прогона H-3 студент-член `grp_advanced_alpha` автоматически получает `belongs_to_group(student, grp_advanced)` — это покрывает шаблон 8 на цепочке длины ≥ 2 без явного дублирования членства в seed.

**Иерархия компетенций:** `is_subcompetency_of` — транзитивное свойство:

```
comp_python
├── comp_basic_syntax
├── comp_functions
│   └── comp_oop          (через is_subcompetency_of(comp_oop, comp_functions))
```

Такая иерархия позволяет студенту с компетенцией `comp_oop` автоматически получать `comp_functions` и `comp_python` через вспомогательное SWRL-правило H-1.

**Методист:** `methodologist_smirnov` — автор всех политик.

**Студенты (4 профиля):**

| Индивид | Группа | Явные компетенции | Роль в сценарии |
|---|---|---|---|
| `student_ivanov` | `grp_standard` | `comp_basic_syntax` | «усердный средний»: завершает модули 1–2, не имеет `comp_functions` → недоступен module_3 |
| `student_petrov` | `grp_standard` | — | «отстающий»: только просмотрел пару лекций, провалил quiz_1 |
| `student_sidorov` | `grp_advanced_alpha` (через H-3 → `grp_advanced`) | `comp_basic_syntax`, `comp_functions`, `comp_oop` | «отличник»: проходит весь курс, единственный с доступом к `extra_material` и `practice_3` |
| `student_korolev` | `grp_remote` | `comp_basic_syntax` (из внешней системы) | «перезачёт»: компетенция получена до курса, но прогресса по элементам нет |

### 6.5. Политики (покрытие 9 типов)

| # | Индивид политики | Тип | Атрибуты | На каком элементе |
|---|---|---|---|---|
| p1 | `p1_lecture2_requires_lecture1` | `completion_required` | `targets_element=lecture_1_variables` | `lecture_2_operators.has_access_policy` |
| p2 | `p2_module2_requires_quiz1_grade` | `grade_required` | `targets_element=quiz_1`, `passing_threshold=75.0` | `module_2_functions.has_access_policy` |
| p3 | `p3_quiz1_requires_viewed_lecture1` | `viewed_required` | `targets_element=lecture_1_variables` | `quiz_1.has_access_policy` |
| p4 | `p4_module3_requires_comp_functions` | `competency_required` | `targets_competency=comp_functions` | `module_3_oop.has_access_policy` |
| p5 | `p5_seasonal_workshop_date_window` | `date_restricted` | `valid_from=2026-04-15T00:00:00Z`, `valid_until=2026-06-30T23:59:59Z` | `seasonal_workshop.has_access_policy` |
| p6 | `p6_practice3_and` | `and_combination` | `has_subpolicy={p6_sub_a, p6_sub_b}` | `practice_3.has_access_policy` |
| — | `p6_sub_a_lecture4_completion` | `completion_required` | `targets_element=lecture_4_classes` | подполитика p6 |
| — | `p6_sub_b_quiz3_grade70` | `grade_required` | `targets_element=quiz_3`, `passing_threshold=70.0` | подполитика p6 |
| p7 | `p7_quiz3_or` | `or_combination` | `has_subpolicy={p7_sub_a, p7_sub_b}` | `quiz_3.has_access_policy` |
| — | `p7_sub_a_comp_basic_syntax` | `competency_required` | `targets_competency=comp_basic_syntax` | подполитика p7 |
| — | `p7_sub_b_quiz2_grade85` | `grade_required` | `targets_element=quiz_2`, `passing_threshold=85.0` | подполитика p7 |
| p8 | `p8_extra_material_advanced` | `group_restricted` | `restricted_to_group=grp_advanced` | `extra_material.has_access_policy` |
| p9 | `p9_final_exam_avg_prereq` | `aggregate_required` | `aggregate_function="AVG"`, `aggregate_elements={quiz_1, quiz_2, practice_1, practice_2}`, `passing_threshold=70.0` | `final_exam.has_access_policy` |

Все политики имеют `is_active=true`, `has_author=methodologist_smirnov`. Подполитики p6_sub_*, p7_sub_* **не** имеют `has_access_policy` сами по себе: они существуют только как композиционные части, `is_active` ставим `true` ради единообразия (шаг 1 SWRL проверяет `is_active`).

### 6.6. Прогресс студентов

Записи `ProgressRecord` (имена индивидов — `pr_{student}_{element}` для краткости).

| Элемент | ivanov | petrov | sidorov | korolev |
|---|---|---|---|---|
| `lecture_0_welcome` | `status=viewed` | `status=viewed` | `status=viewed` | — |
| `lecture_1_variables` | `status=completed` | `status=viewed` | `status=completed` | — |
| `lecture_2_operators` | `status=completed` | — | `status=completed` | — |
| `quiz_1` | `grade=80.0`, `status=completed` | `grade=50.0`, `status=failed` | `grade=95.0`, `status=completed` | — |
| `practice_1` | `grade=70.0`, `status=completed` | — | `grade=85.0`, `status=completed` | — |
| `lecture_3_functions` | `status=completed` | — | `status=completed` | — |
| `quiz_2` | `grade=75.0`, `status=completed` | — | `grade=90.0`, `status=completed` | — |
| `practice_2` | `grade=65.0`, `status=completed` | — | `grade=80.0`, `status=completed` | — |
| `lecture_4_classes` | — | — | `status=completed` | — |
| `quiz_3` | — | — | `grade=75.0`, `status=completed` | — |
| `practice_3` | — | — | `grade=70.0`, `status=completed` | — |

**Инвариант ABox.** Прогресс Корoлева намеренно пуст: его единственная роль — продемонстрировать срабатывание шаблона 4 (`competency_required`) при компетенции, полученной вне прогресса курса, и шаблона 5 (`date_restricted`) для студента без записей.

### 6.7. Ожидаемые выводы резонера (happy-path)

После `reason_and_materialize` на этом ABox ожидается следующая таблица `is_available_for(element, student)`. Колонки — студенты; ✅ — элемент доступен через вывод политики или через default-allow (нет `has_access_policy`); ❌ — default-deny или каскадная блокировка родительского модуля; 🔒 — каскадная блокировка (сам элемент без политики, но родительский модуль недоступен).

| Элемент | Политика на нём | ivanov | petrov | sidorov | korolev |
|---|---|---|---|---|---|
| `lecture_0_welcome` | — | ✅ | ✅ | ✅ | ✅ |
| `lecture_1_variables` | — | ✅ | ✅ | ✅ | ✅ |
| `lecture_2_operators` | p1 completion | ✅ | ❌ | ✅ | ❌ |
| `quiz_1` | p3 viewed | ✅ | ✅ | ✅ | ❌ |
| `practice_1` | — | ✅ | ✅ | ✅ | ✅ |
| `module_2_functions` | p2 grade≥75 | ✅ | ❌ | ✅ | ❌ |
| `lecture_3_functions` | — | ✅ | 🔒 | ✅ | 🔒 |
| `quiz_2` | — | ✅ | 🔒 | ✅ | 🔒 |
| `practice_2` | — | ✅ | 🔒 | ✅ | 🔒 |
| `module_3_oop` | p4 comp_functions | ❌ | ❌ | ✅ | ❌ |
| `lecture_4_classes` | — | 🔒 | 🔒 | ✅ | 🔒 |
| `quiz_3` | p7 or(comp \| grade) | 🔒¹ | 🔒 | ✅ | 🔒² |
| `practice_3` | p6 and(compl + grade) | 🔒 | 🔒 | ✅ | 🔒 |
| `seasonal_workshop` | p5 date (сейчас активно) | ✅ | ✅ | ✅ | ✅ |
| `extra_material` | p8 group=advanced | ❌ | ❌ | ✅ | ❌ |
| `final_exam` | p9 aggregate | ✅ | ❌ | ✅ | ❌ |

¹ ² — шаблон 7 (OR) сам по себе у ivanov и korolev сработал бы (comp_basic_syntax), но элемент внутри module_3_oop, к которому нет доступа → каскад.

**Покрытие шаблонов.** Каждый из 9 шаблонов имеет в таблице хотя бы одну строку с положительным выводом и хотя бы одну — с отрицательным. Это нужно для EXP3 (accuracy по типам): без обоих знаков метрика вырождается.

**Покрытие enricher-контрактов.** Шаблон 5 (p5) демонстрирует работу `CurrentTime`: без инжекции `current_time_ind` семантика «сейчас внутри окна» не выражается в SWRL. Шаблон 9 (p9) демонстрирует работу `AggregateFact`: enricher для каждого студента создаёт индивид `agg_{student}_p9` со своим `computed_value`. Для ivanov `computed_value = (80+75+70+65)/4 = 72.5 ≥ 70 → satisfies`; для petrov `computed_value = 50 / 1 = 50` (пустые записи исключены) `< 70 → deny`; для korolev — `AggregateFact` не создаётся вовсе (нет записей) → `satisfies` не выводится → default-deny.

### 6.8. Негативные мини-ABox (под СВ-1…СВ-5)

Эти фрагменты — отдельные файлы-оверлеи поверх минимальной онтологии (2–3 элемента, 2 студента). Каждый ломает одно свойство. Использование: `verification_service.full_verify(course_id)` на таком ABox должен вернуть отчёт с найденным нарушением.

**`bad_sv1_disjointness_violation`** — СВ-1 Consistency.
- Индивид `user_mixed_role` помечен одновременно типом `Student` и `Methodologist`. Класс-дизъюнктность (§1.5) нарушена.
- Ожидаемое: Pellet выбрасывает `OwlReadyInconsistentOntologyError`. `VerificationService` ловит исключение, отчёт СВ-1: `"Student ⊓ Methodologist ⊑ ⊥ violated by user_mixed_role"`.
- Алгоритм: А2 стадия REASON (обработка ошибок), маршрутизация в отчёт.

**`bad_sv2_rule_cycle`** — СВ-2 Acyclicity.
- Два модуля `module_A`, `module_B`, две политики: `p_cycle_ab` — `completion_required` с `targets_element=module_B` на `module_A`; `p_cycle_ba` — зеркально.
- Ожидаемое: А1 split-node DiGraph находит цикл `module_A.complete → module_B.access → module_B.complete → module_A.access → module_A.complete`. Отчёт СВ-2 с указанием пары политик.
- Алгоритм: А1 (`find_all_cycles` в UC-6).

**`bad_sv3_atomic_unreach_threshold`** — СВ-3 Reachability (атомарная).
- Политика `p_unreach_threshold`: `grade_required`, `passing_threshold=150.0` (значение вне диапазона оценок, которые существуют в системе: `has_grade ∈ [0, 100]`).
- Ожидаемое: А4 Проход 1 (`check_atomic_satisfiability`) возвращает `UNSAT` без запуска Pellet. Отчёт СВ-3 с указанием политики и причины «threshold=150.0 вне диапазона [0, 100]».

**`bad_sv3_empty_date_window`** — СВ-3 Reachability (атомарная, date).
- Политика `p_unreach_date`: `date_restricted`, `valid_from=2026-06-01`, `valid_until=2026-05-01` (from > until, пустое окно).
- Ожидаемое: А4 Проход 1 возвращает `UNSAT`. Отчёт с указанием «пустое окно».

**`bad_sv3_structural_unreach`** — СВ-3 Reachability (структурная, Проход 2).
- Три элемента `A, B, C`, политики: A защищена `completion_required(B)`, B защищена `completion_required(C)`, C защищена `completion_required(A)`. Формально 3-цикл — мог бы поймать и СВ-2, но если цикл «длинный» и проходит через композитные политики, А4 ловит его по недостижимости через fixed-point.
- Ожидаемое: А4 Проход 2 завершает фиксированной точкой с пустым множеством достижимых элементов (при synthetic_student без прогресса). Отчёт: «элементы A, B, C не могут стать доступными ни одному студенту».

**`bad_sv4_redundant_policies`** — СВ-4 Redundancy.
- Два `grade_required` правила на одном элементе `quiz_R`: `p_red_strong` с `threshold=80`, `p_red_weak` с `threshold=60`. Тот же `targets_element=quiz_R_prereq`.
- Любой студент, удовлетворивший `p_red_strong`, автоматически удовлетворяет `p_red_weak` (grade≥80 ⟹ grade≥60). В OR-семантике шага 2 одной сработавшей политики достаточно → `p_red_strong` избыточна (её наличие не меняет множество студентов с доступом).
- Ожидаемое: А6 `SubsumptionChecker` через `synthetic_prerequisites` + Pellet subsumption выносит вердикт «p_red_strong redundant (subsumed by p_red_weak)». Отчёт СВ-4.

**`bad_sv5_subject_subsumption`** — СВ-5 Subject Subsumption.
- На одном элементе `elem_S` две политики:
  - `p_subj_all`: `grade_required`, `threshold=70`, `targets_element=quiz_prereq`.
  - `p_subj_group`: `and_combination` из (`grade_required threshold=70, targets_element=quiz_prereq`) + (`group_restricted, restricted_to_group=grp_advanced`).
- Любой студент, удовлетворяющий `p_subj_group`, удовлетворяет и `p_subj_all` (те же критерии + более жёсткий групповой фильтр). При этом `p_subj_all` срабатывает для более широкой аудитории. `p_subj_group` поглощена `p_subj_all` на уровне **subjects** (множество студентов).
- Ожидаемое: А6 различает СВ-4 (одинаковые условия) и СВ-5 (разные субъекты при одном условии) по witness — если множество студентов, удовлетворяющих подмножеству условий, шире → это subject subsumption. Отчёт СВ-5.

### 6.8.1. Отклонения фактической сборки от спецификации (22.04)

При реализации скриптов `code/onto/scenarios/` и прогоне Pellet на собранном ABox обнаружены три расхождения с §6.3/§6.6/§6.7:

1. **Прямые элементы курса обёрнуты в `module_extras`.** `contains_element` в TBox имеет `domain=Module`, а `seasonal_workshop`, `extra_material`, `final_exam` по §6.3 висят прямо на курсе. Owlready2 в OWA выводит `Module(course_python_basics)` при `course.contains_element = ...`, что нарушает `AllDisjoint([Course, Module, EducationalElement])`. Минимальный фикс — обёрточный `module_extras: Module` с `is_required=false`. Альтернатива (расширение `contains_element domain=[Module, Course]`) отложена, чтобы не ломать inverse `is_contained_in_module` и существующие тесты.
2. **`quiz_3`/`practice_3` не помечены `assesses=comp_oop`.** С `comp_oop ⊑ comp_functions` и p4 `competency_required(comp_functions)` на `module_3_oop` GraphValidator находит структурный цикл: `p4` раскрывается через `assesses` на всех под-компетенциях (A1, §6.2), даёт дугу `practice_3.complete → module_3_oop.access`, а hierarchy descent даёт обратную `module_3_oop.access → practice_3.access`. Цикл реальный, детектор прав. `comp_oop` сохраняется только как sub-компетенция `comp_functions` — `student_sidorov` получает её извне через `has_competency = [comp_oop]`, и H-1 поднимает цепочку вверх, демонстрируя наследование без создания цикла.
3. **SWRL rule 3 `viewed_required` требует именно `status_viewed`.** Строго, `status_completed` ≠ `status_viewed`: если студент завершил элемент, но не имеет отдельной записи «viewed», rule 3 базовый не сработает. Решение 23.04 закрыло этот разрыв через шаблон **3b** `rule_viewed_via_completed` (см. §2.3): второй `Imp()` с той же головой даёт дизъюнкцию «status_viewed ∨ status_completed». Матрица §6.7 теперь корректна и операционно: `viewed_required` срабатывает у студентов с `status_completed` без явной записи `viewed`.

### 6.9. Связь с экспериментами и фазой 2

| Артефакт | Использование |
|---|---|
| Основной happy-path ABox (§6.3–6.7) | Seed `3_seed_demo_data.py` (D1–D4, расширение с 1 политики до 9); EXP3 accuracy по 9 типам; EXP6 демо-сценарий; UC-7 симулятор — предзаполненный сценарий |
| `bad_sv1`, `bad_sv2` | EXP2 (Precision/Recall обнаружения циклов и консистентности); тесты СВ-1, СВ-2 в `verification_service` |
| `bad_sv3_atomic_*`, `bad_sv3_structural` | EXP2 (reachability); тесты СВ-3 |
| `bad_sv4`, `bad_sv5` | EXP1 (Precision/Recall СВ-4/5); тесты `SubsumptionChecker` (SUB8 в §А6.10 SAT_ALGORITHMS) |

Формат хранения в репозитории (решение для фазы 2):

```
code/onto/scenarios/
├── happy_path.py              — расширение 3_seed_demo_data.py
├── bad_sv1_disjointness.py
├── bad_sv2_cycle.py
├── bad_sv3_atomic_threshold.py
├── bad_sv3_empty_date.py
├── bad_sv3_structural.py
├── bad_sv4_redundant.py
└── bad_sv5_subject.py
```

Каждый скрипт загружает `edu_ontology_with_rules.owl` и добавляет свой фрагмент ABox; результат сохраняется как отдельный `.owl` для использования в тестах (`tests/test_verification_scenarios.py`). Имена сценариев и их ожидаемые verdict'ы фиксируются в `tests/fixtures/scenarios_ground_truth.json`, по которому считаются Precision/Recall в EXP1/EXP2.

---

## 7. REST API — ревизия OpenAPI

### 7.1. Назначение

Ревизия текущего [openapi.yaml](../code/backend/src/openapi.yaml) (версия 2.1.0, 18 эндпоинтов) под проектные решения 3.5.1 (C4 DSL) и 3.6 (пункты B1–B10). Раздел даёт: (1) карту что есть vs. что должно быть по UC-1…UC-10, (2) контракт недостающих эндпоинтов (UC-6, UC-9, UC-3 dry-run) с примерами запросов/ответов, (3) расширение схем под 9 типов правил и 5 верифицируемых свойств, (4) контракт ошибок с привязкой к НФТ-5 (rollback при inconsistency).

Для реализации (фаза 2): этот раздел → `openapi.yaml` v2.2.0 → генерация FastAPI-роутеров и Pydantic-схем.

### 7.2. Текущее состояние (OpenAPI 2.1.0 + факт. код)

Таблица фактических эндпоинтов с покрытием UC. 18 маршрутов, 5 роутеров.

| # | Method + Path | Router | UC | ФТ | Статус |
|---|---|---|---|---|---|
| 1 | `GET /ontology/meta` | courses | — (UI data) | — | ✅ есть |
| 2 | `GET /courses/{id}/tree` | courses | — (UI data) | — | ✅ есть |
| 3 | `GET /policies` | policies | UC-2 | ФТ-1 | ✅ есть |
| 4 | `POST /policies` | policies | UC-1, UC-3 | ФТ-1, ФТ-5 | ⚠️ валидация внутри, без явного dry-run; errors без структуры |
| 5 | `PUT /policies/{id}` | policies | UC-2 | ФТ-1 | ✅ есть |
| 6 | `DELETE /policies/{id}` | policies | UC-2 | ФТ-1 | ✅ есть |
| 7 | `PATCH /policies/{id}/toggle` | policies | UC-2 | ФТ-1 | ✅ есть |
| 8 | `POST /courses/{id}/sync` | integration | UC-10 | ФТ-4 | ⚠️ не триггерит UC-6 после импорта (решение 18.04) |
| 9 | `POST /events/progress` | integration | UC-5 | ФТ-8 | ⚠️ не относится к integration по DSL (B4) |
| 10 | `GET /access/student/{sid}/course/{cid}` | integration | UC-4 | ФТ-2, ФТ-6 | ⚠️ должен быть в отдельном `/access` роутере (B3) |
| 11 | `GET /sandbox/state` | sandbox | UC-7c | ФТ-7 | ✅ есть |
| 12 | `POST /sandbox/progress` | sandbox | UC-7b | ФТ-7 | ✅ есть |
| 13 | `DELETE /sandbox/progress/{id}` | sandbox | UC-7b | ФТ-7 | ✅ есть |
| 14 | `POST /sandbox/reset` | sandbox | UC-7a | ФТ-7 | ✅ есть |
| 15 | `PUT /sandbox/competencies` | sandbox | UC-7b | ФТ-7 | ✅ есть |
| 16 | `GET /competencies` | competencies | — | — | ✅ есть |
| 17 | `POST /competencies` | competencies | — | — | ✅ есть |
| 18 | `POST /competencies/sync` | competencies | UC-10 | ФТ-4 | ✅ есть |

**Пробелы по UC-1…UC-10:**

| UC | Название | Что есть | Что отсутствует |
|---|---|---|---|
| UC-1 | Создать правило | `POST /policies` | — |
| UC-2 | Редактировать/удалить | PUT/DELETE/PATCH /policies | — |
| UC-3 | Валидация при создании | Валидация внутри POST /policies | Нет явного dry-run-эндпоинта; отчёт об ошибке не структурирован |
| UC-4 | Проверить доступ | `GET /access/...` | — (но путь в integration — перенести) |
| UC-5 | Событие прогресса | `POST /events/progress` | — (перенести из integration в progress) |
| UC-6 | Полная верификация курса | — | **Весь контроллер + сервис отсутствуют** |
| UC-7 | Симулятор (a/b/c) | sandbox router | — |
| UC-8 | Агрегация завершённости | Триггерится внутри `/events/progress` | Нет отдельного endpoint просмотра roll-up состояния |
| UC-9 | Объяснение блокировки | — | **Endpoint explain отсутствует** |
| UC-10 | Импорт курса | `POST /courses/{id}/sync` | Нет автоматического UC-6 после импорта (решение 18.04) |

### 7.3. Целевой API (после фазы 2)

Карта сгруппирована по проектным роутерам из C4 DSL (решение 19.04 + B1–B4 в §3.6 PROJECT_BIBLE). Версия API → `v2.2.0`.

#### 7.3.1. PolicyController (`/api/v1/policies`)

| Method + Path | UC | ФТ | Категория | Комментарий |
|---|---|---|---|---|
| `GET /policies` | UC-2 | ФТ-1 | существует | + фильтр `rule_type` |
| `POST /policies` | UC-1, UC-3 | ФТ-1, ФТ-5 | переделать | return структурированный отчёт при 400 (B6) |
| `POST /policies/validate` | UC-3 | ФТ-5 | **добавить** | dry-run: вернёт `PolicyValidationReport` без сохранения (B1) |
| `PUT /policies/{id}` | UC-2 | ФТ-1 | существует | тот же структурированный отчёт при конфликте |
| `DELETE /policies/{id}` | UC-2 | ФТ-1 | существует | |
| `PATCH /policies/{id}/toggle` | UC-2 | ФТ-1 | существует | |

#### 7.3.2. AccessController (`/api/v1/access`) — **новый роутер (B3)**

| Method + Path | UC | ФТ | Категория |
|---|---|---|---|
| `GET /access/student/{sid}/course/{cid}` | UC-4 | ФТ-2, ФТ-6 | перенести из integration |
| `GET /access/student/{sid}/element/{eid}` | UC-4 | ФТ-2 | **добавить** (одиночный элемент, чаще чем полная матрица) |
| `GET /access/student/{sid}/element/{eid}/explain` | UC-9 | ФТ-6, ФТ-6.1 | **добавить**: вернёт `BlockingExplanation` |

#### 7.3.3. ProgressController (`/api/v1/progress`) — **новый роутер (B4)**

| Method + Path | UC | ФТ | Категория |
|---|---|---|---|
| `POST /progress/events` | UC-5 | ФТ-8 | перенести из integration (`/events/progress`) |
| `GET /progress/student/{sid}/course/{cid}` | UC-4, UC-8 | ФТ-8 | **добавить**: roll-up состояние (какие module/course завершены) |

#### 7.3.4. VerificationController (`/api/v1/verify`) — **новый роутер (B2)**

| Method + Path | UC | ФТ | СВ | Категория |
|---|---|---|---|---|
| `GET /verify/course/{id}` | UC-6 | ФТ-3 | 1, 2, 3 | **добавить**: базовая верификация (must) |
| `POST /verify/course/{id}/full` | UC-6 | ФТ-3 | 1, 2, 3, 4, 5 | **добавить**: включая subsumption/redundancy (медленнее) |
| `GET /verify/reports/{run_id}` | UC-6 | ФТ-3 | — | **добавить**: получить сохранённый отчёт (кэш C9) |

Решение: обычный `GET /verify/course/{id}` выполняет СВ-1/2/3 (быстро, ≤ НФТ-3 10 с); `POST .../full` запускает тяжёлую А6 (Subsumption) и возвращает `run_id` для асинхронного чтения через `GET /verify/reports/{run_id}`. Это обходит НФТ-3 для дорогой верификации.

#### 7.3.5. IntegrationController (`/api/v1/integration`) — упростить (B5)

| Method + Path | UC | ФТ | Категория |
|---|---|---|---|
| `POST /integration/courses/{id}/import` | UC-10 | ФТ-4 | переименовать из `/courses/{id}/sync` |
| `POST /integration/courses/{id}/import/verify` | UC-10 + UC-6 | ФТ-4, ФТ-3 | **добавить**: импорт + автоматический UC-6 (решение 18.04) |
| `POST /integration/competencies/sync` | — | ФТ-4 | перенести из `/competencies/sync` |

#### 7.3.6. CourseController (`/api/v1/courses`) — UI data

| Method + Path | UC | Категория |
|---|---|---|
| `GET /courses` | — | **добавить**: список курсов (сейчас нет — фронт хардкодит) |
| `GET /courses/{id}` | — | **добавить**: метаданные одного курса |
| `GET /courses/{id}/tree` | UC-1 (редактор), UC-6 (отчёт) | существует |

#### 7.3.7. SandboxController и CompetencyController

Без структурных изменений. Эндпоинты те же. Внутри `SandboxService` — переиспользование `AccessService` (B8), на API это не влияет.

#### 7.3.8. Служебные

| Method + Path | Категория | Комментарий |
|---|---|---|
| `GET /ontology/meta` | существует | дополнить полем `verifiable_properties` (СВ-1…СВ-5) — для UI отчёта |
| `GET /health` | **добавить** | liveness-probe (НФТ-5, Docker Compose, FIX10) |
| `GET /health/reasoner` | **добавить** | проверка, что Pellet отвечает (НФТ-3 таймаут) |

### 7.4. Новые эндпоинты — контракты

Для каждого нового эндпоинта: путь, запрос (минимально необходимые поля), ответ (структура), HTTP-коды, ошибки. Примеры — не полный YAML, а суть контракта.

#### 7.4.1. `POST /policies/validate` (UC-3 dry-run)

**Запрос:** тот же `PolicyCreate` (см. §7.5).

**Ответ 200:**

```json
{
  "valid": true,
  "consistency":  { "status": "passed", "violations": [] },
  "acyclicity":   { "status": "passed", "cycle_path": [] },
  "warnings": [
    { "code": "SV4_PARTIAL_OVERLAP", "message": "Политика по семантике ≥ существующей p_red_weak — потенциальная избыточность (СВ-4)" }
  ]
}
```

**Ответ 422** (валидация не прошла, но политика не сохранена):

```json
{
  "valid": false,
  "consistency": { "status": "failed", "violations": [{ "kind": "disjointness", "detail": "..." }] },
  "acyclicity":  { "status": "failed", "cycle_path": ["module_A.complete", "module_B.access", "module_A.access"] },
  "warnings": []
}
```

**Семантика.** Эндпоинт ничего не сохраняет в ABox — проверка ведётся на временной копии. После получения `valid: true` клиент должен сделать `POST /policies`. При `valid: false` и попытке `POST /policies` сервер также вернёт 422 — но уже с откатом изменений (НФТ-5 rollback).

#### 7.4.2. `GET /access/student/{sid}/element/{eid}/explain` (UC-9)

**Ответ 200:**

```json
{
  "element_id": "module_3_oop",
  "student_id": "student_ivanov",
  "is_available": false,
  "cascade_blocker": null,
  "applicable_policies": [
    {
      "policy_id": "p4_module3_requires_comp_functions",
      "rule_type": "competency_required",
      "satisfied": false,
      "failure_reason": "Студент не обладает компетенцией comp_functions",
      "witness": { "required_competency": "comp_functions", "student_competencies": ["comp_basic_syntax"] }
    }
  ]
}
```

**Каскадная блокировка:**

```json
{
  "element_id": "quiz_3",
  "student_id": "student_ivanov",
  "is_available": false,
  "cascade_blocker": "module_3_oop",
  "cascade_reason": "Родительский модуль недоступен по policy p4_module3_requires_comp_functions",
  "applicable_policies": [
    {
      "policy_id": "p7_quiz3_or",
      "rule_type": "or_combination",
      "satisfied": true,
      "note": "Политика выполняется, но каскад блокирует доступ"
    }
  ]
}
```

**Источник данных.** Сервис берёт результат последнего reasoning-прогона из Redis (`access:{student_id}`) и дополняет trace-информацией из ABox: для каждой политики на `eid` (и его предках) вычисляет `satisfies` + причину неудачи из локальной интерпретации типа правила (не DL justification — это FIX9, отдельная задача с другим уровнем точности).

#### 7.4.3. `GET /verify/course/{id}` (UC-6 базовая)

**Ответ 200 (happy):**

```json
{
  "course_id": "course_python_basics",
  "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "timestamp": "2026-04-21T14:32:10Z",
  "duration_ms": 2340,
  "properties": {
    "consistency":  { "status": "passed" },
    "acyclicity":   { "status": "passed" },
    "reachability": { "status": "passed" }
  },
  "summary": "3 из 3 базовых свойств выполнены"
}
```

**Ответ 200 (violations):**

```json
{
  "course_id": "course_broken",
  "run_id": "01ARZ3NDEK...",
  "timestamp": "2026-04-21T14:32:10Z",
  "duration_ms": 1820,
  "properties": {
    "consistency": {
      "status": "failed",
      "violations": [
        { "code": "SV1_DISJOINTNESS", "individuals": ["user_mixed_role"], "classes": ["Student", "Methodologist"] }
      ]
    },
    "acyclicity": {
      "status": "failed",
      "cycles": [
        { "path": ["module_A", "module_B", "module_A"], "policies": ["p_cycle_ab", "p_cycle_ba"] }
      ]
    },
    "reachability": {
      "status": "failed",
      "unreachable_elements": [
        { "element_id": "quiz_Z", "reason": "SV3_THRESHOLD_OUT_OF_RANGE", "policy_id": "p_unreach", "detail": "threshold=150.0 вне [0, 100]" }
      ]
    }
  },
  "summary": "0 из 3 базовых свойств выполнены, 3 нарушения"
}
```

**HTTP-коды:** 200 (отчёт сформирован, независимо от violations); 504 (reasoning timeout НФТ-3 — вернётся частичный отчёт с полем `partial: true`); 404 (курс не найден).

#### 7.4.4. `POST /verify/course/{id}/full` (UC-6 + А6)

**Запрос:** пусто (всё берётся из ABox).

**Ответ 202 Accepted:**

```json
{
  "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "status": "running",
  "poll_url": "/api/v1/verify/reports/01ARZ3NDEKTSV4RRFFQ69G5FAV"
}
```

**`GET /verify/reports/{run_id}`** возвращает либо `status: running` (202 тот же), либо финальный отчёт с дополнительными полями `redundancy` и `subsumption`:

```json
{
  "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "status": "done",
  "duration_ms": 8420,
  "properties": {
    "consistency":  { ... },
    "acyclicity":   { ... },
    "reachability": { ... },
    "redundancy": {
      "status": "failed",
      "redundant_pairs": [
        { "policy_a": "p_red_strong", "policy_b": "p_red_weak", "direction": "a_subsumed_by_b", "witness": "grade≥80 ⇒ grade≥60" }
      ]
    },
    "subsumption": {
      "status": "failed",
      "subsumed_pairs": [
        { "policy_a": "p_subj_group", "policy_b": "p_subj_all", "direction": "a_subsumed_by_b", "kind": "subject", "witness": "все advanced ⊂ все студенты" }
      ]
    }
  }
}
```

Сохранение отчёта в Redis — через ключ `verify:{course_id}:{run_id}` (см. §А5.2 SAT_ALGORITHMS + C9 в §А5.8).

#### 7.4.5. `POST /integration/courses/{id}/import/verify` (UC-10 + UC-6)

**Запрос:** тот же `CourseSyncPayload`.

**Ответ 200 (импорт + верификация прошли):**

```json
{
  "course_id": "course_imported",
  "imported": { "elements": 24, "policies": 8 },
  "verification": { /* полный VerificationReport как в 7.4.3 */ }
}
```

Если верификация нашла нарушения — импорт **не откатывается**, но отчёт возвращает `status: failed` для найденных свойств. Это соответствует решению 18.04 (автоверификация после импорта).

### 7.5. Расширение схемы `PolicyCreate` под 9 типов

Текущая схема (openapi.yaml строки 294–322) покрывает только 4 типа: `grade_required, completion_required, competency_required, date_restricted`. Нужно расширить enum и добавить поля для композитов, групп, агрегатов.

**Целевая схема:**

```yaml
PolicyCreate:
  type: object
  required: [source_element_id, rule_type, author_id]
  properties:
    source_element_id: { type: string }  # элемент, на который навешивается политика
    rule_type:
      type: string
      enum: [completion_required, grade_required, viewed_required, competency_required,
             date_restricted, and_combination, or_combination, group_restricted, aggregate_required]
    author_id: { type: string }

    # Атомарные (1, 2, 3):
    target_element_id: { type: string, nullable: true }
    passing_threshold: { type: number, nullable: true, minimum: 0, maximum: 100 }

    # Компетенция (4):
    target_competency_id: { type: string, nullable: true }

    # Дата (5):
    valid_from:  { type: string, format: date-time, nullable: true }
    valid_until: { type: string, format: date-time, nullable: true }

    # Композиты (6, 7) — NEW:
    subpolicy_ids: { type: array, items: { type: string }, nullable: true, minItems: 2 }

    # Группа (8) — NEW:
    restricted_to_group_id: { type: string, nullable: true }

    # Агрегат (9) — NEW:
    aggregate_function:
      type: string
      enum: [AVG, SUM, COUNT]
      nullable: true
    aggregate_element_ids:
      type: array
      items: { type: string }
      nullable: true
      minItems: 1
```

**Валидация по типу (серверная):**

| Тип | Обязательные поля | Запрещённые |
|---|---|---|
| `completion_required` | `target_element_id` | остальные специфичные |
| `grade_required` | `target_element_id`, `passing_threshold` | остальные |
| `viewed_required` | `target_element_id` | остальные |
| `competency_required` | `target_competency_id` | остальные |
| `date_restricted` | `valid_from`, `valid_until` (valid_from < valid_until) | остальные |
| `and_combination` | `subpolicy_ids` (≥2, различные) | остальные |
| `or_combination` | `subpolicy_ids` (≥2, различные) | остальные |
| `group_restricted` | `restricted_to_group_id` | остальные |
| `aggregate_required` | `aggregate_function`, `aggregate_element_ids`, `passing_threshold` | остальные |

Серверная валидация реализуется через дискриминированный `oneOf` в OpenAPI 3.0 или Pydantic `Field(..., discriminator='rule_type')` — конкретика в фазе 2.

### 7.6. Новые схемы

| Схема | Назначение | Секция |
|---|---|---|
| `PolicyValidationReport` | ответ `POST /policies/validate` | §7.4.1 |
| `BlockingExplanation` | ответ `/access/.../explain` | §7.4.2 |
| `VerificationReport` | ответ `/verify/course/...` | §7.4.3, §7.4.4 |
| `CyclePath` | вложенная в `acyclicity.cycles[]` | §7.4.3 |
| `ConsistencyViolation` | вложенная в `consistency.violations[]` | §7.4.3 |
| `UnreachableElementReport` | вложенная в `reachability.unreachable_elements[]` | §7.4.3 |
| `SubsumptionPair` | вложенная в `redundancy` / `subsumption` | §7.4.4 |
| `Group` | список групп (новая сущность TBox §1.2) | для UI редактора и симулятора |
| `AggregatePolicyDetails` | расширение `Policy` для типа 9 (function, elements[]) | чтение политик |

### 7.7. Контракт ошибок (НФТ-5, FIX1)

Текущий `ErrorResponse` — `{error: str, details: str}`. Для структурированной диагностики (UC-3, FIX9):

```yaml
ErrorResponse:
  type: object
  required: [error_code, message]
  properties:
    error_code:
      type: string
      enum: [
        VALIDATION_FAILED,          # 422 — pre-save валидация
        INCONSISTENT_ONTOLOGY,      # 422 — Pellet не смог построить модель (НФТ-5 rollback выполнен)
        CYCLE_DETECTED,             # 422 — А1 нашёл цикл
        REASONING_TIMEOUT,          # 504 — НФТ-3 10 с превышен
        POLICY_NOT_FOUND,           # 404
        COURSE_NOT_FOUND,           # 404
        INTERNAL_ERROR              # 500
      ]
    message: { type: string }       # человекочитаемое описание
    details:                        # структура зависит от error_code
      type: object
      nullable: true
    rollback_applied:               # для INCONSISTENT_ONTOLOGY, CYCLE_DETECTED
      type: boolean
      nullable: true
```

**Маппинг HTTP-кодов:**

| Код | Когда | error_code |
|---|---|---|
| 200 | Успех | — |
| 201 | Создано (POST /policies) | — |
| 202 | Принято async (UC-5, UC-6 full) | — |
| 400 | Неверный формат запроса (parse error) | — |
| 404 | Ресурс не найден | `*_NOT_FOUND` |
| 422 | Семантическая ошибка (бизнес-логика, валидация онтологии) | `VALIDATION_FAILED`, `INCONSISTENT_ONTOLOGY`, `CYCLE_DETECTED` |
| 500 | Внутренняя ошибка | `INTERNAL_ERROR` |
| 503 | Кэш недоступен (Redis down) | `INTERNAL_ERROR` с `details.subsystem = "cache"` |
| 504 | Таймаут reasoning | `REASONING_TIMEOUT` |

### 7.8. Версионирование и миграция

Текущая версия `2.1.0`. Целевая: **`2.2.0`** — backward-compatible:
- Все существующие эндпоинты сохранены.
- Новые эндпоинты добавлены.
- `PolicyCreate` расширена новыми полями (все `nullable`), старые клиенты с 4 типами продолжают работать.
- `ErrorResponse` расширен, старое поле `error/details` остаётся (дублируется из `error_code/message`) для одной мажорной версии.

**Breaking changes** (запланировано на `3.0.0`, вне scope ВКР):
- `is_required` → `is_mandatory` в `CourseElement` (T10).
- `EducationalElement` → `LearningActivity` в типе элементов.
- Перенос `/events/progress` → `/progress/events` (B4).
- Перенос `/access/...` → выделенный `/access` роутер (B3).

На период фазы 2 поддерживается compatibility-layer: старые пути возвращают 308 Permanent Redirect на новые.

### 7.9. Диф с `openapi.yaml` (вход в 3.6, блок OPAPI)

| # | Правка | Приоритет | Связь | Статус (24.04) |
|---|---|---|---|---|
| OPAPI1 | Обновить enum `rule_type` в `PolicyCreate` и `Policy` — добавить 5 типов | 🔴 | FIX6, FIX7, FIX8, FIX11, FIX12 | ✅ Блок 3 |
| OPAPI2 | Добавить поля `subpolicy_ids`, `restricted_to_group_id`, `aggregate_function`, `aggregate_element_ids` в `PolicyCreate` | 🔴 | FIX6–FIX8, FIX11, FIX12 | ✅ Блок 3 |
| OPAPI3 | Добавить схему `VerificationReport` + подсхемы (9 новых схем) | 🔴 | UC-6, B1, B2 | ✅ 24.04-поздно: `VerificationReportResponse` + `PropertyReportResponse` в `schemas.py`, `response_model=` в `/verify/course/{id}`, integration-тест валидирует |
| OPAPI4 | Добавить схему `BlockingExplanation` | 🟡 | UC-9, FIX9, B3 | ✅ 24.04-поздно: `BlockingExplanationResponse` + `JustificationNodeResponse` (рекурсивная) + `BlockedPolicyResponse`, `response_model=` в `/access/.../explain`, unit-тест валидирует |
| OPAPI5 | Добавить схему `PolicyValidationReport` | 🟡 | UC-3, B1 | ❌ не реализовано: validation идёт через исключения `ValueError` + HTTP 409/422 без структурированного отчёта (см. B6 §3.6.3 PROJECT_BIBLE) |
| OPAPI6 | Добавить эндпоинты `/verify/*` | 🔴 | UC-6 | ✅ Блок 2: `GET /api/v1/verify/course/{id}?full=true` |
| OPAPI7 | Добавить эндпоинты `/access/.../explain` | 🟡 | UC-9 | ✅ Блок 2/3: `GET /api/v1/access/student/{sid}/element/{eid}/explain` через AccessService + FIX9 justification tree |
| OPAPI8 | Добавить эндпоинт `POST /policies/validate` | 🟡 | UC-3 | ❌ не реализовано: dry-run отсутствует, pre-creation проверки встроены в `POST /policies` (связано с OPAPI5) |
| OPAPI9 | Переструктурировать роутеры: выделить `/access`, `/progress` из `/integration` | 🟡 | B3, B4 | ✅ Блок 2 (access) + 23.04 (progress) |
| OPAPI10 | Расширить `ErrorResponse` на `error_code` | 🟡 | НФТ-5, FIX1, FIX9 | 🟡 частично: 409 возвращается с `detail` как строка, enum `error_code` не введён |
| OPAPI11 | Добавить `/health`, `/health/reasoner` | 🟢 | FIX10 | 🟡 частично: `GET /` есть, `/health/reasoner` отсутствует |
| OPAPI12 | Дополнить `OntologyMeta` полем `verifiable_properties` (СВ-1…СВ-5) | 🟢 | UC-6 UI | ❌ не реализовано: список СВ хардкодится на фронте |
| OPAPI13 | Добавить `GET /courses` и `GET /courses/{id}` | 🟢 | фронт сейчас хардкодит | ❌ не реализовано: фронт по-прежнему хардкодит `course_python_basics` |

**Итого по блокирующим:** OPAPI1, OPAPI2, OPAPI3, OPAPI6 закрыты полностью (24.04-поздно — TD11 закрыт). OPAPI4 и OPAPI7 закрыты заодно. Остальные 🟡/🟢 — хвосты в перспективу:

- OPAPI5/OPAPI8 (dry-run validation) — реализация dry-run потребует отдельного entry-point в `PolicyService` с изолированным World-снимком. Не критично для защиты.
- OPAPI10 (error_code enum) — оформление. Для демо достаточно `detail` + HTTP-код.
- OPAPI11 (`/health/reasoner`) — добавляется строкой в `main.py`, ориентировочно в фазу 4.
- OPAPI12/OPAPI13 — UX-улучшения, закрываются при расширении scope (мультикурс).

TD11 в PROJECT_BIBLE §4.3 закрыт. Оставшиеся хвосты OPAPI5/OPAPI8/OPAPI10/OPAPI11/OPAPI12/OPAPI13 — не блокер защиты.

---

## 8. Redis — схема кэша

### 8.1. Назначение

Материализованный слой результата reasoning для НФТ-1 (≤ 50 мс на запрос UC-4). Redis держит: (1) карту доступов per student, (2) маркер версии онтологии, (3) распределённую блокировку на reasoning, (4) кэш отчётов верификации. Алгоритм инвалидации формализован в [SAT_ALGORITHMS §А5](SAT_ALGORITHMS.md); здесь — сводная таблица ключей, payload-контракты и TTL-политика как вход для seed-тестов Redis и fixture'ов в фазе 2.

Связь с архитектурой C4: компонент `CacheManager` в Core Layer ([workspace.dsl](../diagrams/c4/workspace.dsl)); владелец схемы — `CacheManager`, единственные читатели — `AccessService` (UC-4) и `VerificationService` (UC-6).

### 8.2. Таксономия ключей

| Namespace | Тип Redis | Назначение | Владелец | TTL |
|---|---|---|---|---|
| `access:{student_id}` | STRING (JSON) | Карта доступных элементов одного студента | CacheManager.set_student_access | адаптивный, §8.4 |
| `onto:version` | STRING | SHA-256 файла `edu_ontology_with_rules.owl` | ReasoningOrchestrator.on_ontology_save | ∞ (перезаписывается) |
| `verify:{course_id}:{run_id}` | STRING (JSON) | Отчёт `VerificationReport` | VerificationService.save_report | 1 час |
| `verify:latest:{course_id}` | STRING (ULID) | Указатель на последний `run_id` | VerificationService.save_report | 1 час |
| `lock:reasoning:global` | STRING (SET NX EX) | Глобальный mutex на массовый rebuild | ReasoningOrchestrator | 30 с |
| `lock:reasoning:student:{s}` | STRING (SET NX EX) | Per-student mutex при параллельном miss | CacheManager.rebuild_for | 30 с |
| `recent:students` | SET | ID студентов с активностью за 15 мин (для preemptive rebuild) | AccessService.on_hit | ∞, ротация через ZADD+ZREMRANGEBYSCORE |

Namespace-разделитель `:` — конвенция Redis; делит пространство ключей для разных сущностей. Префиксы выбраны короткими, но не абревиатурными, чтобы `redis-cli --scan --pattern "access:*"` читался в продакшен-дебаге.

Всё, что не в этой таблице, в Redis **не пишется**. В частности: структура курса, список политик, прогресс — живут в OWL-онтологии (источник истины), Redis не дублирует. Причина: инвалидация при изменении TBox/ABox стала бы распределённой задачей двух хранилищ; ограничение Redis только результатом А2 делает контракт однонаправленным — ABox пишет, Redis материализует.

### 8.3. Контракты payload

#### 8.3.1. `access:{student_id}`

```json
{
  "student_id": "student_ivanov",
  "updated_at": "2026-04-21T14:32:10.123Z",
  "ontology_version": "a7f3c2e1b8d9...",
  "duration_ms": 1840,
  "elements": {
    "lecture_0_welcome":   { "available": true,  "blocked_by": null },
    "lecture_2_operators": { "available": true,  "blocked_by": null },
    "module_3_oop":        { "available": false, "blocked_by": "p4_module3_requires_comp_functions" },
    "quiz_3":              { "available": false, "blocked_by": "module_3_oop", "cascade": true },
    "extra_material":      { "available": false, "blocked_by": "p8_extra_material_advanced" }
  }
}
```

**Поля.**
- `updated_at` — ISO-8601 UTC, момент завершения А2 для этого студента. Нужен для stale-cache fallback при таймауте (§А2.8).
- `ontology_version` — хэш `edu_ontology_with_rules.owl` на момент материализации. Проверяется при чтении; расхождение с `onto:version` → инвалидация + miss (С4 в §А5.8).
- `duration_ms` — время А2 в мс, для самоотчёта (EXP4, мониторинг НФТ-1).
- `elements[*].blocked_by` — id первого отказавшего элемента в цепочке (атомарная политика или родитель при каскаде). `null` для доступных и для свободных (без политики). Это минимальный trace для UC-9, без полного DL-justification — тот возвращается отдельным вызовом (OPAPI7 `/explain`).
- `elements[*].cascade` — true, если `blocked_by` указывает на родительский элемент (иерархическая блокировка), а не на политику.

**Размер.** При 500 элементах и среднем 80 байт на запись: ≈ 40 КБ сырого JSON, ≈ 15 КБ после сжатия (gzip HTTP). Укладывается в рекомендацию Redis `< 100 KB` на STRING.

**Почему не hash-структура `HSET access:{s} elem:1 {...}`.** Hash даёт частичное чтение/запись, но мы всегда читаем всё (фронт рисует дерево курса целиком). Парсинг одного JSON на клиенте — 1 мс; 500 вызовов `HGET` — сетевой overhead. STRING проще и быстрее для нашего паттерна.

#### 8.3.2. `onto:version`

```
"a7f3c2e1b8d9f6e5d4c3b2a19087654321fedcba..."
```

Голая строка — SHA-256 (hex, 64 символа) файла онтологии. Перезаписывается каждый раз, когда `ReasoningOrchestrator.save_ontology` фиксирует изменения в `.owl`. Не имеет TTL — всегда актуальна текущая версия.

#### 8.3.3. `verify:{course_id}:{run_id}`

```json
{
  "course_id": "course_python_basics",
  "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "timestamp": "2026-04-21T14:32:10Z",
  "duration_ms": 8420,
  "ontology_version": "a7f3c2e1b8d9...",
  "properties": {
    "consistency":  { "status": "passed" },
    "acyclicity":   { "status": "passed" },
    "reachability": { "status": "failed", "unreachable_elements": [ /* ... */ ] },
    "redundancy":   { "status": "passed" },
    "subsumption":  { "status": "failed", "subsumed_pairs": [ /* ... */ ] }
  }
}
```

Совпадает со схемой `VerificationReport` из §7.4.3–7.4.4. TTL 1 час покрывает сценарий «методист смотрит отчёт несколько раз за сессию». При изменении политик курса — инвалидация любого `verify:{course_id}:*` (через SCAN). Указатель `verify:latest:{course_id}` хранит только `run_id`; клиент делает два запроса (GET указателя → GET отчёта) или сервер разворачивает это в один endpoint (OPAPI6).

#### 8.3.4. Блокировки

Паттерн Redis distributed lock:

```
SET lock:reasoning:student:{s} "{worker_id}" NX EX 30
  → OK     — захвачено
  → nil    — уже заблокировано, ждём retry / отдаём stale-cache
DEL lock:reasoning:student:{s}     — явное снятие в finally
```

TTL 30 с — выше pessimistic-оценки А2 (до 10 с по НФТ-3 + запас × 3). Значение — UUID воркера, нужен для диагностики (видно в `MONITOR` — кто держит).

`lock:reasoning:global` — только для операций E1–E4, E10 (массовая инвалидация). Поднимает serializability: два `PolicyService.create_policy` не могут параллельно триггерить `invalidate_all_access`.

#### 8.3.5. `recent:students`

Redis SORTED SET: `ZADD recent:students <unix_ts> <student_id>`. Периодический `ZREMRANGEBYSCORE recent:students -inf (now - 900)` чистит старше 15 минут. Используется `CacheManager.rebuild_for_active` при событиях E1–E4: preemptive rebuild только для активных, а не всех 1000+ студентов.

Опциональный путь оптимизации — включается в фазе 2 через feature flag; без него работает lazy rebuild (§А5.4).

### 8.4. TTL-политика

**Реализация (24.04, вариант В).** Фиксированный TTL=3600 с на `access:{s}` + ограничение `PolicyCreate.valid_from/valid_until` на часовую гранулярность. Подробное обоснование выбора — §А5.5 SAT_ALGORITHMS.

| Ключ | TTL (реализован) | Комментарий |
|---|---|---|
| `access:{s}` | 3600 с | Фиксированный час. Датные границы `date_restricted` кратны часу (валидация в PolicyCreate), TTL гарантирует cache miss не позже следующей границы |
| `onto:version` | — | Не реализован (см. §8.8, пункт C2) |
| `verify:{course_id}:{run_id}` | 3600 с | Не реализован (см. §8.8, пункт C9), отчёт пересчитывается на каждый запрос |
| `lock:reasoning:student:{s}` | — | Не реализован (см. §8.8, пункт C7); single-worker FastAPI исключает race |
| `recent:students` | — | Не реализован (см. §8.8, пункт C8) |

Вариант А (адаптивный TTL) оставлен в §А5.5 как «альтернатива, не выбрана». Корректность обеспечивается событийной инвалидацией (E1–E10) в коде `PolicyService`/`ProgressService` + фиксированным часовым TTL. Проверка `ontology_version` при чтении — TD10 Bible §4.3.

### 8.5. Матрица «событие → действие» (сводка)

Полная формализация — §А5.3 SAT_ALGORITHMS. Сводка для оперативного понимания:

| Источник события | Инвалидация | Preemptive rebuild |
|---|---|---|
| E1–E4: создание/обновление/удаление/toggle политики | `SCAN access:*` + DEL; DEL всех `verify:{course_id}:*` | Активные студенты (≤ 15 мин) — сейчас; остальные — lazy |
| E5–E6: прогресс одного студента + rollup | DEL `access:{s}` | Не нужен — студент сам запросит доступ следующим запросом |
| E7: competency acquired | DEL `access:{s}` | То же, что E5 |
| E8: membership в группе | DEL `access:{s}` | То же |
| E9: симулятор | DEL `access:{sim_s}` | Сейчас же — UI симулятора ожидает свежего ответа |
| E10: import course | `SCAN access:*` + DEL, DEL `verify:*` | Активные — сейчас; включает автозапуск UC-6 (OPAPI-import/verify) |
| E11: датная граница | Ничего (TTL уже истёк или истечёт) | Lazy при следующем UC-4 |
| E12: перезапуск сервиса | `FLUSHDB access:*` если `onto:version` не совпадает со сохранённым | Нет — все lazy |

### 8.6. Sizing-бюджет

Ориентир на сценарий ВКР и EXP4:

| Параметр | Значение | Источник |
|---|---|---|
| Активных студентов (норма) | 500 | НФТ-4 |
| Размер `access:{s}` (мажоранта) | 40 КБ | §8.3.1 |
| Общий объём `access:*` | ~20 МБ | 500 × 40 КБ |
| Размер `verify:{course_id}:{run_id}` (мажоранта) | 100 КБ | отчёт с 20 violations + 50 subsumed pairs |
| Отчётов в кэше | ~20 (1 курс × 20 запусков за час) | §8.2 TTL |
| Общий объём кэша | ~22 МБ | + служебные ключи |
| Redis инстанс | 256 МБ (`maxmemory`) | 10× запас |

При росте до НФТ-10 (5000 студентов) объём `access:*` → ~200 МБ, Redis `maxmemory` поднимается до 1 ГБ. Это параметр развёртывания, не проектное решение.

### 8.7. Контракт надёжности

**Инвариант 1 — default-deny при сбое Redis.** Если Redis недоступен:
- `GET access:{s}` → cache miss → прямая материализация (медленнее, но корректно, §А5.6 инвариант 2).
- `DEL access:*` → no-op с warning в логах.
- `SET lock:reasoning:*` → no-op; в single-worker (фаза 1) не критично, в multi-worker (фаза 2 после FIX10) может привести к double-reasoning; на корректность выводов не влияет (А2 идемпотентен), только на производительность.

Следствие: Redis в архитектуре — **оптимизация, не источник истины**. Отключение Redis не меняет поведение системы, только латентность. Это прямой ответ на НФТ-6 (восстановление после сбоя).

**Инвариант 2 — never-serve-stale.** Даже при hit'е проверяется `ontology_version`. Устаревший кэш не выдаётся клиенту (вместо этого — прозрачный miss с rebuild). Это отличает нашу схему от TTL-only подхода, где между событием инвалидации и истечением TTL пользователь может получить устаревшее.

**Инвариант 3 — отсутствие «dangling lock».** Все блокировки берутся с EX 30 с. Если воркер падает внутри критической секции — lock истечёт автоматически; в худшем случае следующий воркер стартует reasoning через ≤ 30 с.

### 8.8. Диф с текущим кодом

**Статус (24.04-поздно).** Компонент переименован в [services/cache_manager.py](../code/backend/src/services/cache_manager.py) (решение 23.04, закрывает C6). Покрывает: `access:{s}` + `SET`/`GET`/`DEL` + фиксированный TTL=3600 с (решение 24.04, C3 заменён). Второй заход 24.04 поздно закрыл ontology_version-консистентность и SCAN-инвалидацию (TD10).

| Ключ схемы | Что реализовано | Что не реализовано | Соответствие §А5.8 |
|---|---|---|---|
| `access:{s}` | SET/GET/DEL + `ex=3600` + `ontology_version` в payload + проверка версии при GET (stale → miss + DEL) | `updated_at`, `duration_ms` в payload | C1 частично, C4 ✅ |
| `onto:version` | Устанавливается на startup через `CacheManager.publish_ontology_version()` (sha256 `.owl`, кэшируется по mtime) | — | C2 ✅ |
| `verify:{course_id}:*` | SET/GET/DEL + TTL + `ontology_version` в payload | `run_id`-история (latest-ссылка достаточна) | C9 открыт — при росте курсов до 100+ включать |
| `lock:reasoning:student:{s}` | — | Single-worker FastAPI гонок не даёт | C7 открыт — при Docker multi-worker |
| `recent:students` | — | Lazy rebuild работает приемлемо | C8 открыт — оптимизация при |students|>100 |

Технические пункты: C5 (`SCAN` вместо `KEYS`) закрыт через `_scan_and_delete` с батчами по 500. C10 (startup-hook) закрыт через FastAPI `@on_event("startup")` → `ensure_version_consistency()`: при рассинхроне `onto:version` делает `SCAN`-инвалидацию `access:*` + `verify:*` и публикует новый хэш.

Блокирующих 🔴 нет. Оставшиеся C7/C8/C9 — TD12 в PROJECT_BIBLE §4.3, актуально при multi-worker Docker или |students|>1000.

---

## 9. Маппинг совместимости с СДО (три слоя)

### 9.1. Назначение и метод

Доказательство платформо-независимости (решение 18.04 PROJECT_BIBLE §7) требует не декларации «универсальная модель», а конкретной сверки со всеми пятью проанализированными СДО: **Moodle, Canvas, Blackboard, Open edX, Stepik**. Маппинг — таблица соответствий, не программная интеграция: реализуется только адаптер под Moodle (приоритетная платформа Дистех); для остальных — показано, что адаптер технически возможен.

Метод — трёхслойный: сверяем отдельно **структуру контента**, **типы правил** и **сущности данных**. Без такого разделения одна таблица не показала бы, что совместимость требует **трёх** независимых соответствий; несовпадение хотя бы на одном слое сломает интеграцию.

| Слой | Что сверяется | Источник данных | Расположение в документах |
|---|---|---|---|
| 1. Структура контента | Иерархия Course → Module → Activity | L1 фаза 0 | PROJECT_BIBLE §3.5.3 (исходная таблица) + §9.2 (уточнения) |
| 2. Типы правил доступа | 9 типов → механизмы платформы | L1 фаза 0 | PROJECT_BIBLE §3.5.3 + §9.3 (формат хранения и извлечения) |
| 3. Сущности данных | Классы и свойства TBox → таблицы/ресурсы СДО | L1 + документация платформ | **§9.4 (новое)** |

Источники по платформам:
- Moodle: [moodle/docs/dev/Access API](https://docs.moodle.org/dev/Access_API), схема БД `mdl_*` из Moodle 4.x.
- Canvas: [Canvas LMS REST API](https://canvas.instructure.com/doc/api/), официальная документация Instructure.
- Blackboard: [Blackboard Learn REST API docs](https://developer.blackboard.com/portal/displayApi), Adaptive Release справочник.
- Open edX: [Open edX Django models](https://github.com/openedx/edx-platform), документация пререкизитов.
- Stepik: [Stepik API reference](https://stepik.org/api/docs/), публичная справка по структурам курса.

### 9.2. Слой 1: Структура контента (уточнение)

Исходная таблица — в PROJECT_BIBLE §3.5.3. Ниже — уточнения по *уровням иерархии*, на которые можно навешивать правила (важно для UC-1 и маппинга `source_element_id`).

| Наш концепт | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| `Course` | `course` (таблица `mdl_course`) | Course | Course | `CourseOverview` | Course |
| `Module` (контейнер) | Section (`mdl_course_sections`) | Module | Content Area / Folder | Section → Subsection | Module (Section) |
| `LearningActivity` (атомарный) | Activity (`mdl_course_modules`): Assignment, Quiz, Page, Lesson, File, URL | Module Item | Content Item: Assignment, Test, Document | Unit → Component (Video/HTML/Problem) | Lesson → Step (Video/Text/Quiz) |
| На какой уровень можно навесить правило | Section и Activity | **только Module** | Content Item (любой уровень) | только Subsection | только Module (в платных тарифах) |

**Следствие:** наша модель разрешает правило на любом уровне (решение 16.04). При адаптации на Canvas/Stepik правила для `LearningActivity` нужно либо поднимать до уровня Module (теряется гранулярность), либо адаптер должен эмулировать проверку на клиенте (вне контекста платформы). Для Moodle/Blackboard/Open edX — прямое соответствие.

### 9.3. Слой 2: Типы правил доступа (формат хранения)

Исходная таблица покрытия — PROJECT_BIBLE §3.5.3. Здесь — ответ на вопрос «как адаптер извлекает правило из платформы и приводит к нашему виду».

| Платформа | Формат хранения правил | Извлечение через API | Тонкости нормализации |
|---|---|---|---|
| Moodle | JSON в поле `course_modules.availability` — дерево `{"op":"&","c":[{"type":"completion","cm":12,"e":1}, ...]}` | `core_availability_get_...` или прямой SQL | Плоское дерево с произвольной вложенностью AND/OR/NOT; NOT конвертируется в наш паттерн CWA или исключается (FIX6/FIX7). NOT в Moodle — редкий случай, в L1 не зафиксирован обязательным |
| Canvas | Поле `prerequisite_module_ids` в Module (массив UUID предшествующих модулей) | `GET /api/v1/courses/:id/modules` с `include[]=items` | Только completion-prerequisite; grade-пороги задаются через Mastery Paths (отдельный механизм). Маппинг: каждый UUID → отдельная `completion_required`-политика |
| Blackboard | XML в proprietary-формате Adaptive Release (через REST возвращается структурированный JSON) | `GET /learn/api/public/v1/courses/:id/contents/:cid/availability` | ДНФ-структура: массив `{rules: [{conditions: [...]}]}` — каждая `rule` = OR, внутри `conditions` = AND. Трёхуровневая: rules ↔ `or_combination`, conditions ↔ `and_combination` |
| Open edX | Django-модель `PrerequisiteCourseCompletion` + `SubsectionGrade.passing_grade` | `GET /api/courses/v1/courses/:id/` + `GET /api/grades/v1/subsection/:block_id/` | Один пререквизит на подсекцию, без булевой композиции. Маппинг в наш `completion_required` / `grade_required` прямой, композиты не возникают |
| Stepik | Поле `max_score` и `is_locked_by_ability` в `Section` | `GET /api/sections/:id/` | Только порог баллов на модуле (платный тариф). Маппинг в `grade_required` с target на «сумму баллов по модулю» — требует дополнительной логики адаптера через `aggregate_required` |

**Следствие для IntegrationService (UC-10).** Адаптер под каждую платформу — отдельный слой трансляции, читающий её формат и генерирующий стандартную ABox (наши `AccessPolicy` + свойства). Корректность доказывается по таблице соответствий выше. Референсный адаптер под Moodle — фаза 2; для остальных платформ — таблица как проектное обоснование, без реализации.

### 9.4. Слой 3: Сущности данных (новое)

Таблица: TBox-классы и ключевые свойства → таблицы/модели/ресурсы СДО. Колонка «Нормализация» — что делает `IntegrationService` при чтении. Колонка «Запись» — куда система пишет обратно (как правило, пусто: мы не вмешиваемся в источник истины СДО, только читаем).

#### 9.4.1. Пользователи и роли

| TBox | Что моделирует | Moodle | Canvas | Blackboard | Open edX | Stepik | Нормализация |
|---|---|---|---|---|---|---|---|
| `User` | Пользователь платформы | `mdl_user` | `User` | `User` | `auth_user` + `UserProfile` | `User` | `id` — внешний ключ платформы; `name` — `firstname + lastname` или `display_name` |
| `Student` | Роль «обучающийся» | `role_assignments` с `roleid=student` | Enrollment.type = 'StudentEnrollment' | Course membership role = STUDENT | `CourseEnrollment.mode` | роль неявная (все User = Student) | Student — подкласс User, роль определяется по enrollment в конкретном курсе |
| `Teacher` | Роль «преподаватель» | `role_assignments` с `roleid=editingteacher`/`teacher` | Enrollment.type = 'TeacherEnrollment' | role = INSTRUCTOR | `CourseAccessRole.role='instructor'` | staff / owner | Teacher — подкласс User |
| `Methodologist` | Автор правил доступа | отдельной роли нет; проксируется через teacher/manager | role = 'DesignerEnrollment' (если используется) | role = COURSE_BUILDER | role = 'staff' (разработчик курса) | staff | В референсной имплементации проксируется ролью Teacher с capability `edu:policies:write` |

**Примечание.** Все 5 СДО различают student/teacher, но **только методист как явную роль автора правил — никто**. Наш класс `Methodologist` — семантическая роль, не security-principal: в интеграции он проксируется teacher+capability. Это соответствует решению 15.04 «RBAC вне scope».

#### 9.4.2. Структура курса (связи)

| TBox свойство | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| `has_module(Course, Module)` | `course_sections.course` FK | Module.course_id | Course → contents tree | CourseOverview → Section | Course.sections |
| `contains_activity(Module, LearningActivity)` | `course_modules.section` FK | ModuleItem.module_id | Content Item parent_id | Subsection → Component/Block | Section.lessons |
| `is_mandatory(element, bool)` | `course_modules.completion != 0` | атрибут `completion_requirement` в ModuleItem | setting per Content Item | `visible_to_staff_only=false` + graded flag | all items mandatory by default |
| `order_index(element, int)` | `course_sections.sequence` | ModuleItem.position | parent-ordered list | display_order | Position |

#### 9.4.3. Прогресс и оценки

| TBox | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| `ProgressRecord` | `course_modules_completion` + `grade_grades` | `Submission` + `ModuleProgression` | Grade Center entry + Review Status | `BlockCompletion` + `SubsectionGrade` | `Submission` + `Step.progress` |
| `refers_to_student` | `.userid` | `.user_id` | `userPk1` | `.user_id` | `user_id` |
| `refers_to_element` | `.coursemoduleid` | `.assignment_id` / `.module_item_id` | `contentPk1` | `.block_id` / `.usage_key` | `step_id` / `lesson_id` |
| `has_grade` | `grade_grades.finalgrade` (numeric, 0–100 по умолчанию) | `Submission.grade` (может быть %, буквой, points) | Grade value + format (`GradeSchema`) | `SubsectionGrade.earned_all / possible_all` (доля) | `Submission.score` (points) |
| `has_status` | `completionstate`: 0/1/2/3 → not_attempted/complete/passed/failed | `workflow_state`: submitted/graded | Review Status: `NOT_ATTEMPTED`/`COMPLETED` | `BlockCompletion.completion` ∈ [0.0, 1.0] | `Step.is_passed` (bool) |
| `started_at` | `timecreated` | `attempted_at` | `firstAttempted` | `created` | `time_viewed` |
| `completed_at` | `timemodified` (при complete) | `graded_at` или `submitted_at` | `completedDate` | `modified` | `time_passed` |

**Нормализация оценок.** Наш `has_grade` — float в диапазоне [0, 100]. Адаптер:
- Moodle: берёт напрямую (`finalgrade` уже в шкале 0–100 по умолчанию; при нестандартной шкале — нормализует по `grade_items.grademax`).
- Canvas: если числовая — нормализует в %; если буквенная — маппит по `GradingStandard` ({"A":95, "B":85, ...}); если points — делит на possible × 100.
- Blackboard: `Score / pointsPossible × 100`.
- Open edX: `earned_all / possible_all × 100`.
- Stepik: `score / max_score × 100` (max берётся из `Step.cost`).

**Нормализация статуса.** `has_status` — enum `status_viewed / status_completed / status_failed / status_passed`. Адаптер:
- Moodle: `completionstate=0 → status_viewed` (если есть log просмотра), `=1 → status_completed`, `=2 → status_passed`, `=3 → status_failed`. Пустая запись → отсутствие `ProgressRecord` (OWA default).
- Canvas: `submitted_at NOT NULL → status_viewed`, `workflow_state='graded' + grade≥threshold → status_passed`.
- Blackboard: `REVIEWED → status_viewed`, `COMPLETED → status_completed`, grade сравнивается с passing → `status_passed`/`status_failed`.
- Open edX: `completion≥0.5 → status_viewed`, `completion=1.0 → status_completed`, SubsectionGrade ≥ passing → `status_passed`.
- Stepik: `is_passed=true → status_passed`, `time_viewed NOT NULL → status_viewed`.

#### 9.4.4. Группы и членства

| TBox | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| `Group` | `mdl_groups` | `Section` (в рамках курса) / `Group` | Course Group | `CourseCohort` (через Open edX Cohorts) | ❌ — нет концепта групп |
| `belongs_to_group(Student, Group)` | `mdl_groups_members` | `Enrollment.section_id` / `GroupMembership` | CourseGroupUser | `CohortMembership` | не применимо |

**Следствие для Stepik.** Шаблон 8 (`group_restricted`) на этой платформе неработоспособен. Адаптер под Stepik не может заполнить `belongs_to_group` — соответствующие политики в импортированном курсе игнорируются с warning. Это — ограничение целевой платформы, не нашей модели; документируется для Дистех.

#### 9.4.5. Компетенции

| TBox | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| `Competency` | `mdl_competency` (+ `mdl_competency_framework`) | `Outcome` | `Goals` | ❌ штатно нет; проксируется через `CourseTag` | ❌ |
| `has_competency(Student, Competency)` | `mdl_competency_usercomp` + `mdl_user_competency_course` (при завершении) | Outcome Result API | Goals progress | — | — |
| `assesses(Activity, Competency)` | `mdl_competency_modulecomp` | `OutcomeLink` на задание | Goals ↔ Content mapping | — | — |
| `is_subcompetency_of(Competency, Competency)` | `mdl_competency.parentid` | `OutcomeGroup` иерархия | Goals hierarchy | — | — |

**Следствие для Canvas/Blackboard/Open edX/Stepik.** Полноценная поддержка `competency_required` (шаблон 4 + вспомогательное H-1) — только в Moodle. В Canvas/Blackboard частичная: Outcomes/Goals существуют, но их присвоение студенту происходит через mastery-шкалу, а не булеву компетентность. Адаптеру нужно задать порог mastery → присвоение `has_competency`. Для Open edX и Stepik тип правила `competency_required` не работает; политики с этим типом не переживают импорт.

#### 9.4.6. Политики доступа (хранение)

| TBox | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| `AccessPolicy` | поле `course_modules.availability` (JSON, по одному на activity) | `Module.prerequisites` + `Module.completion_requirements` | Adaptive Release rules per content | `PrerequisiteCourseCompletion` + `SubsectionGrade.passing_grade` | `Section.max_score` |
| `has_access_policy(element, AccessPolicy)` | выводится из наличия `availability != NULL` | как массив предшественников | inline per content | FK на course_overview | inline |
| `is_active(AccessPolicy, bool)` | `availability != NULL AND not empty` | атрибут `require_sequential_progress` | флаг enable в rule | implicit | implicit |
| `has_author(AccessPolicy, Methodologist)` | нет поля; выводится из `course_modules.timemodified` + `role_assignments` (кто последний редактировал) | `wiki_pages_history` аналог (для модулей нет прямой attribution) | audit log (`ContentHistory`) | git history курса | нет |

**Следствие.** Авторство правил — слабая точка всех СДО. Наше поле `has_author` в интеграции заполняется best-effort (последний редактор); если информация недоступна — остаётся пустым с default-значением `methodologist_unknown`. Это приемлемо: `has_author` используется только для UI-отчёта, не для reasoning.

### 9.5. Что остаётся внутри нашей системы (не в СДО)

Три класса TBox не имеют прообраза в СДО и не подлежат импорту:

- **`CurrentTime` (singleton-индивид)** — служебный enricher-артефакт; создаётся/удаляется внутри `ReasoningOrchestrator`, не связан с данными платформы. Объявление — SAT_DATA_MODELS §1.6 инвариант 1.
- **`AggregateFact` (семейство per-student-per-policy)** — вычисляется enricher-ом из `ProgressRecord`. Прообраз в источнике — только исходные `has_grade`-значения; агрегат сам — наш артефакт. Объявление — §1.6 инвариант 2.
- **`Status`-индивиды (`status_viewed`, `status_completed`, `status_failed`, `status_passed`)** — TBox-константы; не импортируются из платформы, только используются при нормализации (§9.4.3).

Эти классы инвариантны относительно платформы — поэтому маппинг слоя 3 для них не требуется.

### 9.6. Итог совместимости

Сводная оценка: какие из 9 типов правил полностью/частично/не поддерживаются в каждой СДО после интеграции через наш адаптер.

| Тип правила | Moodle | Canvas | Blackboard | Open edX | Stepik |
|---|---|---|---|---|---|
| 1. completion_required | ✅ | ✅ | ✅ | ✅ | ⚠️ частично (только на уровне модуля) |
| 2. grade_required | ✅ | ✅ | ✅ | ✅ | ✅ |
| 3. viewed_required | ✅ | ⚠️ (через submitted) | ✅ | ⚠️ (через completion≥0.5) | ⚠️ (через time_viewed) |
| 4. competency_required | ✅ | ⚠️ (через Outcome mastery) | ⚠️ (через Goals) | ❌ | ❌ |
| 5. date_restricted | ✅ | ✅ | ✅ | ✅ | ❌ |
| 6. and_combination | ✅ | ⚠️ (только одноуровневые) | ✅ | ❌ | ❌ |
| 7. or_combination | ✅ | ⚠️ (через Mastery Paths) | ✅ | ❌ | ❌ |
| 8. group_restricted | ✅ | ✅ | ✅ | ✅ | ❌ |
| 9. aggregate_required | ✅ (gradebook categories) | ❌ | ✅ (weighted columns) | ✅ (subsection grade) | ⚠️ (через max_score) |

Легенда: ✅ полная поддержка, ⚠️ частичная (через суррогатный механизм или с потерей гранулярности), ❌ неподдерживаемо.

**Вывод по совместимости.** Наша онтология **структурно совместима со всеми 5 платформами**; практическая реализуемость адаптера различается: Moodle — полная; Blackboard и Open edX — 85–90%; Canvas — 70% (теряются композиты); Stepik — 40% (теряются композиты, группы, компетенции, даты). Это согласуется с позицией «референсная реализация под Moodle + теоретическая совместимость с остальными» (решение 18.04).

---

## 10. Интеграционный слой: режимы и обоснование выбора

> **Назначение раздела:** зафиксировать архитектурное решение о позиционировании разработанной системы относительно внешней СДО. Раздел используется как фактура для главы 2 §2.6 ПЗ. Конкретный референсный адаптер для Moodle описан в §11; маппинг онтологии на 5 СДО — в §9.

### 10.1. Терминология XACML

Опираемся на стандартную классификацию ролей по NIST SP 800-162 [P14] и спецификации XACML 3.0 [P15]:

| Роль | Расшифровка | Где в нашей архитектуре |
|---|---|---|
| **PDP** | Policy Decision Point — компонент, принимающий решения о доступе | Разработанная система целиком (ядро + REST API + резонер + кэш) |
| **PEP** | Policy Enforcement Point — компонент, применяющий решения PDP к запросу | Внешняя СДО (Moodle, Canvas и т. д.), которая рендерит UI с заблокированными элементами по решению PDP |
| **PAP** | Policy Administration Point — компонент управления политиками | Frontend разработанной системы (`PolicyRuleCard.vue`, `ImportManager`, `VerificationReport.vue`) |
| **PIP** | Policy Information Point — источник атрибутов для решения | `IntegrationService` (DSL §40), импортирующий структуру курса и события прогресса из СДО |

Стандартное разделение PDP / PEP / PAP / PIP даёт точку опоры в нормативной литературе и снимает риск размытой формулировки «наша система делает всё».

### 10.2. Режим А — twin storage с обратной трансляцией

**Что это.** Политики хранятся одновременно в нашей онтологии и в `course_modules.availability` Moodle (соответствующих структурах других СДО). При создании или изменении политики в нашей системе она транслируется в JSON-формат Moodle и записывается в Moodle через Web Services.

**Поток данных.** Methodologist пишет политику через наш UI → `PolicyService.create_policy` сохраняет в OWL → `IntegrationService.translate_to_moodle_availability` формирует JSON → Moodle Web Services записывает в `course_modules.availability` → Moodle PHP-интерпретатор применяет политику при рендере страницы.

**Ограничения.**

1. **Подрыв гипотезы работы.** В режиме А enforcement остаётся в процедурном PHP-интерпретаторе Moodle — это та самая проблема P1 из главы 1 (отсутствие формальной семантики правил доступа). Получается «умный редактор JSON availability с верификацией перед записью», что не требует онтологии для самой задачи enforcement. Положение 2 на защите (DL + графовый анализ обнаруживают пять классов дефектов) теряет смысл — дефекты найдены в нашем хранилище, но enforcement идёт по Moodle-копии, корректность которой не гарантирована (трансляция может потерять семантику).
2. **Семантические потери на типах 4 и 9.**
   - `competency_required` (тип 4): Moodle availability conditions поддерживают `completion` определённой activity, но не «получение компетенции с иерархическим наследованием». Транслировать пришлось бы в условие «завершить любой assessor компетенции», что теряет H-1 (наследование от sub-компетенции) и H-2 (выдача компетенции при завершении assessor с порогом).
   - `aggregate_required` (тип 9): Moodle gradebook categories поддерживают агрегаты по элементам категории, но не по произвольному набору activity вне иерархии. Транслировать пришлось бы через создание custom gradebook category, что меняет структуру курса.
3. **Двойная инвалидация.** При изменении политики надо синхронно записывать в OWL и в Moodle DB, поддерживать целостность при сбоях одной из сторон, обрабатывать конфликты (методист правит availability в Moodle UI напрямую) — отдельная распределённая задача.

### 10.3. Режим Б — single PDP

**Что это.** Политики хранятся **только** в нашей онтологии. Существующие availability conditions в Moodle при импорте курса игнорируются. Enforcement делегируется Moodle на наш PDP через REST API: custom availability condition plugin на стороне Moodle при каждом рендере activity вызывает наш `GET /api/v1/access/student/{sid}/element/{eid}` и блокирует элемент при отрицательном ответе.

**Поток данных.**

1. **Импорт структуры курса (один раз):** `MoodleCourseImporter.import_course(course_id)` через Moodle Web Services читает иерархию Course → Section → Activity, создаёт ABox в нашей системе. Существующие availability conditions Moodle игнорируются.
2. **Управление правилами:** методист создаёт и редактирует политики **только через наш UI** (PAP). В Moodle availability conditions не трогаются.
3. **Получение событий прогресса (постоянно):** custom Moodle event observer plugin подписан на `\core\event\course_module_completion_updated`, `\mod_quiz\event\attempt_submitted`, `\mod_assign\event\submission_graded` и шлёт webhook на `POST /api/v1/events/progress`. Этот эндпоинт уже существует в `IntegrationService` (DSL §40, OPAPI4) — режим Б предусмотрен с момента проектирования API.
4. **Применение правил (на каждый запрос):** custom Moodle availability condition plugin при показе activity делает `GET /api/v1/access/student/{sid}/element/{eid}` и возвращает `bool` + локализованное сообщение пользователю.

**Свойства режима Б.**

- Все 9 типов правил работают одинаково через REST API; никакой трансляции в чужой формат нет.
- Источник истины — наша онтология; Moodle не имеет копии политик и не может «отстать» или «противоречить».
- Архитектурно Moodle становится чистым PEP, как в стандартной XACML-конфигурации.
- Цена — два PHP-плагина на стороне Moodle (event observer ~50 строк, availability condition ~100 строк) и сетевой вызов на каждый рендер activity (mitigated кэшем PDP, см. НФТ-1 §2.7.4).

### 10.4. Сравнение режимов

| Критерий | Режим А (twin storage) | Режим Б (single PDP) |
|---|---|---|
| Источник истины политик | OWL + Moodle DB (требует sync) | Только OWL |
| Enforcement | PHP-интерпретатор Moodle | Наш PDP через REST |
| Покрытие 9 типов правил | Частичное (теряются 4, 9) | Полное |
| Положение 2 на защите | Подрывается (verify в OWL ≠ enforce в Moodle) | Прямо подтверждается |
| Цена на стороне Moodle | Использовать существующий механизм + transmit-обратная трансляция в нашей системе | 2 кастомных PHP-плагина |
| Latency на access-check | 0 (локальный PHP) | 1 HTTP-вызов к нашему PDP (mitigated cache hit ≤50 мс) |
| Доступность | Moodle работает при недоступности нашей системы | Fail-close (см. §11.5.4 + НФТ-3 timeout) |
| Совместимость с проблемой P1 главы 1 | Не решает (та же процедурность) | Решает (формальное представление + декларативный enforcement) |

### 10.5. Выбор режима Б — обоснование

Режим Б выбран по двум причинам:

1. **Сохранение гипотезы работы и положений на защиту.** В режиме А научная новизна 1 и 3 теряют связь с реальным enforcement: онтология становится «удобной формой записи правил с верификацией», а исполнение остаётся процедурным. В режиме Б онтология одновременно носитель формальной семантики, основа для верификации и source-of-truth для enforcement через REST.

2. **Полнота покрытия 9 типов.** Режим Б работает для всех типов правил без исключений; режим А теряет типы 4 (competency_required) и 9 (aggregate_required) при трансляции.

Цена режима Б — два PHP-плагина на стороне Moodle и сетевой вызов на каждый рендер. Latency mitigated через кэш Redis (НФТ-1 ≤50 мс при cache hit, p99 1.61 мс на reference hardware — EXP4 §4.4.3 ПЗ); failure-mode (fail-close при недоступности PDP) соответствует принципу least privilege NIST SP 800-162.

### 10.6. Архитектурные следствия

- **Ядро системы платформо-независимо.** Ни в TBox (§1), ни в SWRL-каталоге (§2), ни в сервисах нет сущностей, специфичных для Moodle. Адаптация под конкретную СДО — изолированный слой переводчика на границе системы (`code/integrations/<platform>/`).
- **Адаптер для каждой СДО — это PIP + PEP-плагины.** PIP-часть (импорт структуры через Web Services + получение событий через webhooks) пишется на стороне нашего адаптера. PEP-часть (availability condition в UI СДО) — на стороне платформы (PHP для Moodle, Python plugin для Open edX, JavaScript-overlay для Stepik и т. д.).
- **Существующий код спроектирован под режим Б.** Эндпоинты `IntegrationService.sync_course_structure` (POST /integration/courses/{id}/sync, OPAPI3) и `IntegrationService.record_progress_event` (POST /events/progress, OPAPI4) есть в DSL §40 и реализованы в фазе 2. Это документирование уже принятого решения, а не ретрофит под Moodle.

---

## 11. Референсный адаптер для Moodle

> **Назначение раздела:** конкретизировать режим Б на одной из 5 целевых платформ (Moodle, как наиболее распространённая и документированная). Используется как фактура для главы 3 §3.4 ПЗ. Маппинг онтологии на остальные 4 СДО — в §9.

### 11.1. Структура адаптера

Артефакт реализации — `code/integrations/moodle/`:

```
code/integrations/moodle/
├── moodle_client.py              — обёртка над Moodle Web Services (REST API)
├── adapter.py                    — MoodleCourseImporter.import_course(course_id)
├── translators.py                — маппинг сущностей Moodle на классы TBox
├── docker-compose.moodle.yml     — отдельный compose-стэк с bitnami/moodle (не в основной)
├── php/
│   ├── event_observer.php        — спецификация PHP-плагина (не runnable)
│   └── availability_condition.php — спецификация PHP-плагина (не runnable)
└── README.md                     — инструкции запуска и known issues
```

В терминах §10.1: Python-часть (`moodle_client.py`, `adapter.py`, `translators.py`) — PIP-адаптер; PHP-часть (`event_observer.php`, `availability_condition.php`) — PEP-плагины.

### 11.2. Маппинг сущностей Moodle на TBox

Полная таблица соответствий, используемая `translators.py`:

| Moodle | Тип в TBox | Поле-связь Moodle | Поле-связь TBox | Примечание |
|---|---|---|---|---|
| `course` | `Course` | `course.shortname` | `Course.individual_name` | shortname как стабильный идентификатор |
| `course.fullname` | datatype `has_title` | `course.fullname` | `has_title` |  |
| `section` | `LearningModule` | `section.id` (целое) | `module_<id>` | sequence на курсе |
| `section.name` | datatype `has_title` | `section.name` | `has_title` |  |
| `course_module` (cm) | `LearningActivity` | `cm.id` | `activity_<id>` | подкласс по `cm.modname` |
| `cm.modname == "quiz"` | `Quiz` (subclass) | — | `is_a` | специализация TBox |
| `cm.modname == "lesson"` | `Lesson` | — | `is_a` |  |
| `cm.modname == "assign"` | `Assignment` | — | `is_a` |  |
| `cm.modname == "page"` / `"resource"` | `Resource` | — | `is_a` |  |
| `cm.completion == 2` (manual) | datatype `is_mandatory` | `cm.completion` | `is_mandatory=True` | методист отметил обязательность |
| `user` | `Student` | `user.id` | `student_<id>` |  |
| `user.firstname + lastname` | datatype `has_full_name` | конкатенация | `has_full_name` |  |
| `group` | `Group` | `group.id` | `group_<id>` |  |
| group membership (`groups_members`) | `belongs_to_group` | (user_id, group_id) | object property |  |
| `grade_item` | связан с `LearningActivity` | `grade_item.iteminstance == cm.instance` | через cmid | используется для grade_required |
| `course_competency` | `Competency` | `competency.id` | `comp_<id>` | опционально, через core_competency API |

Сущности Moodle, **не импортируемые** в TBox (по решению §10.3): `course_modules.availability` (политики Moodle игнорируются — источник истины наша система), `availability_conditions_*` (внутренние таблицы Moodle availability), `course_format` (визуальная конфигурация).

### 11.3. Импорт структуры курса (PoC реализован)

**Web Services endpoints**, используемые `adapter.py`:

| Endpoint | Назначение |
|---|---|
| `core_course_get_courses_by_field` | Метаданные курса по shortname или id |
| `core_course_get_contents` | Список sections + course_modules с метаданными |
| `core_user_get_users_by_field` | Студенты курса |
| `core_enrol_get_enrolled_users` | Альтернатива — список зачисленных |
| `core_group_get_course_groups` | Группы курса |
| `core_group_get_group_members` | Членство в группах |
| `core_grades_get_grade_items` | Gradebook (для связи cm ↔ grade_item) |
| `core_competency_list_course_competencies` | Компетенции курса (опционально) |

**Алгоритм** `MoodleCourseImporter.import_course(course_id)`:

1. Открыть Web Services сессию с токеном из конфигурации.
2. Получить курс через `core_course_get_courses_by_field`; создать `Course` индивид в OWL.
3. Получить содержимое через `core_course_get_contents`; для каждой section создать `LearningModule`, для каждого cm создать `LearningActivity` соответствующего подкласса (через `translators.py`).
4. Получить студентов через `core_enrol_get_enrolled_users`; создать `Student` индивидов.
5. Получить группы и членство; создать `Group` индивидов и `belongs_to_group` отношения.
6. Получить gradebook items; связать с `LearningActivity` через `cmid`.
7. Опционально получить компетенции и связи `assesses` через `core_competency`.
8. Сохранить ABox через `OntologyCore.save()`.
9. Инициировать первый прогон reasoner-а через `ReasoningOrchestrator.reason_full()`.
10. Вернуть статистику (числа созданных индивидов, время выполнения, warnings).

**Важно:** существующие availability conditions Moodle при импорте **игнорируются**. Это часть выбора режима Б (§10.3).

### 11.4. Получение событий прогресса (спроектирован)

**События Moodle**, на которые подписан observer plugin:

| Событие | Когда генерируется | Полезные поля |
|---|---|---|
| `\core\event\course_module_completion_updated` | Студент или система отметили cm как completed | `userid`, `objectid` (cm.id), `relateduserid` |
| `\mod_quiz\event\attempt_submitted` | Сохранена попытка quiz с финальной оценкой | `userid`, `objectid` (attempt.id), `contextinstanceid` (cmid), grade через `quiz_attempts` |
| `\mod_assign\event\submission_graded` | Преподаватель выставил оценку assignment | `userid`, `objectid` (grade.id), `relateduserid` |

**Webhook** на нашу систему: `POST /api/v1/events/progress` с payload:

```json
{
  "student_id": "user_42",
  "element_id": "activity_quiz_3",
  "status": "completed",
  "grade": 87.5,
  "timestamp": "2026-04-25T12:34:56Z"
}
```

Эндпоинт уже существует в `IntegrationService` (DSL §40, OPAPI4); идемпотентность обеспечена `ProgressRepository.upsert_record` (по `(student_id, element_id)`).

**Спецификация PHP event observer** (`code/integrations/moodle/php/event_observer.php`, не runnable, ~30 строк ключевой функции):

```php
public static function handle_completion_updated(\core\event\course_module_completion_updated $event) {
    $config = get_config('local_external_pdp');

    $payload = [
        'student_id'  => 'user_' . $event->relateduserid,
        'element_id'  => 'activity_' . $event->contextinstanceid,
        'status'      => self::map_completion_state($event->other['completionstate']),
        'grade'       => self::fetch_grade($event->relateduserid, $event->contextinstanceid),
        'timestamp'   => gmdate('c', $event->timecreated),
    ];

    $ch = curl_init($config->pdp_url . '/api/v1/events/progress');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 2,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json',
                                   'Authorization: Bearer ' . $config->api_token],
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode($payload),
    ]);
    $response = curl_exec($ch);

    if (curl_errno($ch) || curl_getinfo($ch, CURLINFO_HTTP_CODE) !== 200) {
        // Сохранить в локальный retry-буфер для reconciliation worker
        self::enqueue_retry($payload);
    }
    curl_close($ch);
}
```

Полная реализация PHP-плагина — в перспективы (отдельная инженерная задача).

### 11.5. Применение правил (спроектирован)

**Custom Moodle availability condition plugin** размещается в `availability/condition/external_pdp/`. Стандартный механизм Moodle: Moodle вызывает `condition::is_available($cm, $userid)` на каждый рендер activity на странице курса.

**Спецификация PHP availability condition** (`code/integrations/moodle/php/availability_condition.php`, не runnable, ~30 строк):

```php
public function is_available($not, info $info, $grabthelot, $userid) {
    $config = get_config('availability_external_pdp');
    $cmid   = $info->get_context()->instanceid;

    $url = sprintf(
        '%s/api/v1/access/student/user_%d/element/activity_%d',
        $config->pdp_url, $userid, $cmid
    );

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT_MS     => 200,           // НФТ-1 жёсткий budget
        CURLOPT_HTTPHEADER     => ['Authorization: Bearer ' . $config->api_token],
    ]);
    $response = curl_exec($ch);

    if (curl_errno($ch) || curl_getinfo($ch, CURLINFO_HTTP_CODE) !== 200) {
        // Fail-close по принципу least privilege (NIST SP 800-162)
        $this->reason = get_string('pdp_unavailable', 'availability_external_pdp');
        return false;
    }
    curl_close($ch);

    $verdict = json_decode($response, true);
    $allow   = $verdict['access'] === 'allow';
    if (!$allow) {
        $this->reason = $verdict['reason'] ?? get_string('blocked_default', 'availability_external_pdp');
    }
    return $allow XOR $not;
}
```

**Кэш на стороне Moodle не используется:** наш PDP уже кэширует через Redis (НФТ-1 50 мс p99 — cache hit, EXP4 §4.4.3); дублирование кэша на стороне Moodle усложняет инвалидацию без выигрыша.

### 11.6. Ограничения режима Б на практике

1. **Latency на access-check.** На каждый рендер страницы курса — N HTTP-вызовов (по числу activity на странице). При N=20 и cache hit это 20 × 1.4 мс ≈ 28 мс — приемлемо. Cold start (cache miss + reasoning) — до 2 с (НФТ-2), один раз в первом запросе пользователя в сессии. Mitigation: warm-up cache при login через batch-вызов `GET /api/v1/access/student/{sid}/course/{cid}` (UC-4 batch).

2. **Fail-open vs fail-close.** При недоступности PDP plugin блокирует всё (fail-close — secure default по NIST SP 800-162). Альтернатива fail-open снимает блокировку при сбое — отвергнута: ломает гарантии безопасности доступа.

3. **Eventual consistency прогресса.** Между событием Moodle и инвалидацией нашего кэша — задержка 100–500 мс (HTTP-roundtrip + reasoning). На практике не критично: студент не «опережает» reasoning при последовательном прохождении activity. Worst case — устаревший verdict на 500 мс, после чего пользователь делает refresh.

4. **Webhook delivery guarantees.** At-least-once с retry на стороне Moodle (локальный буфер в Moodle DB при недоступности нашего API). Идемпотентность нашего `/events/progress` обеспечена upsert-семантикой в `ProgressRepository`.

5. **Reconciliation.** Периодический worker (раз в час), который полным проходом по `core_completion_get_activities_completion_status` per student сверяет completion states с нашим ABox и компенсирует пропущенные события. Реализация — в перспективы.

### 11.7. Что требует реализации (вынесено в перспективы)

- PHP availability condition plugin (~100 строк рабочего кода + локализация + tests).
- PHP event observer plugin (~50 строк + db/events.php регистрация).
- Reconciliation worker (Python service, опрос Moodle Web Services по cron).
- Пилотное внедрение совместно с ООО «Дистех» с актом о внедрении (требование К1 критериев оценки ВКР).

---

## 12. Что осталось по разделу 3.5.3

В рамках 3.5.3 (Модели данных) этот сателлит полностью покрывает:

- [x] OWL TBox — онтологическая схема (раздел 1)
- [x] SWRL — каталог правил, 9 типов + мета-правило + вспомогательное (раздел 2)
- [x] Связь с СВ-1…СВ-5 (раздел 3)
- [x] CWA-enforcement — позиция в архитектуре (раздел 4, полная формализация — в 3.5.4 A2)
- [x] OWL ABox — демо-курс (раздел 6, 21.04)
- [x] REST API — OpenAPI-ревизия (раздел 7, 21.04)
- [x] Redis — схема кэша (раздел 8, 21.04)
- [x] Маппинг совместимости с СДО — все три слоя (раздел 9, 21.04)
- [x] Интеграционный слой: режимы и обоснование выбора (раздел 10, 25.04)
- [x] Референсный адаптер для Moodle (раздел 11, 25.04)

**Раздел 3.5.3 PROJECT_BIBLE закрыт.** Следующая итерация сателлита — только в ответ на изменения в коде фазы 2 (OPAPI1–OPAPI13, T1–T13 и прочие пункты дифа).
