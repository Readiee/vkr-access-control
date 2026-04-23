"""IntegrationController (DSL §31): импорт структуры и правил из внешней СДО.

UC-10 (sync структуры) + meta/tree эндпоинты для Web UI. Приём событий прогресса
(UC-5) вынесен в отдельный ProgressController (api/routers/progress.py) по DSL.
После импорта IntegrationService автоматически запускает VerificationService
(стрелка DSL §118, решение 18.04).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.dependencies import get_integration_service
from schemas.schemas import CourseSyncPayload, CourseTreeNode, OntologyMeta
from services.integration_service import IntegrationService

router = APIRouter(prefix="/api/v1", tags=["Integration"])


@router.post(
    "/courses/{course_id}/sync",
    summary="Импорт структуры курса (UC-10) с автоверификацией",
    status_code=status.HTTP_200_OK,
)
async def sync_course(
    payload: CourseSyncPayload,
    course_id: str = Path(..., description="ID синхронизируемого курса"),
    service: IntegrationService = Depends(get_integration_service),
) -> dict:
    """Загрузить иерархию курса из СДО в онтологический граф + прогнать UC-6."""
    try:
        return service.sync_course_structure(course_id, payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка синхронизации: {exc}",
        )


@router.get(
    "/ontology/meta",
    response_model=OntologyMeta,
    summary="Метаданные онтологии для Web UI",
)
async def get_ontology_meta(
    service: IntegrationService = Depends(get_integration_service),
) -> OntologyMeta:
    """Словари типов правил, статусов, компетенций, групп, элементов курса."""
    return service.get_meta()


@router.get(
    "/courses/{course_id}/tree",
    response_model=List[CourseTreeNode],
    summary="Дерево курса с политиками для TreeTable",
)
async def get_course_tree(
    course_id: str = Path(..., description="ID курса в онтологии"),
    service: IntegrationService = Depends(get_integration_service),
) -> List[dict]:
    """Иерархия курса с прикрепленными политиками."""
    try:
        return service.get_course_tree(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
