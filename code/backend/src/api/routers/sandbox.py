"""Песочница методиста: единственный тестовый студент для проверки правил
без побочных эффектов на реальные ABox.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.dependencies import get_sandbox_service
from schemas import SandboxGroupsPayload, SandboxProgressPayload
from services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sandbox", tags=["Sandbox"])

_INTERNAL_ERROR = "Внутренняя ошибка песочницы"


@router.get("/state", summary="Состояние песочницы (доступы и прогресс)")
async def get_sandbox_state(
    course_id: str = Query(..., description="ID курса"),
    service: SandboxService = Depends(get_sandbox_service),
) -> dict:
    try:
        return service.get_sandbox_state(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("get_sandbox_state %s упал", course_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_INTERNAL_ERROR,
        )


@router.post("/progress", summary="Симулировать прогресс тестового студента")
async def simulate_progress(
    payload: SandboxProgressPayload,
    service: SandboxService = Depends(get_sandbox_service),
) -> dict:
    try:
        return service.simulate_progress(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("simulate_progress упал на payload %s", payload)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_INTERNAL_ERROR,
        )


@router.delete("/progress/{element_id}", summary="Откатить прогресс по элементу")
async def rollback_progress(
    element_id: str = Path(..., description="ID элемента курса"),
    service: SandboxService = Depends(get_sandbox_service),
) -> dict:
    try:
        return service.rollback_progress(element_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/reset", summary="Полная очистка песочницы")
async def reset_all(
    service: SandboxService = Depends(get_sandbox_service),
) -> dict:
    try:
        return service.reset_all()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/competencies", summary="Перезаписать компетенции тестового студента")
async def set_competencies(
    competency_ids: List[str],
    service: SandboxService = Depends(get_sandbox_service),
) -> dict:
    try:
        return service.set_competencies(competency_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/groups", summary="Перезаписать группы тестового студента")
async def set_groups(
    payload: SandboxGroupsPayload,
    service: SandboxService = Depends(get_sandbox_service),
) -> dict:
    try:
        return service.set_groups(payload.group_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
