"""Импорт структуры курса и meta/tree-эндпоинты для Web UI."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.dependencies import get_integration_service
from schemas import (
    CourseSyncPayload,
    CourseTreeNode,
    ElementCompetenciesPayload,
    ElementMandatoryPayload,
    OntologyMeta,
)
from services.integration_service import IntegrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Integration"])


@router.post(
    "/courses/{course_id}/sync",
    summary="Импорт структуры курса с автоверификацией",
    status_code=status.HTTP_200_OK,
)
async def sync_course(
    payload: CourseSyncPayload,
    course_id: str = Path(..., description="ID синхронизируемого курса"),
    service: IntegrationService = Depends(get_integration_service),
) -> dict:
    try:
        return service.sync_course_structure(course_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("sync_course %s упал", course_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка синхронизации",
        )


@router.get(
    "/ontology/meta",
    response_model=OntologyMeta,
    summary="Метаданные онтологии для Web UI",
)
async def get_ontology_meta(
    service: IntegrationService = Depends(get_integration_service),
) -> OntologyMeta:
    return service.get_meta()


@router.get(
    "/courses/{course_id}/tree",
    response_model=List[CourseTreeNode],
    summary="Дерево курса с политиками",
)
async def get_course_tree(
    course_id: str = Path(..., description="ID курса в онтологии"),
    service: IntegrationService = Depends(get_integration_service),
) -> List[dict]:
    try:
        return service.get_course_tree(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/elements/{element_id}/competencies",
    summary="Перезаписать список выдаваемых элементом компетенций",
)
async def set_element_competencies(
    payload: ElementCompetenciesPayload,
    element_id: str = Path(..., description="ID элемента курса"),
    service: IntegrationService = Depends(get_integration_service),
) -> dict:
    try:
        return service.set_element_competencies(element_id, payload.competency_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put(
    "/elements/{element_id}/mandatory",
    summary="Перезаписать флаг обязательности элемента",
)
async def set_element_mandatory(
    payload: ElementMandatoryPayload,
    element_id: str = Path(..., description="ID элемента курса"),
    service: IntegrationService = Depends(get_integration_service),
) -> dict:
    try:
        return service.set_element_mandatory(element_id, payload.is_mandatory)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
