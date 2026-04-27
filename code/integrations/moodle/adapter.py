"""Оркестратор импорта курса Moodle в онтологию (режим Б, single PDP).

Запуск:
    python -m integrations.moodle.adapter \\
        --moodle-url http://localhost:8081 \\
        --moodle-token <ws_token> \\
        --pdp-url http://localhost:8000 \\
        --course-shortname HAPPYPATH

Скрипт читает структуру курса из Moodle, формирует ``CourseSyncPayload`` и
посылает его на ``POST /api/v1/courses/{id}/sync``. После импорта серверная
часть автоматически запускает верификацию (UC-6).

Существующие ``course_modules.availability`` Moodle при импорте игнорируются
(см. SAT_DATA_MODELS §10.3 и §11.3): источник истины политик — наша онтология.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import requests

from .moodle_client import MoodleClient
from . import translators


logger = logging.getLogger("integrations.moodle.adapter")


@dataclass
class ImportStats:
    course_id: str
    sections: int
    activities: int
    students: int
    groups: int
    memberships: int
    initial_progress_events: int
    elapsed_seconds: float


class MoodleCourseImporter:
    """Импортирует курс Moodle и инициализирует ABox онтологии."""

    def __init__(self, moodle: MoodleClient, pdp_url: str, http_timeout: float = 15.0):
        self._moodle = moodle
        self._pdp_url = pdp_url.rstrip("/")
        self._http_timeout = http_timeout

    def import_course(self, course_shortname: str) -> ImportStats:
        started = time.monotonic()

        course = self._moodle.get_course_by_shortname(course_shortname)
        course_id = translators.course_individual_id(course)
        logger.info("Импорт курса %s (Moodle id=%s)", course_id, course["id"])

        contents = self._moodle.get_course_contents(course["id"])
        payload = translators.build_sync_payload(course, contents)
        self._post_course_sync(course_id, payload)

        users = self._moodle.get_enrolled_users(course["id"])
        groups = self._moodle.get_course_groups(course["id"])
        members = self._moodle.get_group_members([g["id"] for g in groups])
        memberships_index = {m["groupid"]: m.get("userids") or [] for m in members}
        group_payload, memberships = translators.extract_group_memberships(groups, memberships_index)
        self._post_groups(group_payload, memberships)

        student_payload = translators.extract_students(users)
        self._post_students(student_payload)

        progress_events = self._collect_initial_grades(course["id"], contents, users)
        for event in progress_events:
            self._post_progress(event)

        elapsed = time.monotonic() - started
        return ImportStats(
            course_id=course_id,
            sections=sum(1 for el in payload["elements"] if el["element_type"] == "module"),
            activities=sum(1 for el in payload["elements"] if el["element_type"] not in ("course", "module")),
            students=len(student_payload),
            groups=len(group_payload),
            memberships=len(memberships),
            initial_progress_events=len(progress_events),
            elapsed_seconds=elapsed,
        )

    def _post_course_sync(self, course_id: str, payload: Dict[str, Any]) -> None:
        url = f"{self._pdp_url}/api/v1/courses/{course_id}/sync"
        response = requests.post(url, json=payload, timeout=self._http_timeout)
        response.raise_for_status()

    def _post_groups(
        self,
        groups: List[Dict[str, Any]],
        memberships: List[Tuple[str, str]],
    ) -> None:
        # Серверная часть ожидает группы как часть структуры курса либо
        # отдельным эндпоинтом IntegrationService. В текущей DSL §40 группы
        # передаются вместе с памятью на стороне ``OntologyCore``; для PoC
        # достаточно записи через ``IntegrationService.set_group_membership``.
        for group in groups:
            url = f"{self._pdp_url}/api/v1/groups"
            requests.post(url, json=group, timeout=self._http_timeout)
        for student_id, group_id in memberships:
            url = f"{self._pdp_url}/api/v1/groups/{group_id}/members"
            requests.post(url, json={"student_id": student_id}, timeout=self._http_timeout)

    def _post_students(self, students: List[Dict[str, Any]]) -> None:
        url = f"{self._pdp_url}/api/v1/students/batch"
        requests.post(url, json={"students": students}, timeout=self._http_timeout)

    def _collect_initial_grades(
        self,
        course_id: int,
        contents: List[Dict[str, Any]],
        users: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        cmid_to_activity = {}
        for section in contents:
            for cm in section.get("modules") or []:
                cmid_to_activity[cm["id"]] = translators.activity_individual_id(cm)

        events: List[Dict[str, Any]] = []
        try:
            grade_items = self._moodle.get_grade_items(course_id)
        except Exception:
            logger.warning("Gradebook недоступен — стартовые оценки не импортированы")
            return events

        for entry in grade_items.get("usergrades", []) if isinstance(grade_items, dict) else []:
            student_individual = f"student_{entry['userid']}"
            for item in entry.get("gradeitems") or []:
                cmid = item.get("cmid")
                if cmid is None or cmid not in cmid_to_activity:
                    continue
                event = translators.grade_to_progress_event(
                    student_individual, cmid_to_activity[cmid], item,
                )
                if event is not None:
                    events.append(event)
        return events

    def _post_progress(self, event: Dict[str, Any]) -> None:
        url = f"{self._pdp_url}/api/v1/events/progress"
        requests.post(url, json=event, timeout=self._http_timeout)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Импорт курса Moodle в онтологию")
    parser.add_argument("--moodle-url", required=True, help="Базовый URL Moodle")
    parser.add_argument("--moodle-token", required=True, help="Web Services token")
    parser.add_argument("--pdp-url", required=True, help="URL OntoRule API")
    parser.add_argument(
        "--course-shortname",
        required=True,
        help="Moodle shortname импортируемого курса",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    importer = MoodleCourseImporter(
        moodle=MoodleClient(base_url=args.moodle_url, token=args.moodle_token),
        pdp_url=args.pdp_url,
    )
    stats = importer.import_course(args.course_shortname)
    logger.info(
        "Импорт завершён: course=%s, sections=%d, activities=%d, students=%d, groups=%d, "
        "memberships=%d, progress=%d, elapsed=%.2fs",
        stats.course_id, stats.sections, stats.activities, stats.students,
        stats.groups, stats.memberships, stats.initial_progress_events, stats.elapsed_seconds,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
