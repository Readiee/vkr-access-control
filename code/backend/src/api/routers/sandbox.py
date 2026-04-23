from fastapi import APIRouter, Depends, HTTPException

from services.sandbox_service import SandboxService
from schemas.schemas import SandboxProgressPayload
from api.dependencies import get_sandbox_service

router = APIRouter(prefix="/api/v1/sandbox", tags=["Sandbox"])


@router.get("/state", summary="Получить состояние песочницы (доступы и прогресс)")
def get_sandbox_state(
    course_id: str,
    service: SandboxService = Depends(get_sandbox_service),
):
    try:
        return service.get_sandbox_state(course_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/progress", summary="Симулировать прогресс тестового студента")
def simulate_progress(
    payload: SandboxProgressPayload,
    service: SandboxService = Depends(get_sandbox_service),
):
    try:
        return service.simulate_progress(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/progress/{element_id}", summary="Откатить прогресс для элемента")
def rollback_progress(
    element_id: str,
    service: SandboxService = Depends(get_sandbox_service),
):
    try:
        return service.rollback_progress(element_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/reset", summary="Ядерная кнопка: полная очистка песочницы")
def reset_all(
    service: SandboxService = Depends(get_sandbox_service),
):
    try:
        return service.reset_all()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/competencies", summary="Перезаписать компетенции")
def set_competencies(
    competency_ids: list[str],
    service: SandboxService = Depends(get_sandbox_service),
):
    try:
        return service.set_competencies(competency_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
