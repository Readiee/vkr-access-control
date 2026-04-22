from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.dependencies import get_access_service
from schemas.schemas import AvailableElements
from services.access_service import AccessService

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
    """Доступные элементы курса из кэша Redis (через AccessService)."""
    try:
        return service.get_course_access(student_id, course_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )


@router.get(
    "/student/{student_id}/element/{element_id}/explain",
    summary="Объяснение (не)доступа к элементу (UC-9)",
)
async def explain_access(
    student_id: str = Path(..., description="ID студента"),
    element_id: str = Path(..., description="ID элемента"),
    service: AccessService = Depends(get_access_service),
) -> dict:
    """Возвращает, какая политика заблокировала элемент или какой родитель каскадно."""
    try:
        return service.explain_blocking(student_id, element_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
