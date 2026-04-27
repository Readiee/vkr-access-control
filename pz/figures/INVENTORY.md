# Инвентарь рисунков ВКР

> Список всех ожидаемых рисунков с финальными именами и статусами. Создан 25.04 до старта письма (решение 25.04 §7 PROJECT_BIBLE), обновляется по мере готовности каждого артефакта.
>
> **Имена** — по правилу из [pz/figures/README.md](README.md): `<глава>-<номер>-<имя>.<ext>`. Имена фиксируются заранее: при письме главы ссылка вписывается один раз, при подготовке картинки имя уже известно.
>
> **Нумерация рисунков в ПЗ** — сквозная в пределах главы (Рисунок 2.3 = третий рисунок второй главы), по [SAT_PZ_REQUIREMENTS.md §8](../docs/SAT_PZ_REQUIREMENTS.md). Последовательность ниже соответствует первому появлению рисунка в тексте главы; при перестановке рисунков имена тоже меняются (одной операцией ru-rename).
>
> **Статусы:**
>
> - ✅ готово — файл лежит в `pz/figures/` или в указанном источнике, готов к вставке в DOCX
> - 🟡 сгенерировать из DSL — есть исходник Mermaid/PlantUML/Structurizr, нужно прогнать render-pipeline
> - 🟠 создать DSL и отрисовать вручную — финальная версия в draw.io по правилу §3.5.2 PROJECT_BIBLE (рендер DSL служит референсом для ручной отрисовки)
> - 🔴 скриншот или зависит от внешнего ресурса — UI приложения, terminal output, требует запущенной системы или PoC
> - 📝 не картинка — содержимое лучше представить как code-блок, таблицу или формулу в теле текста

---

## Глава 1. Анализ предметной области

| № | Файл | Что показывает | Статус | Источник или пометка |
|---|---|---|---|---|
| 1.1 | 1-1-activity-as-is.png | Процесс управления доступом к контенту в существующих СДО (as-is) | 🟡 | [diagrams/uml/activity-as-is.mmd](../../diagrams/uml/activity-as-is.mmd); render через mermaid-cli Docker |
| 1.2 | 1-2-use-cases.png | Диаграмма вариантов использования (UC-1..UC-10) | 🟠 | [diagrams/uml/use-cases.puml](../../diagrams/uml/use-cases.puml) → финал draw.io; «паучья сеть» при автолейауте, нужна ручная отделка (решение 18.04 §7) |

---

## Глава 2. Проектирование системы

| № | Файл | Что показывает | Статус | Источник или пометка |
|---|---|---|---|---|
| 2.1 | 2-1-c4-context.png | Контекст системы (C4 System Context) | ✅ | [diagrams/c4/exports/png/SystemContext.png](../../diagrams/c4/exports/png/) |
| 2.2 | 2-2-c4-container.png | Декомпозиция на контейнеры (C4 Container, 4 контейнера) | ✅ | [diagrams/c4/exports/png/Containers.png](../../diagrams/c4/exports/png/) |
| 2.3 | 2-3-c4-component-overview.png | Все 16 компонентов в одном виде | ✅ | [diagrams/c4/exports/png/Overview.png](../../diagrams/c4/exports/png/) |
| 2.4 | 2-4-c4-component-policy-flow.png | Сфокусированный вид PolicyFlow (UC-1/2/3) | ✅ | [diagrams/c4/exports/png/PolicyFlow.png](../../diagrams/c4/exports/png/) |
| 2.5 | 2-5-c4-component-access.png | Сфокусированный вид AccessEvaluation (UC-4/7/9) | ✅ | [diagrams/c4/exports/png/AccessEvaluation.png](../../diagrams/c4/exports/png/) |
| 2.6 | 2-6-c4-component-verification.png | Сфокусированный вид Verification (UC-6) | ✅ | [diagrams/c4/exports/png/Verification.png](../../diagrams/c4/exports/png/) |
| 2.7 | 2-7-c4-component-integration.png | Сфокусированный вид IntegrationRollup (UC-5/8/10) | ✅ | [diagrams/c4/exports/png/IntegrationRollup.png](../../diagrams/c4/exports/png/) |
| 2.8 | 2-8-activity-to-be.png | Целевой процесс управления доступом (to-be) | 🟡 | [diagrams/uml/activity-to-be.mmd](../../diagrams/uml/activity-to-be.mmd) |
| 2.9 | 2-9-deployment.png | Модель развёртывания | 🟡 | [diagrams/uml/deployment.puml](../../diagrams/uml/deployment.puml) |
| 2.10 | 2-10-tbox-class-diagram.png | Структура терминологического компонента онтологии | 🟡 | [diagrams/uml/class-tbox.puml](../../diagrams/uml/class-tbox.puml); 18 классов + ключевые свойства |
| 2.11 | 2-11-split-node-example.png | Трансформация графа зависимостей в split-node для алгоритма обнаружения циклов | 🟡 | [diagrams/uml/split-node-example.mmd](../../diagrams/uml/split-node-example.mmd) (DSL создан 25.04, рендерить через mermaid-cli; финал в draw.io опционально) |
| 2.12 | 2-12-sequence-reasoning-pipeline.png | Конвейер логического вывода (4 стадии) | 🟡 | [diagrams/uml/sequence-reasoning-pipeline.mmd](../../diagrams/uml/sequence-reasoning-pipeline.mmd) |
| 2.13 | 2-13-rollup-tree-cascade.png | Дерево с каскадом завершения (восходящая агрегация) | 🟡 | [diagrams/uml/rollup-tree-cascade.mmd](../../diagrams/uml/rollup-tree-cascade.mmd) (DSL создан 25.04 на основе happy_path для student_ivanov, рендерить через mermaid-cli; финал в draw.io опционально) |
| 2.14 | 2-14-sequence-policy-create.png | Создание политики с валидацией (UC-1/3) | 🟡 | [diagrams/uml/sequence-policy-create.mmd](../../diagrams/uml/sequence-policy-create.mmd) |
| 2.15 | 2-15-sequence-access-check.png | Запрос доступа с кэшем (UC-4) | 🟡 | [diagrams/uml/sequence-access-check.mmd](../../diagrams/uml/sequence-access-check.mmd) |
| 2.16 | 2-16-sequence-progress-rollup.png | Агрегация завершённости (UC-5/8) | 🟡 | [diagrams/uml/sequence-progress-rollup.mmd](../../diagrams/uml/sequence-progress-rollup.mmd) |
| 2.17 | 2-17-wireframe-summary.png | Сводный wireframe пяти экранов UI | 🟠 | создать draw.io на основе §3.5.5 PROJECT_BIBLE; UI не научный вклад, делается одним обзорным рисунком |

> **Не рисунками** идут таблицы и формальные записи в теле подразделов: матрица F1–F20 и таблица LIM1–LIM7 (§1.6), таблица трёх проходов А4 (§2.4.4), таблица «событие → инвалидация» А5 (§2.4.5), пример пары политик и таблица проходов А6 (§2.4.6), маппинг онтологии на 5 СДО (§2.7.3 + Приложение Ж), компактная формальная запись Прохода 3 А4 в теле 2.4.4 (5–10 строк алгоритмической нотации).

---

## Глава 3. Реализация программного комплекса

| № | Файл | Что показывает | Статус | Источник или пометка |
|---|---|---|---|---|
| 3.1 | 3-1-class-backend.png | Класс-диаграмма серверной части (3 слоя × 16 компонентов) | 🟡 | [diagrams/uml/class-backend.puml](../../diagrams/uml/class-backend.puml) |
| 3.2 | 3-2-moodle-course-tree.png | Дерево демонстрационного курса в Moodle UI | 🔴 | скриншот после PoC; курс happy_path в bitnami/moodle |
| 3.3 | — | JSON ответа `core_course_get_contents` Web Services | 📝 | code-блок в теле §3.4.2 (не рисунок); подходит fenced JSON |
| 3.4 | 3-4-moodle-import-result.png | Результат импорта в OWL после прогона `MoodleCourseImporter.import_course` | 🔴 | скриншот / dump индивидов через owlready2 |
| 3.5 | — | curl-запрос `GET /api/v1/access/student/.../element/...` с verdict | 📝 | code-блок в теле §3.4.2 |
| 3.6 | 3-6-sequence-moodle-event.png | Sequence: событие Moodle → webhook → ABox update | 🟡 | [diagrams/uml/sequence-moodle-event-import.mmd](../../diagrams/uml/sequence-moodle-event-import.mmd) |
| 3.7 | 3-7-sequence-moodle-availability.png | Sequence: Moodle render → availability plugin → REST | 🟡 | [diagrams/uml/sequence-moodle-availability-check.mmd](../../diagrams/uml/sequence-moodle-availability-check.mmd) |
| 3.8 | 3-8-frontend-policy-editor.png | Редактор правил (PolicyRuleCard.vue) | 🔴 | скриншот UI; одна форма для одного из 9 типов правил, например AND-композит |
| 3.9 | 3-9-frontend-verification-report.png | Отчёт верификации курса (VerificationReport.vue) | 🔴 | скриншот UI; аккордеон по 3 свойствам с найденными нарушениями (после решения 25.04 §7) |
| 3.10 | 3-10-frontend-blocking-explanation.png | Модальное объяснение блокировки (BlockingExplanation.vue) | 🔴 | скриншот UI; UC-9 с justification tree |

> **Листинги PHP** для §3.4.3 и §3.4.4 идут code-блоками в теле подразделов (~30 строк каждый), не рисунками. Полная спецификация — `code/integrations/moodle/php/event_observer.php` и `availability_condition.php`.

---

## Глава 4. Экспериментальная оценка

| № | Файл | Что показывает | Статус | Источник или пометка |
|---|---|---|---|---|
| 4.1 | 4-1-exp1-confusion-matrix.png | Confusion matrix per-property для Эксперимента 1 (72 сценария × 3 свойства, после решения 25.04 §7) | 🟠 | пересобрать столбчатую диаграмму без SV4/SV5 строк из [figures/exp1/combined_day2.csv](exp1/combined_day2.csv) |
| 4.2 | 4-2-exp2-accuracy-by-type.png | Accuracy по 9 типам правил для Эксперимента 2 | ✅ | [figures/exp3/accuracy_by_type.png](exp3/accuracy_by_type.png) — переименовать-скопировать |
| 4.3 | 4-3-exp3-scalability.png | Зависимость времени верификации от числа политик (10/50/100/500) | ✅ | [figures/exp4/scalability_exp4.png](exp4/scalability_exp4.png) |
| 4.4 | 4-4-exp3-latency.png | Latency UC-4 cache hit / miss / cold start | ✅ | [figures/exp4/latency_exp4.png](exp4/latency_exp4.png) |

> **Confusion matrix** в §4.2 можно дать одной столбчатой диаграммой (TP/TN/FP/FN по 3 свойствам), либо таблицей. Если таблицей — рисунок 4.1 не нужен. Решается при письме главы 4.

---

## Приложения

| № | Файл | Что показывает | Статус | Источник или пометка |
|---|---|---|---|---|
| Б-1 | Б-1-tbox-overview.png | Полная схема онтологии в большом формате | 🟡 | тот же исходник, что 2.10, но landscape A3 без crop; для Приложения Б |

> **Приложения В, Г, Д, Е, Ж** идут как тексты, листинги, таблицы — не рисунки.

---

## Резюме по статусам

| Статус | Количество | Пояснение |
|---|---|---|
| ✅ Готово | 11 | Существующие PNG из `diagrams/c4/exports/` и `pz/figures/exp*/` |
| 🟡 Сгенерировать из DSL | 13 | Mermaid / PlantUML / Structurizr — есть исходники, нужен render |
| 🟠 Создать DSL и отрисовать вручную | 5 | draw.io по референсу из render-pipeline |
| 🔴 Скриншот после реализации | 7 | UI приложения (4) + Moodle PoC (3) |
| 📝 Не рисунок (code-блок в тексте) | 2 | JSON Web Services, curl-output |
| **Итого активных рисунков** | **36** | в ПЗ + 1 в приложениях |

---

## Точки внимания при работе

1. **Картинки 🟡 пакетом** удобнее рендерить за один проход через Docker pipeline после готовности всех глав, чтобы не настраивать инструмент много раз.
2. **🟠 рисунки** требуют ручной работы в draw.io. План: создаю DSL и render как референс → пользователь делает финальную draw.io. Закладываем под это отдельные сессии после готовности глав 2 и 3.
3. **🔴 скриншоты UI и Moodle** делаются после PoC адаптера (между главой 1 и главой 3, см. решение 25.04 §7). Я пишу инструкцию (что захватить, с какими данными, при каком увеличении), пользователь снимает.
4. **Сквозной демо-курс happy_path** даёт «вертикаль» через все рисунки (решение 24.04 §7): тот же курс импортируется в Moodle (3.2), та же ABox показывается в OWL (3.4), тот же curl возвращает verdict (3.5), тот же rollup-cascade на схеме (2.13). Один пример экономит когнитивную нагрузку.
5. **Финальные имена файлов** уже зафиксированы — при письме глав ссылаюсь на них. Если рисунок ещё не готов, в тексте идёт пометка `[РИСУНОК 2.11 — split-node, статус: 🟠]`, в финальной сборке заменится на номер «Рисунок 2.11».

---

*Версия: 1.0 (25.04). Обновлять при добавлении/удалении/перенумерации рисунков.*
