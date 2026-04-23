import uuid
from typing import Any, List

class StudentRepository:
    def __init__(self, onto):
        self.onto = onto

    def get_or_create(self, student_id: str):
        """Находит студента по ID или создает нового.

        Sandbox-студенты живут под id вроде `sandbox_new` (класс SandboxStudent
        наследует Student, id без префикса `student_`). Сперва ищем индивид по
        оригинальному id — иначе создастся второй Student с префиксом, прогресс
        и вывод is_available_for разъедутся на разных индивидов с одним именем.
        """
        direct = self.onto.search_one(iri=f"*{student_id}")
        if direct is not None:
            return direct
        node_id = student_id if student_id.startswith("student_") else f"student_{student_id}"
        student = self.onto.search_one(iri=f"*{node_id}")
        if not student:
            student = self.onto.Student(node_id)
        return student

class CourseRepository:
    def __init__(self, onto):
        self.onto = onto

    def get_all_elements(self):
        """Возвращает все элементы структуры курса."""
        return self.onto.CourseStructure.instances()

    def find_by_id(self, element_id: str):
        """Находит элемент структуры курса по ID."""
        return self.onto.search_one(iri=f"*{element_id}")

    def get_or_create_element(self, element_id: str, element_class_name: str):
        """Безопасное создание элементов курса (Module, Lecture и т.д.)"""
        element = self.find_by_id(element_id)
        if not element:
            # Получаем класс из онтологии по имени
            element_class = getattr(self.onto, element_class_name)
            element = element_class(element_id)
        return element

    def get_all_competencies(self):
        """Возвращает все компетенции."""
        return self.onto.Competency.instances() if hasattr(self.onto, "Competency") else []

class ProgressRepository:
    def __init__(self, onto):
        self.onto = onto

    def find_record(self, student, element):
        """Находит запись о прогрессе для конкретного студента и элемента."""
        return self.onto.search_one(type=self.onto.ProgressRecord, refers_to_student=student, refers_to_element=element)

    def find_all_for_student(self, student) -> List[Any]:
        """Находит все записи о прогрессе для студента."""
        return list(self.onto.search(type=self.onto.ProgressRecord, refers_to_student=student))

    def create_record(self, student, element):
        """Создает новую запись о прогрессе."""
        pr_id = f"pr_{uuid.uuid4().hex[:8]}"
        record = self.onto.ProgressRecord(pr_id)
        record.refers_to_student = [student]
        record.refers_to_element = [element]
        if record not in getattr(student, "has_progress_record", []):
            student.has_progress_record.append(record)
        return record

    def delete_record(self, student, record):
        """Удаляет запись о прогрессе."""
        if record:
            if hasattr(student, "has_progress_record") and record in student.has_progress_record:
                student.has_progress_record.remove(record)
            from owlready2 import destroy_entity
            destroy_entity(record)

    def get_owl_status(self, status_value: str):
        """Получает OWL-объект статуса по строковому значению."""
        if status_value == "completed": return getattr(self.onto, "status_completed", None)
        if status_value == "failed": return getattr(self.onto, "status_failed", None)
        if status_value == "viewed": return getattr(self.onto, "status_viewed", None)
        return None

class PolicyRepository:
    def __init__(self, onto):
        self.onto = onto

    def find_by_id(self, policy_id: str):
        """Находит политику по ID."""
        return self.onto.search_one(iri=f"*{policy_id}")

    def find_by_source_element(self, policy_node):
        """Находит элементы, которые ссылаются на данную политику."""
        return self.onto.search(has_access_policy=policy_node)

    def create_or_update(self, policy_id: str):
        """Создает или обновляет политику."""
        policy = self.find_by_id(policy_id)
        if not policy:
            policy = self.onto.AccessPolicy(policy_id)
        return policy

    def delete(self, policy):
        """Удаляет политику."""
        from owlready2 import destroy_entity
        if policy:
            destroy_entity(policy)
