"""Маппинг сущностей Moodle на классы TBox онтологии (см. SAT_DATA_MODELS §11.2).

Чистые функции без побочных эффектов. Адаптер собирает данные через
``moodle_client``, прогоняет через переводчики и формирует ``CourseSyncPayload``
для эндпоинта ``POST /api/v1/courses/{id}/sync`` нашей системы.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


# Соответствие cm.modname → ElementType из core.enums
_MODNAME_TO_ELEMENT_TYPE: Dict[str, str] = {
    "quiz": "test",
    "lesson": "lecture",
    "assign": "assignment",
    "page": "lecture",
    "resource": "lecture",
    "url": "lecture",
    "book": "lecture",
    "workshop": "practice",
    "forum": "lecture",
}

# completion=2 — методист потребовал ручной отметки → элемент обязателен
_COMPLETION_MANDATORY = 2


def course_individual_id(course: Dict[str, Any]) -> str:
    """``Course.individual_name`` — ``shortname`` как стабильный идентификатор."""
    shortname = course.get("shortname") or f"course_{course['id']}"
    return f"course_{shortname}"


def section_individual_id(section: Dict[str, Any]) -> str:
    return f"module_{section['id']}"


def activity_individual_id(course_module: Dict[str, Any]) -> str:
    return f"activity_{course_module['id']}"


def student_individual_id(user: Dict[str, Any]) -> str:
    return f"student_{user['id']}"


def group_individual_id(group: Dict[str, Any]) -> str:
    return f"group_{group['id']}"


def competency_individual_id(competency: Dict[str, Any]) -> str:
    return f"comp_{competency.get('id') or competency.get('competencyid')}"


def translate_activity(course_module: Dict[str, Any]) -> Dict[str, Any]:
    """Привести Moodle ``course_module`` к ``CourseElement`` нашей схемы."""
    modname = (course_module.get("modname") or "").lower()
    element_type = _MODNAME_TO_ELEMENT_TYPE.get(modname, "lecture")
    is_mandatory = course_module.get("completion") == _COMPLETION_MANDATORY
    return {
        "element_id": activity_individual_id(course_module),
        "name": course_module.get("name") or f"activity_{course_module['id']}",
        "element_type": element_type,
        "is_mandatory": is_mandatory,
    }


def translate_section(section: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "element_id": section_individual_id(section),
        "name": section.get("name") or f"section_{section['id']}",
        "element_type": "module",
        "is_mandatory": True,
    }


def translate_course(course: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "element_id": course_individual_id(course),
        "name": course.get("fullname") or course.get("shortname"),
        "element_type": "course",
        "is_mandatory": True,
    }


def build_sync_payload(
    course: Dict[str, Any],
    contents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Собрать ``CourseSyncPayload`` из ответа Moodle.

    Иерархия плоская: ``elements`` — все узлы (курс, секции, активности).
    ``parent_id`` указывает на контейнер. Порядок задаётся ``order_index``.
    """
    course_id = course_individual_id(course)
    elements: List[Dict[str, Any]] = []

    course_node = translate_course(course)
    course_node["parent_id"] = None
    course_node["order_index"] = 0
    elements.append(course_node)

    for section_index, section in enumerate(contents):
        section_node = translate_section(section)
        section_node["parent_id"] = course_id
        section_node["order_index"] = section_index
        elements.append(section_node)

        for cm_index, cm in enumerate(section.get("modules") or []):
            activity_node = translate_activity(cm)
            activity_node["parent_id"] = section_node["element_id"]
            activity_node["order_index"] = cm_index
            elements.append(activity_node)

    return {
        "course_name": course.get("fullname") or course.get("shortname"),
        "elements": elements,
    }


def extract_students(users: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Список студентов в формате нашей системы."""
    result = []
    for user in users:
        full_name = " ".join(filter(None, [user.get("firstname"), user.get("lastname")]))
        result.append(
            {
                "student_id": student_individual_id(user),
                "name": full_name or user.get("username") or f"user_{user['id']}",
            }
        )
    return result


def extract_group_memberships(
    groups: Iterable[Dict[str, Any]],
    members_by_group: Dict[int, List[int]],
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """Группы и тапл (student_id, group_id) для belongs_to_group."""
    group_payload: List[Dict[str, Any]] = []
    memberships: List[Tuple[str, str]] = []
    for group in groups:
        group_id = group_individual_id(group)
        group_payload.append({"group_id": group_id, "name": group.get("name")})
        for user_id in members_by_group.get(group["id"], []):
            memberships.append((f"student_{user_id}", group_id))
    return group_payload, memberships


def grade_to_progress_event(
    student_id: str,
    activity_id: str,
    grade_item: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Преобразовать запись gradebook в ``ProgressEvent``.

    Возвращает None, если оценка ещё не выставлена. Используется при первичной
    загрузке исторических данных через адаптер; в стационарном режиме события
    приходят через ``event_observer.php``.
    """
    grade = grade_item.get("graderaw")
    if grade is None:
        return None
    return {
        "student_id": student_id,
        "element_id": activity_id,
        "event_type": "graded",
        "grade": float(grade),
    }
