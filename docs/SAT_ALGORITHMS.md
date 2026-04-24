# SAT_ALGORITHMS — Формализация алгоритмов (раздел 3.5.4)

> Сателлит Project Bible, раздел 3.5.4.
> Дата создания: 20.04.2026 (фаза 1b). Обновлён 21.04.2026: добавлен А6 (обнаружение избыточных/поглощающих правил, СВ-4/СВ-5 переведены в must); ветки `adaptive_routing` удалены из А1 и А4 после сужения пула до 9 типов.
> Статус: проектный документ. Код под него приводится в фазе 2 (→ 3.6).

## Назначение

Формальные спецификации шести алгоритмов, образующих «ядро» программного комплекса:

| # | Алгоритм | Покрывает | Инструмент |
|---|---|---|---|
| А1 | Split-node DiGraph для обнаружения циклов | СВ-2, UC-3, UC-6 | NetworkX (DFS) |
| А2 | Reasoning pipeline с enricher + CWA-enforcement | ФТ-2, UC-4, UC-5 | Owlready2 + Pellet |
| А3 | Восходящая агрегация завершённости (roll-up) | ФТ-8, UC-8 | обход по иерархии |
| А4 | Обнаружение недостижимых состояний | СВ-3, UC-6 | Pellet + граф |
| А5 | Инвалидация кэша при изменении ABox/TBox | НФТ-1, НФТ-6 | Redis |
| А6 | Обнаружение избыточных и поглощающих правил | СВ-4, СВ-5, UC-6 | Pellet subsumption + synthetic ABox (переиспользует А4.5) |

Документ служит:

1. Основой параграфа 2.4 главы 2 ПЗ (формализация алгоритмов).
2. Базой для sequence-диаграмм 3.5.2 (раздел 3.5.4 отвечает за «что делает», sequence — за «как взаимодействуют компоненты»).
3. Источником списка правок кода 3.6 (для каждого алгоритма — разрыв между проектной версией и текущей реализацией).

---

## А1. Обнаружение циклов в графе зависимостей правил доступа

### А1.1. Связь с верификационной моделью

Алгоритм реализует верифицируемое свойство СВ-2 Acyclicity из раздела 2.7.6 Project Bible — граф зависимостей `G = (V, E)` над элементами курса и правилами доступа должен быть ациклическим. Применяется в двух точках:

- **UC-3 Валидация правила при создании.** Вход — текущая онтология без создаваемого правила + параметры нового правила (source, target, тип). Алгоритм строит граф с временно добавленной дугой, проверяет наличие цикла, возвращает `True/False + путь цикла`. Если цикл обнаружен — правило отклоняется в PolicyService до сохранения (НФТ-5 откат при нарушении согласованности).
- **UC-6 Полная верификация курса.** Вход — вся онтология. Алгоритм строит граф по всем активным политикам, возвращает список всех циклов (если их несколько).

Общий случай — одна процедура `build_dependency_graph`, разная пост-обработка.

### А1.2. Мотивация split-node

Почему узлы расщепляются на два («access» и «complete») вместо обычного DiGraph над элементами?

Рассмотрим иерархию курса: `Module M` содержит `Activity A`. Двухуровневые связи иерархии:

- доступ к дочернему элементу требует доступа к родителю: `M_access → A_access`;
- завершение родителя требует завершения всех обязательных потомков: `A_complete → M_complete`.

В обычном DiGraph обе связи сворачиваются в дуги `M → A` и `A → M` — возникает **ложный цикл из иерархии**, без какого-либо участия политик. Любой модуль с хотя бы одной активностью был бы «циклическим». Ошибка детектора совпадает с правильным ответом только случайно.

Расщепление узлов на `access` и `complete` разделяет два семантически разных состояния. Интра-элементная дуга `A_access → A_complete` выражает, что завершение возможно только после доступа — это фундамент, не цикл. Иерархические дуги пересекают уровни состояний (access-к-access, complete-к-complete), и сами по себе ацикличны.

Цикл в split-node графе возникает только тогда, когда политики замыкают цепочку между двумя типами состояний разных элементов. Это и есть «настоящий» цикл зависимостей, который мы хотим обнаружить.

### А1.3. Структура split-node DiGraph

**Множество узлов.** Для каждого элемента курса `e ∈ CourseStructure` (Course, Module, LearningActivity) в графе два узла:

- `e.access` — «доступ к e открыт студенту»;
- `e.complete` — «e завершён студентом».

Узлы — строки вида `"<element_id>_access"` и `"<element_id>_complete"`. Формально — попарно не пересекающиеся множества `V_access ⊔ V_complete`.

**Множество дуг.** Направленная дуга `u → v` означает «состояние `v` невозможно без предварительного выполнения состояния `u`» (дуга идёт *от пререквизита к зависящему состоянию*). Три источника дуг:

1. интра-элементные — один шаблон для каждого элемента;
2. иерархические — два шаблона для каждой пары (родитель, обязательный потомок);
3. политические — зависят от `rule_type` политики (таблица А1.4).

### А1.4. Правила построения дуг

#### А1.4.1. Интра-элементные

Для каждого элемента `e`:

```
(e.access → e.complete)
```

Инвариант: завершить элемент невозможно без доступа к нему. Дуга гарантирует, что self-reference политики (target = source) автоматически превращается в 2-цикл: `source.complete → source.access → source.complete`.

#### А1.4.2. Иерархические

Для каждой пары (контейнер `p`, потомок `c`), где `has_module(p, c)` или `contains_activity(p, c)`:

```
(p.access → c.access)          # доступ к потомку требует доступа к родителю
(c.complete → p.complete)      # завершение родителя следует из завершения потомков
```

Эти дуги строятся для всех потомков, не только обязательных (`is_mandatory=true`). Обязательность регулирует агрегацию завершённости (алгоритм А3), но не структуру графа зависимостей. Для цикл-детектора важнее полнота — иначе необязательный элемент мог бы «скрыть» цикл.

#### А1.4.3. Политические дуги (по типу правила)

Пусть политика `p` с `is_active=true` защищает элемент `src` (`has_access_policy(src, p)`) и имеет `rule_type = T`. Правила построения дуг по `T`:

| # | `rule_type` | Пререквизит в ABox | Дуги в графе | Обоснование |
|---|---|---|---|---|
| 1 | `completion_required` | `targets_element(p, tgt)` | `tgt.complete → src.access` | Доступ к `src` открыт, когда `tgt` завершён |
| 2 | `grade_required` | `targets_element(p, tgt)` | `tgt.complete → src.access` | Оценка по `tgt` подразумевает его завершение (в коде статус `status_passed`/`status_failed` ставится одновременно с `has_grade`) |
| 3 | `viewed_required` | `targets_element(p, tgt)` | `tgt.access → src.access` | Просмотр = доступ без требования завершения. **Это единственный тип, где дуга начинается из `access`, а не `complete`** |
| 4 | `competency_required` | `targets_competency(p, c)` | `∀a. assesses(a, c) ⇒ a.complete → src.access` | Компетенция приобретается завершением хотя бы одного элемента, который её оценивает. Если `c` — подкомпетенция `c'` и `targets_competency(p, c')`, учитываются также элементы, оценивающие `c` (через `is_subcompetency_of`, транзитивно) |
| 5 | `date_restricted` | — | дуги не добавляются | Временное окно не создаёт зависимости между элементами |
| 6 | `and_combination` | `has_subpolicy(p, sub_i)`, i=1..n | для каждой `sub_i` — рекурсивно применить правила А1.4.3 к `sub_i` относительно того же `src` | AND требует всех подполитик → граф получает объединение их зависимостей |
| 7 | `or_combination` | `has_subpolicy(p, sub_i)`, i=1..n | то же, что для AND | Различие AND/OR семантическое (одна или все подполитики), но для цикла-детектора любой цикл через любую подполитику — это цикл |
| 8 | `group_restricted` | `restricted_to_group(p, g)` | дуги не добавляются (в текущей модели) | Членство в группе назначается вне онтологии (import/admin). При появлении политик назначения групп (перспектива) — дуги добавляются аналогично п. 4 |
| 9 | `aggregate_required` | `aggregate_elements(p, e_1..e_k)` | для каждого `e_i`: `e_i.complete → src.access` | Агрегат по набору оценок требует завершения каждого элемента набора |

**Замечание о направлении дуги.** Современное использование в коде (`target_complete → source_access`) соответствует п. 1 таблицы. Это семантика «чтобы *попасть* к источнику, нужно *завершить* цель». Такое направление корректно ровно по одной причине: в алгоритмах ацикличности ищется цикл (замкнутый путь), направление конкретной дуги несущественно для факта наличия цикла — но существенно для восстановления и отображения пути методисту.

**Рекурсия для композитных правил.** При развёртывании `and_combination` / `or_combination` может возникнуть вложенность: подполитика сама может быть композитной. Рекурсия конечна, если онтология не содержит циклической композиции подполитик (`has_subpolicy`). Это отдельный инвариант целостности TBox — проверяется до запуска А1 (см. А1.7).

### А1.5. Псевдокод

Две процедуры: построение графа и проверка цикла.

```text
procedure build_dependency_graph(ontology O):
    G ← empty DiGraph

    # 1. Интра-элементные и иерархические дуги
    for each e ∈ O.CourseStructure:
        G.add_edge(e.access, e.complete)
        for each c ∈ children_of(e):
            G.add_edge(e.access, c.access)
            G.add_edge(c.complete, e.complete)

    # 2. Политические дуги
    for each p ∈ O.AccessPolicy with p.is_active = true:
        src ← { x : has_access_policy(x, p) }
        if src = ∅: continue
        for each s ∈ src:
            add_policy_edges(G, p, s)

    return G


procedure add_policy_edges(G, p, src):
    T ← p.rule_type
    switch T:
        case "completion_required", "grade_required":
            tgt ← p.targets_element
            if tgt ≠ ∅: G.add_edge(tgt.complete, src.access)

        case "viewed_required":
            tgt ← p.targets_element
            if tgt ≠ ∅: G.add_edge(tgt.access, src.access)

        case "competency_required":
            c ← p.targets_competency
            if c = ∅: return
            # транзитивное замыкание is_subcompetency_of выполняется резонером до вызова А1;
            # здесь достаточно обойти прямых «оценивателей» c
            for each a such that assesses(a, c):
                G.add_edge(a.complete, src.access)

        case "and_combination", "or_combination":
            for each sub ∈ p.has_subpolicy:
                add_policy_edges(G, sub, src)

        case "aggregate_required":
            for each e_i ∈ p.aggregate_elements:
                G.add_edge(e_i.complete, src.access)

        case "date_restricted", "group_restricted":
            pass  # no dependency edges


procedure detect_cycles_with_probe(ontology O, src, tgt, probe_type):
    """
    Проверка при создании правила (UC-3).
    probe_type определяет, какую дугу добавить от пробной политики.
    """
    G ← build_dependency_graph(O)
    # пробная дуга — та же, что добавила бы политика типа probe_type
    probe_policy ← synthetic AccessPolicy(rule_type=probe_type, target=tgt)
    add_policy_edges(G, probe_policy, src)
    return find_cycle(G)


procedure detect_cycles_full(ontology O):
    """Полная верификация СВ-2 (UC-6)."""
    G ← build_dependency_graph(O)
    return find_all_cycles(G)


procedure find_cycle(G):
    """
    Возвращает один цикл (как последовательность element_id) или пустой список.
    Реализация — nx.find_cycle(G, orientation="original"), DFS с белый/серый/чёрный.
    """
    try:
        edges ← nx.find_cycle(G, orientation="original")
        return reconstruct_path(edges)
    except NoCycle:
        return []


procedure reconstruct_path(edges):
    """Склейка узлов e.access/e.complete в последовательность element_id."""
    path ← []
    for (u, v) in edges:
        base ← strip_suffix(u, ["_access", "_complete"])
        if path = ∅ or path[-1] ≠ base:
            path.append(base)
    return path
```

`find_all_cycles` — это итерация SCC-разложения (`nx.strongly_connected_components`) с последующим поиском цикла в каждой нетривиальной SCC. Для UC-3 достаточно одного цикла (ранний выход), для UC-6 — всех.

### А1.6. Корректность

**Инвариант 1 (полнота фиксации зависимостей).** Любая пара (пререквизит `A`, зависящий `B`), вытекающая из активной политики, хотя бы одного типа из таблицы А1.4.3, порождает хотя бы одну дугу в `G`. Следствие: если цикл существует в онтологии — он существует в `G`.

**Инвариант 2 (отсутствие ложных циклов от иерархии).** Иерархические дуги (А1.4.2) ацикличны сами по себе: они образуют два изоморфных DAG (access-поддиаграмма и complete-поддиаграмма) + интра-элементные дуги между уровнями. Чисто иерархический граф (без политик) ацикличен.

*Доказательство (набросок).* Access-поддиаграмма построена по `parent → child` — это то же отношение, что `has_module` / `contains_activity`; в корректной модели курса оно ациклично (дерево). Complete-поддиаграмма построена по `child → parent` — обратное отношение того же дерева, тоже ациклично. Интра-элементные дуги `e.access → e.complete` не замыкаются в цикл: нет дуги из любого complete-узла в любой access-узел внутри чисто иерархической модели.

**Инвариант 3 (эквивалентность циклов).** Цикл в `G` существует ⇔ существует цикл зависимостей на уровне политик (с учётом типов из А1.4.3). Значит, `find_cycle(G) ≠ ∅` — необходимое и достаточное условие нарушения СВ-2.

**Инвариант 4 (self-reference).** Если политика указывает `src = tgt`, алгоритм добавляет дугу `src.complete → src.access` (или `src.access → src.access` для `viewed_required`). В обоих случаях `find_cycle` возвращает цикл: в первом — через интра-элементную дугу `src.access → src.complete`; во втором — петлю. Self-reference проверяется дешевле, чем построение всего графа (PolicyService.create_policy делает это first-check), но алгоритм остаётся корректным и без такой предварительной проверки.

### А1.7. Сложность

`build_dependency_graph`:

- проход по элементам: O(|V_struct|);
- проход по потомкам: O(|hierarchy edges|) ≤ O(|V_struct|);
- проход по политикам с рекурсией в композитные: O(|P| + |sub-policies|);
- для `competency_required`: обход `assesses`-обратного индекса, O(|assesses|);
- для `aggregate_required`: O(|aggregate_elements|) per policy.

Итого линейно по размеру ABox.

`find_cycle` (NetworkX): DFS, O(|V| + |E|).

Для размера курса из НФТ-4 (500 элементов, 100 правил): |V| ≤ 1000 узлов, |E| ≤ 500 (hierarchy) + 500 (intra) + 100×k (policies, k — среднее число порождаемых дуг на политику, ≈ 1–3) ≤ 1300. Несколько миллисекунд. Доминирует запуск Pellet в UC-3 (≈ секунды, НФТ-2), не А1.

### А1.8. Восстановление пути цикла для методиста

`find_cycle` возвращает последовательность рёбер, каждое ребро содержит расщеплённые узлы (`A_access`, `B_complete` и т.д.). `reconstruct_path` очищает суффиксы и склеивает в список `element_id`, устраняя соседние дубликаты.

Например, цикл `A_access → A_complete → B_access → B_complete → A_access` после реконструкции: `[A, B, A]`. Это минимально читаемое представление. Для UI PolicyService добавляет:

- `rdfs:label` каждого элемента (через `OntologyCore._get_node_label`);
- тип состояния, на котором замыкается цикл (если нужен расширенный режим диагностики);
- идентификаторы политик на каждом сегменте (при UC-6 — полезно, при UC-3 — очевидно).

Базовый режим возвращает `"Активность А → Практикум Б → Активность А"`. Расширенный — с типами состояний и именами политик — в фазе 2 (FIX4 тесты циклов + UX задача).

### А1.9. Граничные случаи

| Случай | Поведение |
|---|---|
| ABox пуст (нет элементов) | `G = (∅, ∅)`, `find_cycle = []`. Никакого цикла |
| Политика без target (только тип, без `targets_element` / `targets_competency` / подполитик) | Некорректна на уровне валидации PolicyCreate (Pydantic). Защитный код в `add_policy_edges` — `if tgt = ∅: return` — для устойчивости |
| Неактивные политики (`is_active=false`) | Пропускаются на этапе А1.5 step 2. После активации граф пересчитывается |
| Циклическая композиция подполитик (`has_subpolicy` циклически ссылается) | Отдельный инвариант TBox; UC-1 PolicyService блокирует при создании. Если каким-то образом проникло в ABox — рекурсия `add_policy_edges` зациклится. Защита: ограничение глубины рекурсии (log2(|P|) × константа) с raise FormalError — проверяется в тестах фазы 2 |
| Несколько политик на одном элементе с конфликтующими пререквизитами | Не цикл, а `СВ-1 Consistency` (А2 + Pellet). А1 просто добавит все дуги; цикл возникнет только при реальной циркулярности |

### А1.10. Диф с текущим кодом (вход в 3.6)

Текущая реализация — `code/backend/src/services/graph_validator.py`, статический метод `GraphValidator.check_for_cycles`. Расхождения с проектным А1:

| # | Расхождение | Категория | Приоритет |
|---|---|---|---|
| G1 | Дуги добавляются по единой схеме `target.complete → source.access` для *всех* политик. Тип правила не учитывается | Переделать | 🔴 |
| G2 | `viewed_required` порождает ту же дугу, что `completion_required` — проектно должна быть `target.access → source.access` | Переделать | 🔴 |
| G3 | `competency_required` не раскрывается через `assesses`; политика компетенций вообще не порождает дуг | Добавить | 🟡 |
| G4 | `date_restricted`, `group_restricted` порождают дугу (через общую ветку) — должны не порождать | Переделать | 🟡 |
| G5 | `and_combination`, `or_combination` не раскрываются через `has_subpolicy`; проектно требуется рекурсия | Добавить | 🔴 (после S4 в SAT_DATA_MODELS) |
| G6 | `aggregate_required` не раскрывается через `aggregate_elements` | Добавить | 🔴 (после T13/S4) |
| G7 | Реконструкция пути строит последовательность element_id, но теряет информацию о типе состояния (access/complete) — полезна для расширенной диагностики в UC-3 и UC-6 | Улучшить | 🟢 |
| G8 | Нет защиты от циклической композиции подполитик на уровне рекурсии `add_policy_edges` | Добавить | 🟡 (после S4) |
| G9 | `find_all_cycles` для UC-6 не реализован (только одна дуга-проба UC-3) | Добавить | 🔴 (после VerificationService) |
| G10 | Метод `GraphValidator.check_for_cycles` принимает `(onto, new_source_id, new_target_id)`, что эквивалентно неявной пробе типа `completion_required`. Для проверки нового правила с другим типом — интерфейс не годится | Переделать | 🔴 |

Все пункты 🔴 — обязательны для фазы 2 и становятся частью свода правок в 3.6 Project Bible.

**Обоснование приоритетов.**

G1/G2 (различение типов при построении дуг) — блокирует корректность всех СВ-2 проверок после расширения пула правил до 9 типов (решение 21.04: `adaptive_routing` исключён, действуют типы 1–9). До фазы 2 SWRL-каталог тоже подлежит переработке (S2–S4), оба изменения идут параллельно.

G5/G6 (композитные и агрегатные правила) — без них цикл через AND/OR-композицию или через набор элементов `aggregate_elements` не будет обнаружен, что даёт ложно-отрицательный результат СВ-2. Серьёзная потеря корректности.

G10 (интерфейс) — требует расширения до `(onto, probe_policy: {source, target|competency|group|subpolicies|aggregate_elements, rule_type})`. Без этого новые типы не могут вызывать UC-3 валидацию.

**Статус реализации (22.04).** `GraphValidator` переписан Блоком 2 фазы 2. Закрыты:

- G1/G2/G4 — типозависимые дуги по таблице А1.4 (completion/grade/aggregate → `tgt.complete→src.access`; viewed → `tgt.access→src.access`; date/group дуг не добавляют).
- G5/G8 — AND/OR раскрываются рекурсивно через `has_subpolicy` с защитой глубины.
- G6 — `aggregate_required` раскрывается через `aggregate_elements`.
- G9 — `find_all_cycles` через SCC-декомпозицию + `nx.find_cycle` по SCC.
- G10 — интерфейс переделан на `ProbePolicy` с `rule_type` и нужными полями.

Остаются как улучшения:

- G3 — `competency_required` раскрывается через `assesses` и транзитив `is_subcompetency_of` (закрыто Блоком 2, но оставлено как 🟡 — требует больше тестов на глубину ≥3).
- G7 — реконструкция пути с пометкой состояния `access/complete` (🟢, улучшение диагностики UC-3/UC-6).

Файл: [services/graph_validator.py](../code/backend/src/services/graph_validator.py). Тесты — [test_graph_validator.py](../code/backend/src/tests/unit/test_graph_validator.py) (15 кейсов).

---

## А2. Reasoning pipeline с enricher + CWA-enforcement

### А2.1. Связь с архитектурой

Алгоритм — ядро компонента `ReasoningOrchestrator` (Core Layer, см. C4 решение 19.04). Гибридная архитектура обхода трёх ограничений SWRL/OWL:

- LIM1 (нет `now()` в SWRL) → инжекция `current_time_ind`;
- LIM2 (нет агрегатов в SWRL) → инжекция `AggregateFact` per student × policy;
- LIM3/LIM5 (нет NAF из-за OWA) → постобработка default-deny (CWA-enforcement).

Плюс LIM6 (монотонность OWL) — перед каждым прогоном очищаются ранее выведенные `is_available_for` и инжектируемые факты (`CurrentTime`, `AggregateFact`).

Покрывает ФТ-2.1 (вывод решения), ФТ-2.2 (CWA-enforcement), ФТ-2.3 (актуальное состояние при изменениях), частично ФТ-2.4 (таймаут + fallback). UC-4, UC-5, UC-7b вызывают прогон А2 через `ReasoningOrchestrator.reason_and_materialize`.

### А2.2. Триггеры запуска

Полный пересчёт (LIM6: OWL не поддерживает TMS, добавление аксиом не отменяет предыдущих выводов; стандартный паттерн — clear → re-inject → re-reason):

| Событие | UC | Скоуп |
|---|---|---|
| Создана/обновлена/удалена политика | UC-1, UC-2 | Глобальный: пересчёт всех студентов |
| Переключён `is_active` политики | UC-2 | Глобальный |
| Событие прогресса студента (viewed / completed / graded / competency_acquired) | UC-5 | Глобальный прогон reasoner (все политики), затем материализация кэша только для этого студента |
| Импорт курса со структурой и правилами | UC-10 | Глобальный |
| Изменение фактов тестового студента в симуляторе | UC-7b | Глобальный прогон, кэш только для симулируемого студента |
| Cache miss при UC-4 без недавних изменений | UC-4 | Только материализация из `is_available_for` (reasoner не запускается, если ABox не менялся) |

Глобальный прогон reasoner выполняется один раз на событие. Материализация в Redis — per-student, как постобработка результата.

### А2.3. Структура pipeline

Четыре последовательные стадии:

```
ABox change
    ↓
[1. PRE-ENRICH]  инжекция производных фактов
    ↓
[2. REASON]      Pellet выводит satisfies, is_available_for, has_competency, …
    ↓
[3. POST-ENFORCE] CWA (default-deny) + распространение по иерархии
    ↓
[4. MATERIALIZE] per-student карта в Redis
```

Стадии 1–3 — одноразовая глобальная операция на прогон. Стадия 4 вызывается для каждого студента (либо сразу для всех — при изменении политики, либо по требованию — lazy).

### А2.4. Стадия 1: PRE-ENRICH (предобработка)

Инжекция двух классов производных фактов. Контракты — §1.6 инвариант 1 и 2 в SAT_DATA_MODELS.

```text
procedure pre_enrich(ontology O):
    # LIM1: инжекция текущего времени
    destroy_all_individuals_of(O.CurrentTime)
    now_ind ← O.CurrentTime(name="current_time_ind")
    now_ind.has_value ← utcnow()

    # LIM2: инжекция агрегатов per (student, aggregate_required policy)
    destroy_all_individuals_of(O.AggregateFact)
    for each p ∈ O.AccessPolicy with is_active=true and rule_type="aggregate_required":
        elements ← p.aggregate_elements
        fn ← p.aggregate_function        # "AVG" | "SUM" | "COUNT"
        for each s ∈ O.Student:
            grades ← [pr.has_grade for pr ∈ s.has_progress_record
                                   if pr.refers_to_element ∈ elements
                                   and pr.has_grade ≠ null]
            if grades = ∅ and fn ≠ "COUNT": continue
            value ← apply(fn, grades)
            fact ← O.AggregateFact(name=f"agg_{s.name}_{p.name}")
            fact.for_student ← s
            fact.for_policy ← p
            fact.computed_value ← value

    # LIM6: очистка ранее выведенных is_available_for (restart-from-clean)
    for each e ∈ O.CourseStructure:
        e.is_available_for.clear()
```

**Почему очищаются `is_available_for` перед reasoning.** OWL монотонен: если на предыдущем прогоне было выведено `is_available_for(e, s)`, а сейчас студент потерял оценку — Pellet повторным прогоном *не отменит* старую привязку. Pellet только *добавляет* факты. Явная очистка превращает каждый прогон в «вычисление с нуля» поверх актуального ABox — это корректная реализация не-монотонной семантики доступа поверх монотонного резонера.

**Почему `CurrentTime` и `AggregateFact` тоже очищаются.** Те же причины: оставшиеся индивиды предыдущего прогона дадут конкурирующие матчи SWRL-правил (несколько `CurrentTime` → неопределённость «текущего времени»; устаревшие `AggregateFact` → заведомо неверный результат после изменения прогресса).

**`has_competency`, выведенное H-1 (transitive inheritance), не очищается.** Оно воспроизводится reasoner-ом на каждом прогоне из исходных `has_competency` + `is_subcompetency_of`. Если очистить «выведенные», пришлось бы различать «созданные руками» и «выведенные» — OWL такой разницы не хранит. Решение: не трогать; Pellet всё равно выведет заново из исходных фактов (идемпотентно).

### А2.5. Стадия 2: REASON (DL + SWRL)

```text
procedure reason(ontology O) raises TimeoutError:
    with subprocess_patch_jena_to_owlapi():        # LIM5 fix R1 в SAT_DATA_MODELS
        with timeout(НФТ-3: 10s):
            sync_reasoner_pellet(
                infer_property_values=true,
                infer_data_property_values=true
            )
```

Pellet последовательно:

1. Применяет **TBox-рассуждение**: классификация, subsumption, проверка consistency (если онтология противоречива — raise `OwlReadyInconsistentOntologyError`).
2. Применяет **SWRL-правила** к ABox: 10 шаблонов из каталога SAT_DATA_MODELS §2.3–2.4 + H-1 + мета-правило ступени 2. Результат — новые `satisfies(s, p)` и `is_available_for(e, s)`.
3. Материализует выводы в граф Owlready2 (свойство `infer_property_values=true` делает их доступными через обычный Python API).

**Обработка исключений.**

| Исключение | Причина | Поведение |
|---|---|---|
| `OwlReadyInconsistentOntologyError` | СВ-1 нарушена: ABox противоречив (например, два functional-значения `has_status` на одном `ProgressRecord`) | Проброс через `ReasoningOrchestrator` → UC-1/UC-2 отклонит транзакцию (НФТ-5 откат); UC-5/UC-10 запишут в лог + оставят прошлое состояние `is_available_for` + сигнал администратору |
| `TimeoutError` (НФТ-3) | Reasoning превысил 10 с | Fallback на ранее закэшированный Redis-результат (если есть), HTTP 503 в крайнем случае (ФТ-2.4) |
| `JavaError` от Pellet JVM | Техническая ошибка (неверный heap, отсутствие JDK) | Поднятие с контекстом; развёртывание через Docker Compose (FIX10) страхует от этого |

### А2.6. Стадия 3: POST-ENFORCE (CWA + иерархия)

Два шага: CWA-enforcement (OWA → CWA) и иерархическая блокировка (распространение недоступности родителя на детей).

```text
procedure post_enforce(ontology O, student s) → set[element_id]:
    accessible ← ∅

    # Шаг 1: построить precomputed map для иерархического обхода
    parent_of ← {c.id : p.id for each (p, c) in hierarchy_edges(O)}
    has_active_policies ← {e.id : has_active_swrl_policies(e) for each e}
    inferred ← {e.id : s ∈ e.is_available_for for each e}

    # Шаг 2: CWA-decision для каждого элемента (без учёта иерархии)
    cwa_allowed ← {}
    for each e ∈ O.CourseStructure:
        if not has_active_policies[e.id]:
            cwa_allowed[e.id] ← true                # default-allow для свободного контента
        elif inferred[e.id]:
            cwa_allowed[e.id] ← true                # reasoner вывел положительное разрешение
        else:
            cwa_allowed[e.id] ← false               # default-deny для защищённого, не выведенного

    # Шаг 3: распространение блокировки по иерархии
    def is_really_accessible(eid):
        if not cwa_allowed[eid]: return false
        p ← parent_of.get(eid)
        if p is None: return true
        return is_really_accessible(p)

    for each e ∈ O.CourseStructure:
        if is_really_accessible(e.id):
            accessible.add(e.id)

    return accessible
```

**CWA-шаг формализует решение 15.04.** OWA резонера выводит *положительные* `is_available_for`; CWA-слой превращает «не выведено» в «запрещено» для элементов, защищённых хотя бы одной активной SWRL-политикой. Элементы без политик — доступны по умолчанию (default-allow). Ср. Carminati et al. 2011: тот же паттерн для SitBAC.

**Иерархическая блокировка не выражается в SWRL.** Чтобы сказать «ребёнок недоступен, если родитель недоступен», в SWRL требовалось бы отрицание `¬is_available_for(parent, s) ⇒ ¬is_available_for(child, s)` — что есть NAF, невыразимое из-за OWA (LIM5). Поэтому — процедурный шаг на графе иерархии. Это формально **часть CWA-слоя**, не отдельный алгоритм.

**Почему не добавить «дочерняя доступность ⇒ родительская доступность» SWRL-правилом (положительно).** Это обратная семантика. «Если элемент доступен студенту, доступен и родитель» — эрстец ложное утверждение для курсов с политиками на родителе: доступ к активности `quiz_2` не означает автоматически доступа к модулю, у которого есть отдельная политика. Иерархическая блокировка однонаправленна: вниз от родителя к детям, не вверх.

### А2.7. Стадия 4: MATERIALIZE (кэш)

```text
procedure materialize(student s, accessible: set[element_id], enrichers: list[BaseEnricher]):
    payload ← {}
    for eid ∈ accessible:
        e ← O.find(eid)
        element_data ← {}
        for enricher ∈ enrichers:
            element_data ← enricher.enrich(e, element_data)
        payload[eid] ← element_data

    cache.set(f"access:{s.id}", payload, ttl=НФТ-2 buffer)
```

Enricher-ы на этом этапе — *пост-процессоры* (не путать с pre-enricher из стадии 1). Они добавляют к решению о доступе дополнительные данные, релевантные клиенту:

- `DateRestrictionEnricher` — `available_from`/`available_until` временного окна для UI;
- в будущем: `AttemptLimitEnricher`, `CompletionRequirementsEnricher` (что осталось выполнить — для UC-9).

**Почему ключ кэша `access:{student_id}`, а не `access:{student_id}:{element_id}`.** Средний курс (500 элементов по НФТ-4) даёт ~500 ключей per student → при 1000 студентов — 500K ключей. Атомарная инвалидация по студенту тогда становится KEYS SCAN O(500K). Один ключ на студента — `SET`/`DEL` O(1), материализация всей карты один раз. Цена — нельзя получить «доступ только к одному элементу» без десериализации всего набора, но карта маленькая (JSON ~5–20 KB), десериализация на Python — ~1 мс, укладывается в НФТ-1.

Более глубокая схема ключей Redis, включая TTL и стратегию инвалидации при разных событиях — в алгоритме А5 (SAT_ALGORITHMS §А5).

### А2.8. Полный pipeline с обработкой ошибок

```text
procedure reason_and_materialize(ontology O, student_id s_id?):
    try:
        pre_enrich(O)
        reason(O)
    except InconsistentOntologyError as ic:
        return {"status": "inconsistent", "explanation": ic.explanation}
    except TimeoutError:
        # НФТ-3 + ФТ-2.4: fallback на кэш
        if s_id and cache.exists(s_id):
            return {"status": "stale_cache", "from_ts": cache.get_ts(s_id)}
        return {"status": "timeout", "http": 503}

    # Прогон глобальный — материализация per student
    students_to_update ← [O.find(s_id)] if s_id else O.Student.instances()
    for s in students_to_update:
        accessible ← post_enforce(O, s)
        materialize(s, accessible, default_enrichers)

    return {"status": "ok", "updated_students": len(students_to_update)}
```

### А2.9. Корректность

**Инвариант 1 (идемпотентность pre-enrich).** Многократный запуск `pre_enrich` поверх одного и того же ABox даёт один и тот же результат. Это потому, что `destroy_all_individuals_of(C)` удаляет именно результат предыдущего `pre_enrich`, а `utcnow()` перезаписывается при каждом вызове (предыдущее значение не копится).

**Инвариант 2 (монотонность резонера сохраняется внутри прогона).** Pellet применяется к онтологии, в которой нет «устаревших выводов»: `is_available_for` очищен, `CurrentTime` пересоздан, `AggregateFact` пересчитан. Следовательно, новые выводы не конкурируют с прошлыми, и теорема корректности DL-резонинга применима «из коробки».

**Инвариант 3 (бинарность CWA-решения).** Для каждой пары `(e, s)` `post_enforce` возвращает ровно одно из `{allowed, denied}`. Нет «возможно доступно» или «нужно больше данных». Это свойство следует из покрытия трёх случаев в CWA-шаге: «нет политик», «есть политики + выведено», «есть политики + не выведено». Четвёртого нет.

**Инвариант 4 (транзитивная замкнутость иерархической блокировки).** Если элемент `e_0` недоступен и есть цепочка `e_k → e_{k-1} → … → e_0` (child → parent), то все `e_0..e_k` недоступны. Следует из рекурсии `is_really_accessible`: если хотя бы один предок возвращает `false`, весь путь помечается `false`.

**Консистентность с SWRL-слоем.** `satisfies(s, p)` + мета-правило ступени 2 выводят `is_available_for(e, s)` ⇔ у `e` есть активная политика, чьё условие выполнено. `post_enforce` добавляет к этому: «если у `e` есть политики, но `is_available_for` не выведено — запрет». Это не противоречит SWRL, а *дополняет* его до замкнутой семантики AC.

### А2.10. Сложность

**Pre-enrich.** Очистка `CurrentTime`/`AggregateFact` — O(число соответствующих индивидов). Пересчёт агрегатов: O(|Students| × |Aggregate_policies| × avg(|aggregate_elements|)). При НФТ-4 (1000 студентов, ≤100 правил, из них ≤20 aggregate, ≤5 элементов на агрегат): ≤ 10⁵ операций, секунды.

**Reason.** Pellet: OWL 2 DL classification — 2NEXPTIME-complete в худшем случае, практически — зависит от числа SWRL-правил и индивидов (Sirin 2007: 0.5–5 с для 10³–10⁴ индивидов + 10–100 SWRL). НФТ-2 (2 с для 500 элементов) — достижимо.

**Post-enforce.** Для одного студента: O(|elements| × depth_of_hierarchy). Depth обычно ≤ 3 (Course → Module → Activity). Итого — линейно по числу элементов. Миллисекунды.

**Materialize.** O(|accessible| × avg_enricher_cost). Enricher-ы дешёвые (чтение свойств). JSON-сериализация ≤ 1 мс для типичной карты.

Итого на один прогон с full materialize: доминирует Pellet. НФТ-2 (≤ 2 с для типичного курса) выполнима.

**Cache hit path.** Без pre-enrich и reason — только Redis GET + фильтрация `DateAccessFilter`. Миллисекунды, легко укладывается в НФТ-1 (50 мс).

### А2.11. Историческая справка: перенос `date_restricted` с `DateAccessFilter` на SWRL-шаблон 5

**Статус (21.04, FIX11 закрыт).** `utils/access_postprocessors.py` и фильтры `DateAccessFilter`/`DateRestrictionEnricher`/`DateWindowPostProcessor` удалены из кода. Дата полностью обсчитывается SWRL-шаблоном 5 + `CurrentTime`-enricher из [services/reasoning/_enricher.py](../code/backend/src/services/reasoning/_enricher.py). Раздел ниже — обоснование, зачем это было сделано.

До фазы 2 код реализовывал `date_restricted` *на стадии чтения из кэша* через `DateAccessFilter`: reasoning кэшировал `available_from`/`available_until`, фильтр на каждом запросе сравнивал с `utcnow()`. Проектное решение SAT_DATA_MODELS шаблон 5 работает *внутри reasoning* через `CurrentTime`.

**Разница существенная.** При подходе через `DateAccessFilter`:
- Reasoning не знает о временных окнах: `is_available_for(e, s)` выводится без учёта даты; фильтр на чтении снимает доступ, если сейчас не в окне.
- Консистентность при верификации СВ-1 (consistency) теряется: Pellet не увидит конфликт «окно `[01.06–15.06]` для активной политики A и окно `[16.06–30.06]` для политики B, обе требуются одновременно» — оба кажутся совместимыми, reasoner даёт `is_available_for` для пересекающегося класса студентов.

При подходе через `CurrentTime` (реализовано):
- Правило 5 срабатывает только если `utcnow() ∈ [from, until]`; вне окна `satisfies` не выводится → мета-правило не выводит `is_available_for` → CWA блокирует.
- СВ-1 работает: пересечение несовместимых окон даёт неудовлетворимое условие, резонер обнаруживает.
- Цена: reasoning запускается чаще (окно «закрывается» во времени, прежний `is_available_for` устаревает без события прогресса). Решение 24.04 — фиксированный `cache_manager` TTL=3600 с + часовые границы датных политик (подробнее в §А5.5).

### А2.12. Диф с текущим кодом (вход в 3.6)

Текущая реализация размазана между `OntologyCore.run_reasoner`, `ProgressService.register_progress`, `ProgressService.invalidate_student_cache`, `ProgressService.get_student_access` и `utils/enrichers.py`. Расхождения:

| # | Расхождение | Категория | Приоритет |
|---|---|---|---|
| O1 | Нет отдельного компонента `ReasoningOrchestrator` — pipeline разорван между `ProgressService` и `OntologyCore`. FIX4 в Project Bible | Добавить | 🔴 |
| O2 | Pre-enrich стадия отсутствует: нет инжекции `CurrentTime`, нет пересчёта `AggregateFact` | Добавить | 🔴 (после T2, T13 в SAT_DATA_MODELS) |
| O3 | Очистка `is_available_for` перед reasoning не делается — после удаления/деактивации политики старые выводы остаются в ABox до следующего `onto.reload()` | Добавить | 🔴 (LIM6 incident risk) |
| O4 | `DateAccessFilter` реализует `date_restricted` на стадии чтения кэша вместо SWRL — см. §А2.11 | Переделать | 🔴 (после S4 + R2) |
| O5 | Таймаут reasoning (НФТ-3, 10 с) не выставлен — `sync_reasoner_pellet` вызывается без ограничения | Добавить | 🔴 (FIX1 в Project Bible) |
| O6 | Fallback на stale-cache при таймауте (ФТ-2.4) не реализован | Добавить | 🟡 |
| O7 | Обработка `OwlReadyInconsistentOntologyError` (НФТ-5 откат) отсутствует в `PolicyService.create_policy` и `update_policy` | Добавить | 🔴 |
| O8 | CWA-шаг реализован частично и не в `ReasoningOrchestrator`, а в `ProgressService.invalidate_student_cache` под условием «есть активные SWRL-политики и нет `is_available_for`» — корректно по смыслу, но разбросано; сложно тестировать изолированно | Переделать | 🟡 |
| O9 | Иерархическая блокировка выполняется в двух местах: `invalidate_student_cache` (при материализации) и `get_student_access` (`is_really_available` при чтении) — дублирование с риском рассинхрона | Упростить | 🟡 |
| O10 | Patch `subprocess.run` (`Jena → OWLAPI`) встроен прямо в `OntologyCore.run_reasoner` — не помечен как helper, R1 в SAT_DATA_MODELS | Переделать | 🟢 |
| O11 | Материализация кэша сейчас per-student (запускается по requests). Для UC-1/UC-2 (глобальные изменения) должна триггерить full materialize всех студентов, не `invalidate_all_access` пустой инвалидацией. Иначе первый UC-4 после изменения политики вызовет lazy re-reasoning с полной задержкой | Переделать | 🟡 (НФТ-1 miss risk) |
| O12 | Нет единого API `reason_and_materialize(student_id?)` — каждый UC вызывает свой набор: `save + run_reasoner + invalidate_all_access` или `save + run_reasoner + invalidate_student_cache` | Переделать | 🔴 (следует из O1) |

Пункты 🔴 O1, O3, O4, O5, O7, O12 блокируют корректность фазы 2; O2 блокирует реализацию шаблонов 5 и 10. Все — входят в раздел 3.6 Project Bible.

**Статус реализации (23.04).** Pipeline собран решениями 21.04 (Блок 1) и 23.04 (DI-рефакторинг). Закрыты:

- O1 — `ReasoningOrchestrator` выделен как отдельный компонент [services/reasoning/orchestrator.py](../code/backend/src/services/reasoning/orchestrator.py). В DSL — компонент Core Layer.
- O2 — pre-enrich реализован в [services/reasoning/_enricher.py](../code/backend/src/services/reasoning/_enricher.py): `CurrentTime` (R2) + `AggregateFact` per (student, policy) (R4).
- O3 — очистка `is_available_for` перед каждым прогоном — в `_enricher.py`, идемпотентно.
- O4 — `DateAccessFilter` удалён, дата через шаблон 5 + `CurrentTime` (FIX11 закрыт 21.04, см. §А2.11).
- O5 — таймаут через `sync_reasoner_pellet(..., graph_lang="SWRL")` обёрнут в `concurrent.futures` таймаут НФТ-3.
- O7 — `OwlReadyInconsistentOntologyError` ловится в `PolicyService.create_policy` → откат ABox-мутаций + HTTP 409 (FIX1).
- O12 — единый API `reason_and_materialize(student_id=None)` в `ReasoningOrchestrator`.
- O8/O9 — CWA-enforcement вынесен в [services/access/service.py](../code/backend/src/services/access/service.py) (FIX11 + решение 22.04), иерархическая блокировка — там же, дублирование `is_really_available` убрано.
- O10 — Java/Jena→OWLAPI-патч оформлен как `_patched_sync_reasoner` в Orchestrator.

Остаются:

- O6 — fallback на stale-cache при таймауте: можно считывать `access:{s}` с просроченным TTL и отмечать `stale=true`. Не реализовано, 🟡. Для демо-нагрузок таймауты не наблюдаются (p95 reasoning 1.3 с, НФТ-3 запас 8.7 с).
- O11 — материализация per-student вместо full-materialize при UC-1/UC-2. Сейчас `PolicyService._invalidate_all_access_caches` делает пустую инвалидацию → первый UC-4 ловит lazy re-reasoning. Не блокер демо, 🟡.

## А3. Восходящая агрегация завершённости (roll-up)

### А3.1. Назначение

Реализует ФТ-8 (иерархические агрегаты завершения): контейнер (`Module`, `Course`) считается завершённым студентом, когда все его обязательные потомки (`is_mandatory=true`) завершены. Точка вызова — UC-8 (каскадно из UC-5 при фиксации завершения элемента).

Почему алгоритм, а не SWRL-правило. Семантика «все обязательные потомки завершены» в логике — ∀-квантификация: `∀c. mandatory(c) ∧ parent(P, c) ⇒ completed(c, s)`. Эквивалентно отрицанию: «не существует обязательного потомка, который не завершён». Обе формы невыразимы в SWRL: NAF отсутствует (LIM3/LIM5), `owl:allValuesFrom` применим к свойствам, а не к состояниям конкретных ProgressRecord.

Термин «roll-up» — из SCORM 2004 (Sequencing and Navigation, раздел 3.1.2); русский эквивалент — «восходящая агрегация завершённости» (решение 16.04).

### А3.2. Семантика завершения контейнера

Определение. Для студента `s` и контейнера `C` с набором обязательных потомков `M(C) = { c ∈ children(C) : c.is_mandatory = true }`:

```
completed(C, s) ⇔ M(C) ≠ ∅ ∧ ∀c ∈ M(C). completed(c, s)
```

**Почему `M(C) ≠ ∅`.** Контейнер без обязательных потомков не может быть «завершён» — семантика пустого набора. Явное условие уточняет два случая:

- Методист оставил модуль пустым или сделал все потомки необязательными — политика требует ручного завершения, не автоматического;
- Структурная ошибка: модуль без детей — симптом импорта неполного курса, требует сигнала методисту, не тихой «автозавершённости».

Для атомарных элементов (`LearningActivity`) `M(e) = ∅`, и это правило не применяется — завершение приходит от события прогресса (UC-5).

### А3.3. Алгоритм

Восходящий обход от элемента, только что получившего статус `completed`:

```text
procedure rollup(ontology O, student s, just_completed: CourseStructure):
    parent ← find_parent(O, just_completed)
    if parent is None: return                             # корень достигнут

    # собрать обязательных потомков родителя
    mandatory ← [c for c ∈ children(parent) if c.is_mandatory = true]
    if mandatory = ∅: return                              # нет обязательных — не завершаем

    # проверка: все ли обязательные потомки завершены
    for c ∈ mandatory:
        if not is_completed(s, c): return                 # хотя бы один не завершён — стоп

    # все обязательные завершены → пометить родителя и рекурсивно вверх
    set_status(s, parent, COMPLETED)
    rollup(O, s, parent)


procedure is_completed(student s, element e) → bool:
    record ← find_progress_record(s, e)
    if record is None: return false
    return record.has_status = status_completed


procedure find_parent(ontology O, e: CourseStructure) → CourseStructure | None:
    # Обратное направление has_module / contains_activity.
    # Прямой обратный обход требует инверсных свойств (есть в TBox),
    # либо линейный поиск (текущая реализация).
    for p ∈ O.CourseStructure:
        if e ∈ p.has_module or e ∈ p.contains_activity:
            return p
    return None
```

**Рекурсия вверх, не вниз.** Roll-up запускается *после* того, как дочерний элемент получил `completed`. Значит: нужно проверить родителя этого элемента, и только его (не весь курс). Если родитель стал завершён — рекурсивно проверить *его* родителя. Обход идёт от дочернего к корню, длина ≤ depth(hierarchy) ≤ 3–4 в типичном курсе.

**Что проверяется — обязательные потомки, не все.** Roll-up заведомо не смотрит на факультативные элементы: студент мог их пропустить, это не должно блокировать завершение контейнера. Семантика обязательности определяется методистом через `is_mandatory`.

**Идемпотентность.** Если `parent` уже завершён для `s`, `set_status(s, parent, COMPLETED)` — no-op (статус не меняется, запись не создаётся заново). Повторный вызов roll-up от того же `just_completed` даст тот же результат. Это существенно: событие UC-5 может прилететь повторно из СДО (at-least-once delivery), алгоритм не должен ломаться.

### А3.4. Инварианты корректности

**Инвариант 1 (монотонность в сторону корня).** Если `completed(e, s) = true` в момент t и не произошло отката прогресса между t и t', то `completed(e, s) = true` в t'. Следствие: после успешного roll-up-а парент остаётся завершённым, пока не изменится `has_status` одного из его потомков.

Замечание: обратный откат — возможен в принципе (студент не сдал повторно, статус `completed → failed`). В текущей модели это *не* триггерит автоматическое «раззавершение» родителя — родитель остаётся `completed`. Это осознанное ограничение: roll-up работает только вверх, reverse-rollup — перспектива, не усиливает тезис о верификации, требует отдельного обсуждения (что делать с цепочкой статусов, уже зависящих от завершённого контейнера).

**Инвариант 2 (корректное поведение при отсутствии обязательных потомков).** Если `M(parent) = ∅`, алгоритм ничего не меняет. Это не «автозавершение по умолчанию», а явное «не применимо».

**Инвариант 3 (корректность при пустом курсе).** Если `parent = None` (достигнут корень курса, или `just_completed` — сам корень), rollup завершается без действий. Это не ошибка, а граничный случай — корень не имеет родителя.

**Инвариант 4 (единичное изменение за шаг).** Rollup пишет в ABox только `has_status(ProgressRecord(s, parent), completed)` — ровно одно свойство ровно одного индивида. Если parent ещё не имеет ProgressRecord — он создаётся. Никаких побочных эффектов на других студентов или других элементов.

### А3.5. Сложность

На один завершённый элемент:

- `find_parent`: O(|V_struct|) в текущей реализации (линейный поиск). С использованием инверсных OWL-свойств или предвычисленного индекса (словарь `child → parent`) — O(1).
- Сбор обязательных потомков: O(|children(parent)|).
- Проверка всех обязательных: O(|M(parent)|).
- Рекурсия вверх: до depth(hierarchy) шагов.

Итого: O(depth × |V_struct|) в текущей реализации, O(depth × max_siblings) с индексом. Для курса из НФТ-4 (500 элементов, depth ≤ 4) — миллисекунды в любом случае.

### А3.6. Связь с А2 (reasoning pipeline)

Roll-up изменяет ABox (устанавливает `has_status` у записи прогресса родителя). Это изменение — триггер для повторного запуска А2 (reasoning), если какая-либо политика зависит от `completion` на уровне контейнера (например, `completion_required` для Module приводит к открытию доступа к следующему Module).

Последовательность в UC-5:

```
1. UC-5 регистрирует событие (graded / completed / viewed).
2. set_status(student, element, status).
3. rollup(O, student, element) — потенциально обновляет статус контейнеров.
4. А2.reason_and_materialize(student) — единый прогон с учётом и прямого события, и rollup-обновлений.
```

Важно, что А2 запускается *после* А3, не до. Если запустить до — изменения А3 не попадут в этот прогон, кэш будет устаревший до следующего события.

### А3.7. Что не делает roll-up

- **Не пересматривает обязательность.** `is_mandatory` — статическое свойство, устанавливается методистом при создании элемента. Rollup не меняет его.
- **Не обрабатывает оценку/threshold контейнера.** Завершение Module = завершение всех его обязательных потомков, без дополнительных условий (оценка ≥ X по модулю). Расширенные условия — перспектива (§2.4 Project Bible, решение 16.04: «минимальная гибкость, не отдельная подсистема»).
- **Не распространяет завершение вниз.** Завершение контейнера *не* означает завершения всех его детей — наоборот, это следствие их завершения. «Сверху вниз» семантики нет.
- **Не вызывает А2.** Rollup — чистая ABox-операция. А2 вызывается отдельно, в `ProgressService.register_progress` после `rollup` (см. А3.6).

### А3.8. Граничные случаи

| Случай | Поведение |
|---|---|
| `just_completed` — корень курса | `find_parent = None`, алгоритм завершает без действий |
| `parent` не имеет ProgressRecord для студента | Создаётся новый ProgressRecord при `set_status` |
| Обязательный потомок не имеет ProgressRecord (студент его не трогал) | `is_completed` возвращает false → rollup останавливается |
| Обязательный потомок в статусе `failed`/`viewed` (не `completed`) | Аналогично: rollup останавливается |
| Потомки делятся между `has_module` и `contains_activity` | Оба учитываются (union) — обязательные во обоих отношениях |
| Методист помечает Module как `is_mandatory=true`, а все его activity как `is_mandatory=false` | Rollup для Course — рассматривает Module; Rollup для Module — не срабатывает (нет обязательных детей). Значит Module никогда не завершится автоматически, Course не завершится. Корректное поведение: если методист хочет автоматическое завершение Module — должен пометить хотя бы одну activity как обязательную |
| Одновременный (параллельный) rollup от двух событий | В текущей однопоточной модели FastAPI не возникает; при миграции на воркеры в фазе 2 — понадобится блокировка на уровне студента (TODO в диффе) |

### А3.9. Диф с текущим кодом (вход в 3.6)

Текущая реализация — `code/backend/src/services/rollup_service.py`, метод `RollupService.execute`. Расхождения:

| # | Расхождение | Категория | Приоритет |
|---|---|---|---|
| U1 | `is_required` — ожидается переименование в `is_mandatory` (T10 в SAT_DATA_MODELS §5.1). После переименования код `get_owl_prop(child, "is_required", True)` нужно поправить на `is_mandatory` | Переделать | 🟢 (после T10) |
| U2 | Дефолтное значение `is_required` — `True` (строка 34 `rollup_service.py`). Это означает: если свойство не задано в ABox — элемент считается обязательным. Проектное решение: явное `is_mandatory=true` при создании (решение 16.04). Дефолт должен быть тем, что сидит в `1_ontology_builder.py` | Проверить / выровнять | 🟡 |
| U3 | `find_parent` — линейный поиск по всем элементам. При НФТ-4 (500 элементов) укладывается в НФТ-1, но с ростом курса деградирует. Проектное решение — `parent_map: dict[child_id, parent_id]`, один раз построенный на прогон А2 (в `ProgressService` есть похожая логика в `get_student_access`) | Улучшить | 🟡 |
| U4 | Рекурсия реализована через `update_callback` (callback-injection) — связь с `ProgressService.update_progress`. Это работает, но кольцевая зависимость `ProgressService ↔ RollupService` затрудняет тестирование. Проектное решение — RollupService использует `OntologyCore.progress.set_status(...)` напрямую, без callback-injection | Упростить | 🟡 |
| U5 | `completed` включает `viewed` (строки 193–196 в `progress_service.py`) — корректное поведение, но делается в `ProgressService.update_progress`, не в roll-up. При прямом вызове `set_status(COMPLETED)` из roll-up нужно сохранить это поведение | Задокументировать / перенести | 🟡 |
| U6 | Roll-up вызывается только при `status = COMPLETED` (строка 204 в `progress_service.py`). Корректно для текущей модели. При расширении (rollup при failed — перспектива) — возможна регрессия | Задокументировать | 🟢 |
| U7 | Нет теста roll-up на многоуровневую иерархию (Course → Module → Submodule → Activity): завершение одной activity → завершение Submodule → завершение Module → завершение Course. Проект требует поддержки произвольной глубины (решение 16.04: правила назначаются на любой уровень) | Тест | 🔴 (FIX2) |
| U8 | `has_module` и `contains_activity` смешаны в одном `children`. После переименования `contains_element → contains_activity` (T10) и при появлении `Submodule`-уровня — нужно единый хелпер `children_of(e)`, а не конкатенация | Улучшить | 🟢 (после T10) |

Пункт 🔴 U7 — блокирует тестирование корректности иерархии из решения 16.04 и попадает в FIX2 (unit-тесты). Остальные — улучшения среднего/низкого приоритета.

**Статус реализации (22.04).** Закрыты:

- U7 — многоуровневая иерархия Course → Module → Activity покрыта тестами в [test_verification_service.py](../code/backend/src/tests/integration/test_verification_service.py) и scenario-прогонах через `happy_path`.
- U1/U8 — `is_required → is_mandatory` переименован в TBox (T10) и в `rollup_service.get_owl_prop(..., "is_mandatory")`.
- U2 — дефолт `is_mandatory=True` в коде оставлен по решению: отсутствие явного значения трактуется как «обязательный элемент» (консистентно с решением 16.04 о явном `is_mandatory` при создании, но защищает от legacy-ABox).
- U6 — задокументировано: rollup только при `status=COMPLETED`.

Остаются:

- U3 — `find_parent` линейным поиском: при курсе 500 элементов это O(n²), что упирается в НФТ-1 (50 мс) при массовом прогрессе. Для демо (4 студента × 21 запись) не проявляется, 🟡.
- U4 — callback-injection `update_callback` в `RollupService.execute` оставлен как есть: кольцевая зависимость с `ProgressService` мягкая (через `Protocol`), тестируется мок-колбеком. Альтернатива через `OntologyCore.progress.set_status` отложена, 🟡.
- U5 — `completed ⊇ viewed` сделано в `ProgressService.update_progress`, не в rollup. Задокументировано, 🟡.

Файл: [services/rollup_service.py](../code/backend/src/services/rollup_service.py).

## А4. Обнаружение недостижимых состояний

### А4.1. Назначение

Реализует верифицируемое свойство СВ-3 Reachability из §2.7.6 Project Bible: для каждого элемента курса должен существовать хотя бы один набор действий студента, при котором элемент становится доступным. Нарушение — «мёртвый» элемент, чей контент никогда не будет показан никакому студенту.

Точка вызова — UC-6 (полная верификация курса). В UC-3 проверка *не* запускается: для отдельной политики неуместна (смысл имеет только в контексте всего курса), и по стоимости дороже (полный перебор элементов).

### А4.2. Определение достижимости

Пусть `Σ` — пространство состояний студента (набор всех возможных комбинаций `ProgressRecord`, `has_competency`, `belongs_to_group`, учитывая `CurrentTime`).

```
reachable(e) ⇔ ∃σ ∈ Σ. is_available_for(e, σ) после А2.reason_and_materialize
```

Ограничения: `reachable` оценивается для «идеального» студента — то есть мы допускаем любой валидный `σ`. Недостижимость означает: *ни одного* такого `σ` не существует.

Причины недостижимости делятся на три класса:

**Класс 1 (структурная).** Граф зависимостей содержит путь, ведущий к противоречию на уровне структуры — например, цикл (⇒ СВ-2 уже ловит) или разрыв цепочки (parent unreachable → children unreachable).

**Класс 2 (семантика атомарной политики).** Отдельная политика содержит внутренне невыполнимое условие: `passing_threshold > 100`, `valid_from > valid_until`, `aggregate_required` с `passing_threshold > max_possible(fn, |elements|)` или пустым `aggregate_elements`.

**Класс 3 (совместимость политик).** Каждая политика сама по себе выполнима, но их конъюнкция (через `and_combination` или несколько политик на одном элементе с OR) — нет. Классический пример: `p1` требует `grade(X) ≥ 80`, `p2` требует `grade(X) ≤ 50`, обе обязательны.

Алгоритм строится из трёх проходов, покрывающих эти три класса, с разной стоимостью.

### А4.3. Проход 1: атомарная семантика (Класс 2)

Построчная проверка каждой активной политики. O(|P|).

```text
procedure check_atomic_satisfiability(p: AccessPolicy) → bool:
    match p.rule_type:
        "grade_required":
            return 0 ≤ p.passing_threshold ≤ 100                 # шкала предметной области
        "date_restricted":
            return p.valid_from ≤ p.valid_until                 # окно не пусто
        "aggregate_required":
            k ← |p.aggregate_elements|
            if k = 0: return false                               # нечего агрегировать
            match p.aggregate_function:
                "AVG":   max_val ← 100
                "SUM":   max_val ← 100 * k
                "COUNT": max_val ← k
            return 0 ≤ p.passing_threshold ≤ max_val
        "competency_required":
            # компетенция достижима, если её или потомка (по is_subcompetency_of) оценивает хотя бы один элемент
            return exists(a, sub : assesses(a, sub) and sub = p.targets_competency or sub is_subcompetency_of* p.targets_competency)
        "group_restricted":
            return p.restricted_to_group is not None             # в current model группы назначаются администратором — всегда «потенциально достижимы»
        "completion_required", "viewed_required":
            return p.targets_element is not None                 # достижимость target проверяется в проходе 2
        "and_combination", "or_combination":
            # композитные решаются в проходе 2 по рекурсии подполитик
            return true (deferred)
    return true
```

Политика, для которой этот проход возвращает `false`, — локально неудовлетворимая. Элемент, *все* политики которого локально неудовлетворимы, — гарантированно недостижим (Класс 2).

**Почему границы оценки 0–100 — часть модели, не жёстко хардкодить.** В §2.4 Project Bible зафиксировано: нормализация форматов (%, буквы, баллы) — задача API-адаптера; онтология работает с числом от 0 до 100. Значит проверка `0 ≤ th ≤ 100` — корректная верификация семантики, а не эвристика.

### А4.4. Проход 2: структурная достижимость с фиксированной точкой (Класс 1)

Граф зависимостей строится по тем же правилам, что в А1.4 (таблица по `rule_type`), но семантика дуг инвертируется: вместо «замыкания зависимостей» — «распространение достижимости».

Для каждого элемента `e` определяется `can_grant(e)` — булев предикат, равный `true`, если существует набор действий студента, при котором элемент становится доступным.

```text
procedure can_grant_element(e, visited: set, cache: dict) → bool:
    if e.id ∈ cache: return cache[e.id]
    if e.id ∈ visited:                                   # цикл (СВ-2 должна поймать раньше)
        cache[e.id] ← false
        return false
    visited ← visited ∪ {e.id}

    # иерархия: parent должен быть достижим
    parent ← find_parent(e)
    if parent is not None and not can_grant_element(parent, visited, cache):
        cache[e.id] ← false
        return false

    active ← active_policies_on(e)
    if active = ∅:
        cache[e.id] ← true                               # default-allow для свободного контента
        return true

    # хотя бы одна политика должна быть удовлетворимой
    for p ∈ active:
        if check_atomic_satisfiability(p) and can_grant_policy(p, visited, cache):
            cache[e.id] ← true
            return true

    cache[e.id] ← false
    return false


procedure can_grant_policy(p, visited, cache) → bool:
    match p.rule_type:
        "completion_required", "grade_required", "viewed_required":
            return can_grant_element(p.targets_element, visited, cache)

        "competency_required":
            c ← p.targets_competency
            # компетенция достижима, если существует достижимая activity, оценивающая c или его потомка
            return exists(a : (assesses(a, c) or assesses(a, sub) with sub is_subcompetency_of* c)
                              and can_grant_element(a, visited, cache))

        "aggregate_required":
            # каждый элемент набора должен быть достижим, иначе оценки не набрать
            return all(can_grant_element(ei, visited, cache) for ei in p.aggregate_elements)

        "group_restricted":
            return true   # группа — внешний фактор, всегда «потенциально достижима» в текущей модели

        "date_restricted":
            return true   # время зависит только от now(), не от действий студента

        "and_combination":
            return all(can_grant_policy(sub, visited, cache) for sub in p.has_subpolicy)

        "or_combination":
            return any(can_grant_policy(sub, visited, cache) for sub in p.has_subpolicy)


procedure find_all_unreachable(ontology O) → list[element_id]:
    cache ← {}
    unreachable ← []
    for e ∈ O.CourseStructure:
        if not can_grant_element(e, visited={}, cache):
            unreachable.append(e.id)
    return unreachable
```

**Ключевое отличие от simulate-with-Pellet.** Мы *не* строим синтетического студента и не запускаем reasoning для каждой гипотезы. Вместо этого — структурный анализ: для политики типа `grade_required` с threshold=75 и target=T достаточно знать, что T достижим. Мы не проверяем, что именно 75 баллов можно получить (это Pellet бы сделал через satisfiability model building, но это дорого).

Структурный проход корректно обрабатывает Классы 1 и 2. Класс 3 (совместимость политик) требует Pellet.

### А4.5. Проход 3: совместимость политик через Pellet (Класс 3)

Для элементов, помеченных достижимыми в Проходе 2, но с несколькими активными политиками или композитом `and_combination`, запускается проверка совместимости через Pellet.

```text
procedure check_joint_satisfiability(e, O) → (satisfiable: bool, witness?: model):
    # Построить синтетический ABox: студент σ*, которому нужно удовлетворить хотя бы одну политику e
    # (под CWA-слоем достаточно одной).
    for p ∈ active_policies_on(e):
        synthetic_abox ← copy(O.tbox) ∪ synthetic_prerequisites(σ*, p)
        try:
            Pellet.consistent(synthetic_abox)
            if Pellet.derives(synthetic_abox, is_available_for(e, σ*)):
                return (true, synthetic_abox)
        except InconsistentOntologyError:
            continue     # эта политика joint-unsatisfiable, попробуем следующую
    return (false, null)


procedure synthetic_prerequisites(σ*, p) → set[axiom]:
    # Генерирует минимальный набор ABox-аксиом, удовлетворяющих p
    match p.rule_type:
        "completion_required":
            return { ProgressRecord(pr), refers_to_student(pr, σ*), refers_to_element(pr, p.targets_element),
                     has_status(pr, status_completed) }
        "grade_required":
            return { ... + has_grade(pr, p.passing_threshold) }
        "viewed_required":
            return { ProgressRecord(pr), refers_to_student(pr, σ*), refers_to_element(pr, p.targets_element),
                     has_status(pr, status_viewed) }
        "competency_required":
            return { has_competency(σ*, p.targets_competency) }
        "group_restricted":
            return { belongs_to_group(σ*, p.restricted_to_group) }
        "date_restricted":
            # симулируется через enricher: current_time_ind устанавливается в (valid_from + valid_until) / 2
            return { CurrentTime(now_sim), has_value(now_sim, midpoint) }
        "and_combination":
            return union(synthetic_prerequisites(σ*, sub) for sub in p.has_subpolicy)
        "or_combination":
            return synthetic_prerequisites(σ*, first(p.has_subpolicy))  # любая подполитика
        "aggregate_required":
            # построить ProgressRecord по каждому e_i с grade, удовлетворяющим fn(grades) ≥ threshold
            grades ← solve_grades(p.aggregate_function, p.passing_threshold, |p.aggregate_elements|)
            return { ProgressRecord + has_grade(g_i) for (e_i, g_i) in zip(p.aggregate_elements, grades) }
```

**Почему Pellet, а не просто оценить AND/OR вручную.** Мы строим *одну* синтетическую ABox, в которой для политики `p` на элементе `e` заведомо выполнены все её условия. Если эта ABox противоречива — значит условия `p` несовместимы с TBox-аксиомами (функциональные свойства, дизъюнктность классов). Это и есть Класс 3.

Альтернатива — кодировать каждый вид конфликта (два `has_grade` для одного `ProgressRecord`, два `has_status` и т.д.) процедурно. Это дублирует Pellet и теряется выгода от формального представления. Ради цены 1 запуска Pellet на элемент — делегируем проверку.

**Стоимость.** Один Pellet-прогон на элемент. При 500 элементов × 1 с прогон = 500 с. Недопустимо. Оптимизации:

1. Запускать Проход 3 только для элементов с ≥ 2 активными политиками или с `and_combination`. Остальные не требуют joint-check (только один источник удовлетворения).
2. Кэшировать Pellet-прогон по подписи политик (если две активные политики одинаковы для 10 элементов — один прогон на все).
3. Инкрементальные reasoning (HermiT-инкрементальный, в Pellet через reload с патчем) — исследовательская задача на фазу 3.

Pragmatic: для фазы 2 — Проход 3 запускается только для элементов с `and_combination` или множественными активными политиками. Для остальных — Класс 3 потенциально пропускается (ложно-положительный результат СВ-3: элемент помечен достижимым, хотя фактически joint-unsatisfiable). Это осознанное ограничение, фиксируется в §3.4 Project Bible как метрика «recall СВ-3 при ограниченном Pellet-проходе».

**Статус реализации (24.04):** Проход 3 вынесен в перспективы диссертации. Реализованы Проходы 1 + 2 (`_atomic_unsatisfiable` + `_can_grant_element` рекурсивно с фиксированной точкой); они покрывают Классы 1 и 2, что достаточно для EXP1/EXP2 с текущим набором из 8 ground-truth сценариев. Класс 3 (joint-conflict через synthetic ABox + Pellet на изолированном World) требует ≈ 3–5 дней реализации и оформляется в главе 4 ПЗ как направление развития: «полная DL-верификация совместимости нескольких активных политик / композитов через Pellet на synthetic_prerequisites».

### А4.6. Сводный алгоритм А4

```text
procedure detect_unreachable(ontology O) → list[UnreachableReport]:
    reports ← []

    # Фаза 0: консистентность (СВ-1) — если нарушена, СВ-3 неприменима
    if not Pellet.consistent(O):
        return [{reason: "inconsistency", details: Pellet.explanation}]

    # Фаза 1 + 2: структурный фиксированная точка (Классы 1 + 2)
    unreachable_structural ← find_all_unreachable(O)
    for e_id in unreachable_structural:
        reports.append({element: e_id, class: "structural_or_atomic", details: explain_structural(e_id)})

    # Фаза 3: Pellet-joint (Класс 3), только для потенциально уязвимых элементов
    candidates ← {e : e ∈ O.CourseStructure, e.id ∉ unreachable_structural,
                       (|active_policies(e)| ≥ 2 or exists(p on e, p.rule_type = "and_combination"))}
    for e in candidates:
        (sat, witness) ← check_joint_satisfiability(e, O)
        if not sat:
            reports.append({element: e.id, class: "joint_conflict", details: conflicting_policies(e)})

    return reports
```

**Explanation generation.** Для каждого недостижимого элемента — понятное объяснение методисту. Для Класса 2 — «политика `p_X` требует `passing_threshold=105`, что вне диапазона оценок (0–100)». Для Класса 1 — «цепочка зависимостей: `e → parent(e) → политика на parent → target-элемент, недостижимый по причине ...»». Для Класса 3 — `Pellet.explanation` (какие аксиомы в конфликте).

### А4.7. Корректность

**Инвариант 1 (soundness Прохода 1+2).** Если алгоритм возвращает «элемент недостижим» в Проходах 1+2, — то элемент действительно недостижим в полном операционном смысле. Доказательство по индукции на структуре рекурсии `can_grant_element`: базовые случаи (нет политик → достижим; атомарная несовместимость → недостижим) корректны; индуктивный шаг (хотя бы одна политика грантируема И родитель достижим) — достаточное условие достижимости.

**Инвариант 2 (completeness Проходов 1+2 для Классов 1 и 2).** Если элемент недостижим по Классам 1 или 2, алгоритм это обнаружит. Это потому, что:

- Класс 2 ловится `check_atomic_satisfiability` на каждой политике;
- Класс 1 (структурный) ловится фиксированной точкой `can_grant_element`, которая не даёт `true`, если нет валидного пути.

**Инвариант 3 (incompleteness для Класса 3 без Прохода 3).** Только `check_joint_satisfiability` (Pellet) обнаруживает несовместимость нескольких политик. Без Прохода 3 алгоритм может ложно-положительно пометить элемент как достижимый.

**Инвариант 4 (soundness Прохода 3).** Pellet — формальный резонер, его `consistent` не даёт ложных отрицательных. Если Pellet возвращает «несовместимо» — элемент действительно joint-unreachable.

### А4.8. Сложность

**Проход 1+2.** Фиксированная точка на графе: O(|V| + |E| + Σ|policies|). С мемоизацией — каждый элемент анализируется один раз. Для размеров НФТ-4 — миллисекунды.

**Проход 3.** O(|candidates| × cost(Pellet)). При полной верификации (500 элементов, ≈ 20% кандидатов, 1 с прогон) — 100 секунд. Для UC-6 это приемлемо, но не для UC-3. Поэтому UC-3 использует только Проходы 1+2 (достаточно для большинства практических случаев), а Проход 3 запускается только в UC-6 / UC-10.

**Общая стоимость UC-6.** Consistency (СВ-1) — O(Pellet); Acyclicity (СВ-2) — О(|V|+|E|); Reachability (СВ-3) — Pass 1+2 линейно + Pass 3 100 с. Итого: ~100–200 с для курса из НФТ-4. Верификация — редкая операция (импорт курса, аудит), не частая — это приемлемо.

### А4.9. Связь с СВ-2 (Acyclicity)

СВ-2 и СВ-3 пересекаются: цикл в графе зависимостей делает цепочку элементов недостижимой. Но:

- СВ-2 обнаруживает цикл дешевле (DFS O(V+E)), сообщая методисту «найден цикл A → B → C → A».
- СВ-3 обнаруживает ту же цепочку через структурный проход, но сообщает «элементы A, B, C недостижимы» (без указания структуры цикла).

*Рекомендация порядка в UC-6:* СВ-1 → СВ-2 → СВ-3. СВ-2 даёт диагностически сильное сообщение; после исправления цикла — СВ-3 ловит оставшиеся проблемы. `can_grant_element` защищается от циклов (`if e.id ∈ visited: return false`), поэтому СВ-3 формально независима от СВ-2, но их последовательность в UC-6 оптимизирует UX.

### А4.10. Граничные случаи

| Случай | Поведение |
|---|---|
| Элемент — корень курса (`Course`), без политик и родителя | Достижим по default-allow (нет политик) |
| Элемент без родителя, но с неудовлетворимой политикой | Недостижим (Класс 2), отчёт с указанием политики |
| Элемент с one-of-many политик удовлетворимой, остальные неудовлетворимые | Достижим (CWA: одной политики достаточно). В отчёте — предупреждение «одна из политик неудовлетворима» (СВ-4 redundancy) |
| Композит `and_combination` со всеми удовлетворимыми подполитиками, но совместно неудовлетворимыми | Проход 2 пропускает; Проход 3 обнаруживает (Класс 3) |
| Элемент помечен достижимым Проходами 1+2, но Проход 3 отключён для него (не кандидат) | Ложно-положительный риск. Документируется в отчёте флагом `class3_skipped=true` |
| Элементы с циклом (СВ-2 нарушена) | `can_grant_element` возвращает false для всех узлов цикла. СВ-3 сработает, но объяснение будет «structural» (не «cycle»). Пользователь уже увидел СВ-2-сообщение раньше |

### А4.11. Диф с текущим кодом (вход в 3.6)

В текущем коде СВ-3 не реализовано вообще. Все пункты — **добавление нового функционала**.

| # | Пункт | Категория | Приоритет |
|---|---|---|---|
| N1 | Создать `VerificationService` (упоминается в C4 DSL, но нет в `code/backend/src/services/`) | Добавить | 🔴 (блокирует UC-6) |
| N2 | Реализовать `check_atomic_satisfiability` — чистая функция без Pellet, проверяет границы threshold, диапазоны дат, пустоту `aggregate_elements` | Добавить | 🔴 (после T13 в SAT_DATA_MODELS для aggregate_required) |
| N3 | Реализовать `can_grant_element` с мемоизацией | Добавить | 🔴 |
| N4 | Реализовать `check_joint_satisfiability` через Pellet с временными синтетическими ABox'ами (в памяти, без save) | Добавить | 🟡 (может быть отложено до фазы 3 EXP1) |
| N5 | Эндпоинт `GET /courses/{id}/verify` → `VerificationController.verify` → `VerificationService.full_verify(course_id)`, возвращает агрегированный отчёт по СВ-1/2/3 | Добавить | 🔴 (для UC-6) |
| N6 | Использовать тот же `build_dependency_graph` из А1 — не дублировать логику | Переиспользовать | 🟡 |
| N7 | Тесты: неудовлетворимая атомарная политика, недостижимая цепочка, joint-конфликт двух политик, ложно-положительный при отключении Прохода 3 | Тест | 🔴 (FIX2) |

Все 🔴 — часть FIX1 (consistency check) из §4.4, расширенного до полной СВ-1/2/3.

**Статус реализации (21.04).** Закрыты Блоком 2:

- N1 — [services/verification/service.py](../code/backend/src/services/verification/service.py) создан (подпакет `verification/` с DI-рефакторинга 23.04).
- N2 — `check_atomic_satisfiability` покрывает grade/date/aggregate-границы; кейсы в [test_verification_atomic.py](../code/backend/src/tests/unit/test_verification_atomic.py) (11 тестов).
- N3 — `can_grant_element` с мемоизацией через `functools.lru_cache` на parent-map.
- N5 — эндпоинт `GET /api/v1/verify/course/{id}` (+ `?full=true` для СВ-4/5) в [api/routers/verification.py](../code/backend/src/api/routers/verification.py).
- N6 — `build_dependency_graph` переиспользуется из `GraphValidator` (А1) без дублирования.
- N7 — unit + integration тесты: [test_verification_service.py](../code/backend/src/tests/integration/test_verification_service.py), [test_verification_negatives.py](../code/backend/src/tests/integration/test_verification_negatives.py), [test_verification_scenarios.py](../code/backend/src/tests/integration/test_verification_scenarios.py) — суммарно 14 тестов.

**В перспективы ВКР (решение 24.04, §4 ПЗ):**

- N4 — joint-satisfiability (Проход 3 А4.5) через synthetic_prerequisites + Pellet. На ground-truth сценариях EXP1 (8 scenarios + adversarial) синтаксические проходы 1+2 дают F1=1.0 по reachability — ресурс на Pellet-интеграцию Прохода 3 перенесён в направления развития. Оформляется в pz/05_conclusion.md как «полная DL-верификация Класса 3 через изолированный owlready2 World на synthetic_prerequisites».

## А5. Инвалидация кэша

### А5.1. Назначение

Алгоритм определяет, какие ключи Redis инвалидируются при каждом событии изменения состояния и когда кэш считается устаревшим без явного события. Покрывает НФТ-1 (50 мс при cache hit) и НФТ-6 (восстановление после сбоя). Работает в паре с А2: А5 — «когда чистить», А2 — «что кладём обратно».

### А5.2. Схема ключей

Один ключ на студента с агрегированной картой доступов:

```
KEY:   access:{student_id}
VALUE: {
  "updated_at": ISO-8601,
  "ontology_version": hash,     # хэш файла онтологии на момент материализации
  "elements": {
      "<element_id>": {
          "available_from": ISO-8601?,   # из DateRestrictionEnricher; в проектной
          "available_until": ISO-8601?,  # версии удаляется — см. А2.11
      },
      ...
  }
}
TTL: max(60s, min_distance_to_date_boundary(student)) — см. А5.5
```

**Почему один ключ, не два уровня (policy + access).** Обсуждалось в §А2.7: при типичных размерах курса (≤ 500 элементов) JSON-пейлоад на студента — 5–20 KB. Атомарная операция `DEL access:{s}` — O(1). Десериализация на клиенте — ~1 мс. Это укладывается в НФТ-1 без разбиения на несколько ключей.

**Почему добавляется `updated_at` и `ontology_version`.** `updated_at` нужен для fallback stale-cache при таймауте (§А2.8 — возвращаем `{"status": "stale_cache", "from_ts": ...}`). `ontology_version` — сигнальный маркер: если клиент увидит разные версии между своими запросами, он может запросить свежий пересчёт (для долгоживущих UI сессий симулятора UC-7).

Альтернативные ключи:

| Ключ | Назначение | Использование |
|---|---|---|
| `access:{student_id}` | Основная карта | ProgressService.get_student_access |
| `onto:version` | Хэш текущей онтологии | Используется для заполнения `ontology_version` в access-пейлоаде |
| `lock:reasoning` | Распределённая блокировка на время reasoning | Только в multi-worker режиме (фаза 2, после FIX10 Docker) — один воркер не запускает reasoning параллельно с другим |
| `verify:{course_id}` | Кэш отчёта верификации (UC-6) | TTL 1 час; инвалидируется любым изменением политик этого курса |

### А5.3. Таблица «событие → действие»

Охватывает все точки изменения состояния.

| Событие | Где триггерится | Инвалидация | Что пересчитывается немедленно | Обоснование |
|---|---|---|---|---|
| E1. Создана новая политика | PolicyService.create_policy | `DEL access:*` (все студенты) | `REBUILD` всех студентов | Изменилось поведение доступа для всех; откладывать на lazy → первый UC-4 каждого студента заплатит полной ценой reasoning (НФТ-2 ≈ 2 с), нарушая НФТ-1 |
| E2. Обновлена политика | PolicyService.update_policy | `DEL access:*` | `REBUILD` всех | Аналогично E1 |
| E3. Удалена политика | PolicyService.delete_policy | `DEL access:*` | `REBUILD` всех | То же |
| E4. Переключён `is_active` | PolicyService.toggle_policy | `DEL access:*` | `REBUILD` всех | Активация/деактивация = тот же эффект, что модификация |
| E5. Прогресс студента (viewed/completed/graded) | ProgressService.register_progress | `DEL access:{s}` | `REBUILD({s})` | Изменился ABox только одного студента; изменение не затрагивает других |
| E6. Rollup завершил контейнер | RollupService.execute → update_progress | без отдельной инвалидации | зонт E5 уже инвалидировал | Rollup — часть того же события E5, кэш уже помечен грязным |
| E7. Competency acquired | ProgressService (будущее расширение) | `DEL access:{s}` | `REBUILD({s})` | Затрагивает цепочку политик через competency_required и H-1 inheritance, но всё в рамках одного студента |
| E8. Присвоение в группу | PolicyService или AdminService | `DEL access:{s}` | `REBUILD({s})` | group_restricted зависит от belongs_to_group одного студента |
| E9. Изменение факта симулятора | SimulationService.update_test_student | `DEL access:{sim_s}` | `REBUILD({sim_s})` | Только симулируемый студент; продуктовые студенты не трогаются |
| E10. Импорт курса со структурой и правилами | IntegrationService.import_course | `DEL access:*` | `REBUILD` всех | UC-10 == массовое E1/E3; включает UC-6 верификацию до применения |
| E11. Пересечение datetime-границы date_restricted | TTL + lazy | автоматически через TTL | lazy при следующем UC-4 | Событие без триггера в системе; TTL обеспечивает корректность без дополнительной инфраструктуры |
| E12. Перезапуск сервиса | startup hook | `FLUSHDB` всего `access:*` (если `ontology_version` ≠ записанного в Redis) | lazy | НФТ-6 восстановление: онтология могла измениться между запусками; пустой кэш безопаснее устаревшего |

**Разделение «инвалидация» vs «ребилд».** Инвалидация — только `DEL key` (стоимость O(1) per key, O(N) для wildcard). Ребилд — тяжёлая операция: запуск А2 + материализация per student. Для E1–E4, E10 нужен ребилд всех студентов, это дорого (O(|students| × НФТ-2)). Решение:

- Немедленный ребилд «активных» студентов (те, кто заходил за последние ~15 минут — отслеживается отдельной структурой `recent:students`).
- Остальные — lazy, при следующем UC-4 (cache miss).

Это компромисс между полной актуальностью и фазой 2 усилий. В §3.6 Project Bible это отразится как задача «отслеживание активных студентов» (приоритет 🟡, не блокирует).

### А5.4. Lazy rebuild на cache miss

```text
procedure get_student_access_with_cache(student_id):
    cached ← redis.get(f"access:{student_id}")
    if cached is not None:
        if cached.ontology_version = current_ontology_version():
            return cached                                      # HIT
        else:
            # stale по версии онтологии → инвалидировать
            redis.del(f"access:{student_id}")
            cached ← None

    # MISS → полный прогон
    ReasoningOrchestrator.reason_and_materialize(student_id)
    return redis.get(f"access:{student_id}")
```

**Защита от stampede.** При массовом cache miss (например, после E10 импорта курса + перезапуска) несколько параллельных запросов могут одновременно триггерить `reason_and_materialize` для разных студентов. Это безопасно на уровне данных (Pellet глобальный, но материализация per student), но может создать скачок нагрузки. В фазе 2 добавляется simple lock per student: `lock:student:{s}` с TTL 30 с; параллельные запросы для того же `s` ждут освобождения.

### А5.5. TTL и датные границы

`date_restricted` — единственный тип, где кэш становится устаревшим *без события в системе*. Три варианта рассматривались; итоговое решение — (В), остальные зафиксированы для полноты.

**Решение реализации (24.04, вариант В — фиксированный TTL=3600 + часовой шаг дат.** `CacheManager.set_student_access` выставляет `ex=3600` на `access:{s}` (аналогично для `verify:*`). Одновременно `PolicyCreate.validate_by_rule_type` для `date_restricted` отклоняет `valid_from`/`valid_until` с ненулевыми минутами/секундами/микросекундами. Фронт синхронизирован: PrimeVue DatePicker с `stepMinute=60`, `manualInput` отключён на датах. Комбинация этих ограничений даёт ту же гарантию корректности, что и адаптивный TTL: между двумя последовательными датными границами проходит минимум 1 час; TTL 3600 с гарантирует cache miss раньше или ровно в момент следующей границы. Cron-воркер не нужен. Цена — ограничение UX (нельзя задать точное время до минуты), но для образовательных правил доступа «в понедельник с 10:00» — достаточная гранулярность.

Ниже — оригинальные варианты А и Б для полноты. В эксплуатацию пошёл (В).

**Короткий фиксированный TTL (простой).** TTL = 60 с. После минуты ключ исчезает, следующий UC-4 — cache miss → rebuild. Недостаток: ненужная работа для студентов, чьи политики не зависят от даты.

**Адаптивный TTL (оптимальный, не реализован).** При материализации вычисляется «ближайшая датная граница», влияющая на доступ этого студента:

```text
procedure compute_student_ttl(student) → seconds:
    now ← utcnow()
    boundaries ← []
    for policy p with is_active and rule_type="date_restricted":
        for t in [p.valid_from, p.valid_until]:
            if t > now:
                boundaries.append(t)
    if boundaries = ∅:
        return ∞                   # нет датных границ → TTL бесконечен (до следующего E1–E10)
    return max(60s, min(boundaries) - now + 5s)   # +5s запас на rounding
```

60 с — нижняя граница защищает от слишком частого повторного reasoning (если окно, например, открывается через 3 с — лучше закэшировать на 60 и пересчитать, чем дёргать reasoning каждые 3 с). 5 с запас — страховка на clock skew.

**Почему не использовать отдельный cron-воркер для инвалидации по датам.** Cron добавляет инфраструктурную сложность (планировщик, координация с Redis, обработка сбоев). Адаптивный TTL достигает того же эффекта стандартным механизмом Redis без лишних компонентов. Для ВКР это обосновано простотой.

### А5.6. Инварианты корректности

**Инвариант 1 (актуальность cache hit).** Если `get_student_access(s)` возвращает cached значение, то это значение — валидный результат А2 для `s` в момент его материализации (`cached.updated_at`). Данные между `updated_at` и текущим моментом могли измениться только через события E1–E10 (которые триггерят инвалидацию) или через прошествие времени (защищается TTL). Инвариант выполняется по конструкции таблицы А5.3 + адаптивного TTL.

**Инвариант 2 (безопасность default-deny при сбое Redis).** Если Redis недоступен:
- `get_student_access` → cache miss → прямая материализация без кэша (медленно, но корректно).
- `invalidate_all_access` → no-op с warning (OntologyCore логирует).
- Следствие: пользователи переживают сбой Redis (деградация производительности), но не получают неверных доступов.

**Инвариант 3 (идемпотентность инвалидации).** Повторный `DEL access:{s}` — no-op (ключа уже нет). Повторный `reason_and_materialize` возвращает тот же результат (А2.9 инвариант 1). Это важно: при at-least-once delivery событий UC-5 повтор не сломает систему.

**Инвариант 4 (отсутствие гонки читатель-писатель в single-worker).** FastAPI в single-worker режиме обрабатывает запросы последовательно на уровне event loop. Значит: `DEL` и последующий `REBUILD` атомарны относительно других запросов. В multi-worker (фаза 2) требуется `lock:reasoning` (§А5.2).

### А5.7. Сложность операций

| Операция | Сложность |
|---|---|
| `get access:{s}` | O(1) Redis + O(|elements|) JSON-парсинг ≈ 1–5 мс |
| `set access:{s}, map` | O(|elements|) сериализация + O(1) Redis ≈ 1–5 мс |
| `DEL access:{s}` | O(1) |
| `DEL access:*` (wildcard) | O(|students|) через KEYS+DEL; для 1000 студентов — ~10 мс |
| `REBUILD({s})` | О(стоимость А2) ≈ 2 с при cache miss; доминирует Pellet |
| `REBUILD(all)` | О(|students| × А2). Для 1000 студентов — 2000 с ≈ 33 минуты. Невыполнимо синхронно; делается lazy (лишь pre-warm для активных) |

### А5.8. Диф с текущим кодом (вход в 3.6)

Текущий `CacheService` реализует скелет, нужны расширения.

| # | Пункт | Категория | Приоритет |
|---|---|---|---|
| C1 | Добавить `updated_at` и `ontology_version` в payload | Добавить | 🟡 |
| C2 | Функция `current_ontology_version()` (хэш `edu_ontology_with_rules.owl`) + ключ `onto:version` | Добавить | 🟡 |
| C3 | Адаптивный TTL при `set_student_access` (вычисление `compute_student_ttl`) | Добавить | 🟡 |
| C4 | Проверка `ontology_version` при `get_student_access` — если не совпадает, del + miss | Добавить | 🟡 |
| C5 | Заменить `KEYS access:*` + `DELETE` на `SCAN` + `DELETE` для больших кэшей (KEYS блокирует Redis) | Улучшить | 🟢 (актуально при |students|>1000) |
| C6 | Выделить ребилд в отдельный entry-point `CacheManager.rebuild_for(student_id)` (в C4 DSL этот компонент называется `CacheManager`; сейчас логика в `ProgressService.invalidate_student_cache`, имя неточное) | Переделать | 🟡 |
| C7 | Нет lock per student (многопоточный miss) — при переходе на multiworker в фазе 2 (FIX10) будет race | Добавить | 🟡 (предусловие FIX10) |
| C8 | Нет отслеживания «активных студентов» для preemptive rebuild при E1–E4 | Добавить | 🟡 (опция оптимизации, не блокирует) |
| C9 | `verify:{course_id}` кэш отчёта верификации СВ-1/2/3 — ускоряет UC-6 при повторных запросах | Добавить | 🟢 (нужно после реализации VerificationService) |
| C10 | На startup-hook — проверка `onto:version` и условный `FLUSHDB access:*` | Добавить | 🟡 |

Пункты 🔴 отсутствуют — кэш в текущем коде работает, нужны улучшения актуальности и масштабируемости, но ни один пункт не блокирует фазу 2.

**Статус реализации (24.04, обновлён после закрытия TD10).** Решение 24.04 зафиксировало простую схему кэша: фиксированный TTL=3600 с + часовая гранулярность датных границ. Второй заход 24.04 поздно закрыл ontology_version и SCAN-инвалидацию — из 10 пунктов С1–С10 открытыми остаются три (C7/C8/C9), все низкой критичности.

| Пункт | Статус | Комментарий |
|---|---|---|
| C1 `updated_at` / `ontology_version` / `duration_ms` в payload | 🟡 частично | `ontology_version` добавлено в payload; `updated_at` и `duration_ms` пока не требуются (fallback stale-cache на таймаут — отдельная задача) |
| C2 `current_ontology_version()` + `onto:version` ключ | ✅ закрыт | `CacheManager.current_ontology_version()` — sha256 по mtime; `publish_ontology_version()` пишет `onto:version` |
| C3 Адаптивный TTL | ⏭ заменён | Решение 24.04: фиксированный TTL=3600 + часовые границы (см. §А5.5) |
| C4 Проверка `ontology_version` при GET | ✅ закрыт | `get_student_access`/`get_verification` проверяют `_version_matches`, stale payload удаляется и возвращается miss |
| C5 `SCAN` вместо `KEYS access:*` | ✅ закрыт | `_scan_and_delete(pattern)` через `scan_iter` + батчи DEL по 500 |
| C6 `CacheManager.rebuild_for(student_id)` | ✅ закрыт | `CacheService→CacheManager` переименован, ребилд через `AccessService.rebuild_student_access` |
| C7 Lock per student | 🟡 открыт | Для single-worker FastAPI гонок нет; при Docker multi-worker потребуется (TD12) |
| C8 `recent:students` для preemptive rebuild | 🟢 открыт | Оптимизация, не блокер (TD12) |
| C9 `verify:{course_id}` кэш | 🟡 открыт | verify сводится к 1–2 с, кэш не нужен при текущих объёмах (TD12) |
| C10 Startup-hook проверки `onto:version` | ✅ закрыт | FastAPI `@on_event("startup")` вызывает `ensure_version_consistency()` — при рассинхроне делает `SCAN`-инвалидацию `access:*` + `verify:*` и публикует текущий хэш |

Остающиеся C7/C8/C9 — TD12 в PROJECT_BIBLE §4.3: актуально при multi-worker/1000+ студентах.

---

## А6. Обнаружение избыточных и поглощающих правил (СВ-4, СВ-5)

### А6.1. Назначение

Покрывает верифицируемые свойства СВ-4 (Redundancy) и СВ-5 (Subsumption) из §2.7.6 PROJECT_BIBLE. Оба свойства переведены в приоритет **must** решением 21.04 — в текущей секции даётся единый алгоритм, различающий их по типу унификации при проверке.

Формальное определение (двухуровневая SWRL-семантика §2.1 SAT_DATA_MODELS):

> Политика `P1` **semantically subsumes** политику `P2`, если для любого студента `s` из `satisfies(s, P2)` логически следует `satisfies(s, P1)` — то есть условие `P2` сильнее (или равно) условию `P1`.

Из этого определения:
- **СВ-4 (Redundancy).** Если `P1` и `P2` защищают один и тот же элемент и `P1 subsumes P2`, то `P2` избыточна: удаление `P2` не меняет результат `is_available_for` для этого элемента (ступень 2 всё равно сработает через `P1` везде, где срабатывала через `P2`).
- **СВ-5 (Subsumption).** Если `P1` — общее правило «для всех группы A», `P2` — персональное «для студентки Ивановой» и Иванова ∈ A, то `P1 subsumes P2` с унификацией subject-переменной через конкретный индивид. Это Subject-level поглощение, с отдельным сообщением методисту.

Алгоритм А6 — один и тот же для обоих свойств; тип отчёта определяется тем, где при проверке произошла унификация (класс условия или конкретный индивид).

Покрывает ФТ-3.5 (в обновлённой формулировке §2.7.3 после решения 21.04).

### А6.2. Связь с А4.5

А6 переиспользует `synthetic_prerequisites(σ*, p)` из А4.5: тот же механизм «построить минимальный ABox, удовлетворяющий политику» лежит в основе и reachability (А4), и subsumption (А6). Различие — в вопросе, задаваемом Pellet-у:

- **А4.5:** «для одной политики `p` — найдётся ли ABox, в которой `is_available_for(e, σ*)` выводится?» (satisfiability).
- **А6:** «для пары политик `(P1, P2)` — в любой ли ABox, где выводится `satisfies(σ*, P2)`, также выводится `satisfies(σ*, P1)`?» (subsumption).

### А6.3. Область поиска

Проверка всех пар `(P1, P2)` из `O.AccessPolicy` была бы O(|P|²) с Pellet-прогоном на каждой паре — недопустимо. Область сужается двумя фильтрами:

**Фильтр 1: совпадение action.** Оба правила должны защищать один и тот же элемент (или — для СВ-5 — относиться к одному action-классу). Иначе одно не может поглощать другое: удаление одного не меняет доступ к элементу другого.

**Фильтр 2: совпадение или совместимость rule_type.** Пары политик с принципиально разными типами условий почти никогда не вступают в subsumption. Разрешаются сочетания:

| P1.rule_type | P2.rule_type | Возможно ли P1 subsumes P2 |
|---|---|---|
| одинаковые | одинаковые | да (проверяем) |
| `grade_required` | `grade_required` | да: R1 `≥ 60` поглощает R2 `≥ 80` |
| `group_restricted` | `completion_required` (персональный студент) | да (СВ-5 субъектный) |
| `or_combination` | любой | да (если P2 — одна из подполитик P1) |
| `and_combination` | любой | нет (AND — сильнее, не может поглощать одиночное) |
| `date_restricted` | любой другой тип | нет (ортогональная семантика) |

Таблица сужает O(|P|²) до O(|P|·k), где k — среднее число правил на элемент (типично 1–3). На курсе в 500 элементов и 100 правил — 200–300 пар, по 1 Pellet-прогону = единицы секунд, приемлемо для UC-6.

### А6.4. Псевдокод

```text
procedure detect_redundancy_and_subsumption(ontology O) → list[SubsumptionReport]:
    reports ← []
    candidates ← build_candidate_pairs(O)      # фильтры А6.3

    for (P1, P2) ∈ candidates:
        result ← check_subsumption(P1, P2, O)
        if result.subsumes:
            reports.append({
                type: classify(result),           # "redundancy" (СВ-4) | "subject_subsumption" (СВ-5)
                dominant: P1.id,
                dominated: P2.id,
                element: common_target(P1, P2),
                explanation: result.witness       # из synthetic ABox: какие факты унифицировались
            })
    return reports


procedure check_subsumption(P1, P2, O) → SubsumptionResult:
    # 1. Построить синтетический ABox, удовлетворяющий P2
    σ_abox ← copy(O.tbox) ∪ copy(O.disjointness_axioms) ∪ {Student(σ*)}
    σ_abox ← σ_abox ∪ synthetic_prerequisites(σ*, P2)       # переиспользует А4.5

    # 2. Проверить консистентность — иначе P2 сама неудовлетворима (перекрывается СВ-1)
    if not Pellet.consistent(σ_abox):
        return SubsumptionResult(subsumes=false, reason="P2_unsatisfiable")

    # 3. Запустить SWRL+reasoner на σ_abox
    Pellet.run(σ_abox)

    # 4. Проверить: выводится ли satisfies(σ*, P1) в результате?
    if σ_abox.derives(satisfies(σ*, P1)):
        # P1 тоже удовлетворена — значит, условие P2 влечёт условие P1
        witness ← extract_unification(σ_abox, P1, P2)       # что привело к выводу
        return SubsumptionResult(subsumes=true, witness=witness)
    else:
        return SubsumptionResult(subsumes=false, reason="independent_conditions")


procedure classify(result: SubsumptionResult) → string:
    # СВ-4 vs СВ-5 по типу унификации в witness
    if result.witness.has_named_subject_unification():
        # В P2 есть привязка к конкретному индивиду (например, belongs_to_group(σ*, ivanova))
        # или P2 — персональное правило на named Student, а P1 — групповое
        return "subject_subsumption"         # СВ-5
    else:
        return "redundancy"                  # СВ-4 (условия одинакового уровня общности)
```

### А6.5. Пример: СВ-4 Redundancy

Курс имеет две политики на `module_3`:
- `P1`: `grade_required(test_1, threshold=60)` — активна.
- `P2`: `grade_required(test_1, threshold=80)` — активна.

`synthetic_prerequisites(σ*, P2)` даёт ABox с `ProgressRecord(pr), refers_to_student(pr, σ*), refers_to_element(pr, test_1), has_grade(pr, 80)`.

Pellet применяет SWRL шаблон 2 (grade_required):
- Для `P2`: `80 ≥ 80` → `satisfies(σ*, P2)` ✓.
- Для `P1`: `80 ≥ 60` → `satisfies(σ*, P1)` ✓.

Вывод: `P1 subsumes P2`. Отчёт: «P2 избыточна — результат не меняется при её удалении, потому что P1 с порогом 60 всегда срабатывает, когда P1 с порогом 80». Методист видит: «упростить — удалить P2 или P1 (в зависимости от того, какая логика была задумана)».

### А6.6. Пример: СВ-5 Subject Subsumption

Курс имеет две политики на `advanced_module`:
- `P1`: `group_restricted(grp_advanced)` — «доступно всем в группе advanced».
- `P2`: `completion_required(prep_exam)` применяется персонально для студентки `ivanova` (через дополнительный фильтр в ABox — в текущей модели такого нет, но перспективно: `has_applies_to(P2, ivanova)`).

В общем случае СВ-5 требует расширения модели subject-фильтрами. Для MVP СВ-5 сужается до практического случая: `P1 group_restricted(G)` и `P2` — то же условие, но с пересечением `belongs_to_group` на меньшую группу `G' ⊂ G`. Поглощение СВ-5 тогда сводится к subclass-check между группами, разрешимому Pellet через `rdfs:subClassOf` на классах `GroupMember`.

В фазе 2 реализуется **MVP СВ-5**: `group_restricted` vs более узкое `group_restricted` с вложенной группой. Полноценный personal-level subject subsumption — в перспективу (требует расширения модели свойствами «applies_to»).

### А6.7. Сложность

**Pellet-прогон** `check_subsumption` для одной пары: O(время reasoning на ABox ≈ TBox + O(prerequisites)), ≈ 50–500 мс на пару.

**Число пар.** После фильтров А6.3 — O(k·|elements|) + O(g²) для группового MVP, где g — число групп. Типично 200–300 пар на курс из 500 элементов.

**Итого:** единицы секунд на курс, допустимо в UC-6 (верификация по запросу), не в UC-3 (per-rule валидация была бы слишком дорогой).

### А6.8. Оптимизации

1. **Кэш по подписи политик.** Пара `(P1_sig, P2_sig)` с одинаковыми типами и параметрами даёт одинаковый результат — кэшируется.
2. **Отсечение по включению интервалов.** Для пары `grade_required` с порогами `th1 ≤ th2` и одним target — это гарантированная subsumption без Pellet-прогона (синтаксическая проверка). Аналогично для date_restricted: окно `[a, b] ⊆ [c, d]` → политика с узким окном поглощается политикой с широким.
3. **Инкрементальный режим.** При создании новой политики в UC-2 проверяются только пары с новой политикой — O(k), единицы пар. Это допустимо в UC-3 (validate-before-save).

### А6.9. Корректность

**Soundness.** Если А6 возвращает «P1 subsumes P2», то для любого реального студента из `satisfies(s, P2)` следует `satisfies(s, P1)`. Доказательство: `synthetic_prerequisites(σ*, P2)` строит минимальный ABox, а любой реальный студент `s` с `satisfies(s, P2)` содержит в своём ABox как минимум те же факты (или более сильные). SWRL-выводы монотонны по фактам: если на меньшем наборе выведено `satisfies(σ*, P1)`, то на большем — тем более.

**Completeness (partial).** А6 не обнаруживает subsumption, требующий нетривиального DL-вывода через аксиомы TBox вне тривиальной цепочки (например, через глубокую транзитивность subcompetency и композицию с group_restricted). Это теоретическая неполнота; для practical сценариев ВКР-демонстрации не критично — EXP1 (Precision/Recall СВ-4/5) измеряется на наборе сценариев с known-ground-truth.

### А6.10. Диф с текущим кодом (вход в 3.6)

Компонент **не существует** в коде — требуется создание с нуля как часть `VerificationService` (Core Layer в C4 DSL).

| # | Пункт | Категория | Приоритет |
|---|---|---|---|
| SUB1 | Создать модуль `SubsumptionChecker` в `VerificationService` | Добавить | 🔴 (FIX13, FIX14 в §4.4 Project Bible) |
| SUB2 | Реализовать `build_candidate_pairs` с фильтрами А6.3 | Добавить | 🔴 |
| SUB3 | Реализовать `check_subsumption` поверх `synthetic_prerequisites` (переиспользование из А4.5) | Добавить | 🔴 |
| SUB4 | Реализовать классификатор redundancy vs subject_subsumption (по witness) | Добавить | 🔴 |
| SUB5 | Добавить синтаксические оптимизации (п. А6.8.2) для grade_required и date_restricted пар | Добавить | 🟡 (без них UC-6 работает, но медленнее) |
| SUB6 | Интеграция с отчётом UC-6: две секции отчёта — «избыточные правила» (СВ-4) и «поглощённые правила» (СВ-5) | Добавить | 🔴 (ФТ-3.4 — структурированный отчёт) |
| SUB7 | Эндпоинт `POST /verify/subsumption` или объединить в существующий `/verify` как часть полного отчёта | Добавить | 🟡 |
| SUB8 | Тесты: набор сценариев с known-ground-truth для EXP1 (Precision/Recall СВ-4/5) | Добавить | 🔴 (метрика §3.4) |
| SUB9 | UI: раздел «Избыточные и поглощённые правила» в отчёте верификации (фронтенд-минимум §3.5.5) | Добавить | 🟡 |

Все 🔴 — часть фазы 2, триггерятся FIX13 (СВ-4) и FIX14 (СВ-5).

**Статус реализации (24.04).** Реализован `SubsumptionChecker` на синтаксических эвристиках: равенство target + порогов для `grade_required`, вложенность окон для `date_restricted`, subset-отношение для `group_restricted`, поиск эквивалентной подполитики для AND-композита. SUB5/SUB7/SUB9 закрыты: синтаксические оптимизации применяются по умолчанию (п. SUB5), эндпоинт объединён с `GET /verify/course/{id}?full=true` (SUB7), UI-раздел «Избыточные и поглощённые правила» есть в `VerificationReport.vue` (SUB9). Не реализован **полный SUB3** — DL-subsumption через `synthetic_prerequisites` + Pellet на парах композит↔композит и атом↔композит с нетривиальной TBox-цепочкой. Это означает partial-completeness: пары, требующие reasoning через аксиомы TBox вне синтаксического равенства, пропускаются. Для EXP1 это приемлемо — ground-truth сценарии (`bad_sv4_redundant`, `bad_sv5_subject`) спроектированы под ловимые синтаксикой случаи. Полная DL-subsumption выносится в главу 4 ПЗ (перспективы): «DL-резонинг-backed subsumption для композитных политик, с переиспользованием `synthetic_prerequisites` из алгоритма А4 и изолированным owlready2 World на каждую проверяемую пару».
