from fastapi import APIRouter, Path, Depends, HTTPException, status
from typing import List
from schemas.schemas import OntologyMeta, CourseTreeNode
from services.course_service import CourseService
from api.dependencies import get_course_service

router = APIRouter(prefix="/api/v1", tags=["UI Data"])

@router.get("/ontology/meta", response_model=OntologyMeta, summary="Метаданные онтологии")
async def get_ontology_meta(service: CourseService = Depends(get_course_service)) -> OntologyMeta:
    """Возвращает словари типов правил, статусов и компетенций для редактора."""
    return service.get_meta()


@router.get("/courses/{course_id}/tree", response_model=List[CourseTreeNode], summary="Дерево курса")
async def get_course_tree(
    course_id: str = Path(..., description="ID курса в онтологии"),
    service: CourseService = Depends(get_course_service)
) -> List[dict]:
    """Возвращает иерархию курса с прикрепленными политиками для компонента TreeTable."""
    try:
        return service.get_course_tree(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
