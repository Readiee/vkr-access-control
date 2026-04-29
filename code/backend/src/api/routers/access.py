import logging

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.dependencies import get_access_service
from schemas import AvailableElements, BlockingExplanationResponse
from services.access import AccessService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/access", tags=["Access"])


@router.get(
    "/student/{student_id}/course/{course_id}",
    response_model=AvailableElements,
    summary="Матрица доступов студента в рамках курса",
)
async def get_student_access(
    student_id: str = Path(..., description="ID студента"),
    course_id: str = Path(..., description="ID курса"),
    service: AccessService = Depends(get_access_service),
) -> AvailableElements:
    try:
        return service.get_course_access(student_id, course_id)
    except Exception:
        logger.exception("get_student_access %s/%s упал", student_id, course_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка чтения доступа",
        )


@router.get(
    "/student/{student_id}/element/{element_id}/explain",
    summary="Объяснение (не)доступа к элементу",
    response_model=BlockingExplanationResponse,
)
async def explain_access(
    student_id: str = Path(..., description="ID студента"),
    element_id: str = Path(..., description="ID элемента"),
    service: AccessService = Depends(get_access_service),
) -> dict:
    try:
        return service.explain_blocking(student_id, element_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
