from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status

from api.dependencies import get_course_service, get_ontology_core, get_progress_service
from schemas.schemas import CourseSyncPayload, ProgressEvent
from services.course_service import CourseService
from services.ontology_core import OntologyCore
from services.progress_service import ProgressService

router = APIRouter(prefix="/api/v1", tags=["Integration"])


@router.post(
    "/courses/{course_id}/sync",
    summary="Синхронизация структуры курса",
    status_code=status.HTTP_200_OK,
)
async def sync_course(
    payload: CourseSyncPayload,
    course_id: str = Path(..., description="ID синхронизируемого курса"),
    service: CourseService = Depends(get_course_service),
) -> dict:
    """Загрузить иерархию курса из СДО в онтологический граф."""
    try:
        return service.sync_course_structure(course_id, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка синхронизации: {exc}",
        )


@router.post(
    "/events/progress",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Регистрация события успеваемости",
)
async def register_progress(
    data: ProgressEvent,
    background_tasks: BackgroundTasks,
    core: OntologyCore = Depends(get_ontology_core),
    service: ProgressService = Depends(get_progress_service),
) -> dict:
    """Webhook СДО: записать прогресс и запустить reasoning в фоне."""
    try:
        service.update_progress(
            student_id=data.student_id,
            element_id=data.element_id,
            status=data.event_type,
        )

        def run_reasoner_and_cache() -> None:
            core.run_reasoner()
            service.invalidate_student_cache(data.student_id)

        background_tasks.add_task(run_reasoner_and_cache)

        return {
            "status": "processing_in_background",
            "message": "Событие записано, идёт фоновый пересчёт доступов",
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка: {exc}",
        )
