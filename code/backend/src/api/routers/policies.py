from fastapi import APIRouter, Path, Query, status, HTTPException, Depends
from typing import List, Optional
from schemas.schemas import Policy, PolicyCreate, TogglePolicy
from services.policy_service import PolicyService
from api.dependencies import get_policy_service

router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])

@router.get("", response_model=List[Policy], summary="Список политик")
async def get_policies(
    course_id: Optional[str] = Query(None, description="Фильтр по ID курса"),
    element_id: Optional[str] = Query(None, description="Фильтр по ID элемента"),
    service: PolicyService = Depends(get_policy_service)
) -> List[Policy]:
    """Возвращает все политики доступа с опциональной фильтрацией."""
    return service.get_policies(course_id=course_id, element_id=element_id)


@router.post(
    "",
    response_model=Policy,
    status_code=status.HTTP_201_CREATED,
    summary="Создать политику",
)
async def create_policy(
    policy: PolicyCreate,
    service: PolicyService = Depends(get_policy_service)
) -> Policy:
    """Создаёт новый индивид AccessPolicy в графе онтологии."""
    try:
        return service.create_policy(policy)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить политику",
)
async def delete_policy(
    policy_id: str = Path(..., description="ID удаляемой политики"),
    service: PolicyService = Depends(get_policy_service)
) -> dict:
    """Безопасно удаляет индивид AccessPolicy из графа, отсоединяя от всех источников."""
    deleted = service.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Политика {policy_id} не найдена")
    return {"status": "deleted", "policy_id": policy_id}


@router.put(
    "/{policy_id}",
    response_model=Policy,
    summary="Обновить политику",
)
async def update_policy(
    data: PolicyCreate,
    policy_id: str = Path(..., description="ID обновляемой политики"),
    service: PolicyService = Depends(get_policy_service)
) -> dict:
    """Обновляет существующую политику доступа."""
    try:
        return service.update_policy(policy_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/{policy_id}/toggle", summary="Переключить активность")
async def toggle_policy(
    toggle_data: TogglePolicy,
    policy_id: str = Path(..., description="ID политики"),
    service: PolicyService = Depends(get_policy_service)
) -> dict:
    """Включает или отключает политику без её удаления."""
    try:
        service.toggle_policy(policy_id, toggle_data.is_active)
        return {"message": "Статус успешно изменён", "policy_id": policy_id, "is_active": toggle_data.is_active}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
