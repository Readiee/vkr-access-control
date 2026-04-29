import uuid
from typing import Any, List

from owlready2 import destroy_entity


_STATUS_VALUES = ("completed", "failed", "viewed")


class StudentRepository:
    def __init__(self, onto):
        self.onto = onto

    def get_or_create(self, student_id: str):
        direct = self.onto.search_one(type=self.onto.Student, iri=f"*{student_id}")
        if direct is not None:
            return direct
        node_id = student_id if student_id.startswith("student_") else f"student_{student_id}"
        student = self.onto.search_one(type=self.onto.Student, iri=f"*{node_id}")
        if not student:
            student = self.onto.Student(node_id)
        return student


class CourseRepository:
    def __init__(self, onto):
        self.onto = onto

    def get_all_elements(self):
        return self.onto.CourseStructure.instances()

    def find_by_id(self, element_id: str):
        return self.onto.search_one(type=self.onto.CourseStructure, iri=f"*{element_id}")

    def get_or_create_element(self, element_id: str, element_class_name: str):
        element = self.find_by_id(element_id)
        if not element:
            element_class = getattr(self.onto, element_class_name)
            element = element_class(element_id)
        return element

    def get_all_competencies(self):
        return self.onto.Competency.instances() if hasattr(self.onto, "Competency") else []

    def parent_index(self) -> dict:
        """child.name -> parent OWL-индивид; один проход, O(1) lookup при каскаде."""
        index: dict = {}
        for parent in self.get_all_elements():
            children = list(getattr(parent, "has_module", []) or []) + list(
                getattr(parent, "contains_activity", []) or []
            )
            for child in children:
                index[child.name] = parent
        return index


class ProgressRepository:
    def __init__(self, onto):
        self.onto = onto

    def find_record(self, student, element):
        return self.onto.search_one(
            type=self.onto.ProgressRecord,
            refers_to_student=student,
            refers_to_element=element,
        )

    def find_all_for_student(self, student) -> List[Any]:
        return list(self.onto.search(type=self.onto.ProgressRecord, refers_to_student=student))

    def create_record(self, student, element):
        pr_id = f"pr_{uuid.uuid4().hex[:8]}"
        record = self.onto.ProgressRecord(pr_id)
        record.refers_to_student = student
        record.refers_to_element = element
        if record not in getattr(student, "has_progress_record", []):
            student.has_progress_record.append(record)
        return record

    def delete_record(self, student, record):
        if not record:
            return
        if hasattr(student, "has_progress_record") and record in student.has_progress_record:
            student.has_progress_record.remove(record)
        destroy_entity(record)

    def get_owl_status(self, status_value):
        # StrEnum проходит isinstance(_, str), но f-string подтягивает str(Enum) —
        # `ProgressStatus.COMPLETED` вместо `completed`. Нормализуем заранее.
        name = getattr(status_value, "value", status_value)
        if name not in _STATUS_VALUES:
            return None
        return getattr(self.onto, f"status_{name}", None)


class PolicyRepository:
    def __init__(self, onto):
        self.onto = onto

    def find_by_id(self, policy_id: str):
        return self.onto.search_one(type=self.onto.AccessPolicy, iri=f"*{policy_id}")

    def find_by_source_element(self, policy_node):
        return self.onto.search(has_access_policy=policy_node)

    def create_or_update(self, policy_id: str):
        policy = self.find_by_id(policy_id)
        if not policy:
            policy = self.onto.AccessPolicy(policy_id)
        return policy

    def delete(self, policy):
        if policy:
            destroy_entity(policy)
