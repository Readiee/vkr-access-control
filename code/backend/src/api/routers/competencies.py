import logging
from typing import List
from fastapi import APIRouter, status, HTTPException
from schemas.schemas import Competency
from services.ontology_core import OntologyCore
from api.dependencies import get_ontology_core

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/competencies", tags=["Competencies"])

@router.get("", response_model=List[Competency], summary="Получить список компетенций")
def get_competencies():
    """Возвращает список всех компетенций из онтологии."""
    core = get_ontology_core()
    onto = core.onto
    
    result = []
    if hasattr(onto, "Competency"):
        for comp in onto.Competency.instances():
            # Безопасное извлечение родителя
            parent_list = getattr(comp, "is_subcompetency_of", [])
            parent_id = parent_list[0].name if parent_list else None
            
            result.append(Competency(
                id=comp.name,
                name=comp.label[0] if comp.label else comp.name,
                parent_id=parent_id
            ))
    return result

@router.post("", response_model=Competency, status_code=status.HTTP_201_CREATED, summary="Создать компетенцию")
def create_competency(comp: Competency):
    """Создает новую компетенцию в онтологии со связью parent_id."""
    core = get_ontology_core()
    onto = core.onto
    
    # Проверяем, существует ли уже
    existing = onto.search_one(iri=f"*{comp.id}")
    if existing:
        logger.warning(f"Существующая компетенция {comp.id} ({comp.name}) будет перезаписана на {comp.id} ({comp.name})")
    new_comp = onto.Competency(comp.id)
    new_comp.label = [comp.name]

    # parent ищем только среди Competency — иначе при совпадении имён ссылка
    # может привязаться к другому классу (методисту, лекции и т.п.)
    if comp.parent_id:
        parent = onto.search_one(iri=f"*{comp.parent_id}", type=onto.Competency)
        if parent is None:
            raise HTTPException(
                status_code=400,
                detail=f"Родительская компетенция {comp.parent_id} не найдена (ни одного индивида класса Competency с таким id)",
            )
        if parent not in new_comp.is_subcompetency_of:
            new_comp.is_subcompetency_of.append(parent)
    
    core.save()
    return comp

@router.post("/sync", status_code=status.HTTP_200_OK, summary="Синхронизация компетенций из LMS")
def sync_competencies(payload: List[Competency]):
    """Пакетное создание компетенций и их иерархии."""
    core = get_ontology_core()
    onto = core.onto
    
    # 1. Первый проход: создаём/обновляем индивиды класса Competency
    for comp in payload:
        existing = onto.search_one(iri=f"*{comp.id}", type=onto.Competency)
        if existing is None:
            new_comp = onto.Competency(comp.id)
        else:
            new_comp = existing
        new_comp.label = [comp.name]

    # 2. Второй проход: связи иерархии
    for comp in payload:
        if not comp.parent_id:
            continue
        child = onto.search_one(iri=f"*{comp.id}", type=onto.Competency)
        parent = onto.search_one(iri=f"*{comp.parent_id}", type=onto.Competency)
        if child is None or parent is None:
            logger.warning(
                "sync_competencies: пропущена связь %s → %s (Competency не найдены)",
                comp.id, comp.parent_id,
            )
            continue
        if parent not in child.is_subcompetency_of:
            child.is_subcompetency_of.append(parent)
                    
    core.save()
    core.run_reasoner() # Перерасчет графа
    return {"status": "success", "processed_count": len(payload)}
