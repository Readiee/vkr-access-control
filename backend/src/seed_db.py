"""
Идемпотентный скрипт сидирования данных в онтологию.
Полностью перезаписывает ABox, сохраняя TBox (свойства и классы).
"""
import random
from owlready2 import get_ontology, destroy_entity

ONTO_PATH = "data/edu_ontology_with_rules.owl"


def seed_data():
    onto = get_ontology(ONTO_PATH).load()

    # --- Очистка ABox (удаляем все инстансы, кроме статусов) -----------------------
    KEEP_NAMES = {"status_passed", "status_viewed", "status_completed", "status_failed"}
    individuals = list(onto.individuals())
    for ind in individuals:
        if ind.name not in KEEP_NAMES:
            destroy_entity(ind)

    # --- Сидирование чистого ABox ---------------------------------------------------
    with onto:
        random.seed(42)  # фиксируем seed для воспроизводимости

        # 1. Компетенции
        comp_it = onto.Competency("comp_it", label=["IT Общие знания"])
        comp_python = onto.Competency("comp_python", label=["Python Core"],
                                      is_subcompetency_of=[comp_it])
        comp_ds = onto.Competency("comp_data_science", label=["Data Science"],
                                  is_subcompetency_of=[comp_it])
        all_comps = [comp_it, comp_python, comp_ds]

        # 2. Курс
        course = onto.Course("course_fullstack_python",
                             label=["Fullstack разработка на Python 2026"])
        course.is_required = [True]
        course.order_index = [1]

        # 3. Модули и элементы
        module_titles = [
            "Введение в синтаксис", "ООП и паттерны", "Работа с базами данных",
            "Веб-фреймворки (FastAPI)", "Асинхронность в Python", "Тестирование и CI/CD"
        ]

        course_modules = []
        for i, m_title in enumerate(module_titles, 1):
            module = onto.Module(f"module_{i}", label=[f"Модуль {i}: {m_title}"])
            module.is_required = [True]
            module.order_index = [i]
            elements = []

            for j in range(1, 6):
                e_type = "lecture" if j < 4 else "test"
                e_id = f"m{i}_element_{j}"
                e_label = f"{'Лекция' if e_type == 'lecture' else 'Итоговый тест'} #{j} [Модуль {i}]"

                elem_cls = onto.Lecture if e_type == "lecture" else onto.Test
                element = elem_cls(e_id, label=[e_label])
                element.is_required = [True]
                element.order_index = [j]

                # Случайные политики (40%)
                if random.random() < 0.4:
                    policy = onto.AccessPolicy(f"policy_for_{e_id}")
                    r_type = random.choice(["viewed_required", "grade_required", "competency_required"])
                    policy.rule_type = [r_type]
                    if r_type == "competency_required":
                        policy.targets_competency = [random.choice(all_comps)]
                    elif r_type == "grade_required":
                        policy.passing_threshold = [random.randint(60, 90)]
                    element.has_access_policy = [policy]

                elements.append(element)

            module.contains_element = elements
            course_modules.append(module)

        course.has_module = course_modules

    onto.save(file=ONTO_PATH)
    print(f"✅ Готово! 1 Курс, {len(module_titles)} Модулей, {len(module_titles) * 5} Элементов.")


if __name__ == "__main__":
    seed_data()