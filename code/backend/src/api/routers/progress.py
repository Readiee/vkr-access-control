"""Webhook СДО: приём событий прогресса."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from api.dependencies import get_progress_service
from schemas import ProgressEvent
from services.progress_service import ProgressService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["Progress"])


@router.post(
    "/progress",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Регистрация события успеваемости",
)
async def register_progress(
    data: ProgressEvent,
    background_tasks: BackgroundTasks,
    service: ProgressService = Depends(get_progress_service),
) -> dict:
    try:
        service.update_progress(
            student_id=data.student_id,
            element_id=data.element_id,
            status=data.event_type,
        )
        background_tasks.add_task(
            service.rerun_reasoning_and_rebuild_cache, data.student_id
        )
        return {
            "status": "processing_in_background",
            "message": "Событие записано, идёт фоновый пересчёт доступов",
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception:
        logger.exception("register_progress упал на payload %s", data)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка обработки события",
        )
