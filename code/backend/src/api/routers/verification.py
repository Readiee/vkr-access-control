from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.dependencies import get_verification_service
from services.verification import VerificationService

router = APIRouter(prefix="/api/v1/verify", tags=["Verification"])


@router.get(
    "/course/{course_id}",
    summary="Базовая верификация курса (СВ-1/2/3)",
    status_code=status.HTTP_200_OK,
)
async def verify_course(
    course_id: str = Path(..., description="ID курса в онтологии"),
    full: bool = Query(False, description="Включить СВ-4 Redundancy и СВ-5 Subsumption"),
    service: VerificationService = Depends(get_verification_service),
) -> dict:
    """Consistency + Acyclicity + Reachability. При full=true также СВ-4/5."""
    try:
        report = service.verify(course_id, include_subsumption=full)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return report.to_dict()
