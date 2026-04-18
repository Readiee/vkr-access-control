from owlready2 import get_ontology, sync_reasoner_pellet

# 1. Загружаем онтологию
onto = get_ontology("onto/ontologies/edu_ontology_with_rules.owl").load()

# 2. Создаем дерево компетенций
comp_it = onto.Competency("comp_it")
comp_programming = onto.Competency("comp_programming")
comp_python = onto.Competency("comp_python")

# Выстраиваем иерархию (снизу вверх)
comp_python.is_subcompetency_of.append(comp_programming)
comp_programming.is_subcompetency_of.append(comp_it)

# 3. Создаем курс, который требует ШИРОКУЮ компетенцию (Programming)
module_ml = onto.Module("module_machine_learning")
policy = onto.AccessPolicy("policy_req_programming")
policy.rule_type = ["competency_required"]
policy.targets_competency = [comp_programming]
module_ml.has_access_policy.append(policy)

# 4. Создаем студента, у которого есть только УЗКАЯ компетенция (Python)
student_hacker = onto.Student("student_hacker")
student_hacker.has_competency.append(comp_python)

print(f"До ризонинга. Доступен ли модуль студенту? {student_hacker in module_ml.is_available_for}")

# 5. МАГИЯ: Запускаем Pellet
sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

print(f"После ризонинга. Доступен ли модуль студенту? {student_hacker in module_ml.is_available_for}")
print("Успех! Ризонер сам понял, что Python - это Программирование!")
