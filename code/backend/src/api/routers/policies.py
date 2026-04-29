import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.dependencies import get_policy_service
from schemas.schemas import Policy, PolicyCreate, TogglePolicy
from services.policy_service import PolicyConflictError, PolicyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])

INTERNAL_ERROR_DETAIL = "Внутренняя ошибка сервера"


@router.get("", response_model=List[Policy], summary="Список политик")
async def get_policies(
    course_id: Optional[str] = Query(None, description="Фильтр по ID курса"),
    element_id: Optional[str] = Query(None, description="Фильтр по ID элемента"),
    service: PolicyService = Depends(get_policy_service),
) -> List[Policy]:
    return service.get_policies(course_id=course_id, element_id=element_id)


@router.post(
    "",
    response_model=Policy,
    status_code=status.HTTP_201_CREATED,
    summary="Создать политику",
)
async def create_policy(
    policy: PolicyCreate,
    service: PolicyService = Depends(get_policy_service),
) -> Policy:
    try:
        return service.create_policy(policy)
    except PolicyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.explanation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        logger.exception("create_policy упал на payload %s", policy)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_ERROR_DETAIL,
        )


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить политику",
)
async def delete_policy(
    policy_id: str = Path(..., description="ID удаляемой политики"),
    service: PolicyService = Depends(get_policy_service),
) -> dict:
    try:
        deleted = service.delete_policy(policy_id)
    except PolicyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.explanation)
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
    service: PolicyService = Depends(get_policy_service),
) -> dict:
    try:
        return service.update_policy(policy_id, data)
    except PolicyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.explanation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception:
        logger.exception("update_policy %s упал на payload %s", policy_id, data)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_ERROR_DETAIL,
        )


@router.patch("/{policy_id}/toggle", summary="Переключить активность")
async def toggle_policy(
    toggle_data: TogglePolicy,
    policy_id: str = Path(..., description="ID политики"),
    service: PolicyService = Depends(get_policy_service),
) -> dict:
    try:
        service.toggle_policy(policy_id, toggle_data.is_active)
        return {
            "message": "Статус успешно изменён",
            "policy_id": policy_id,
            "is_active": toggle_data.is_active,
        }
    except PolicyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.explanation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
