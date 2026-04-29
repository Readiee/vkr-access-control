from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from api.dependencies import get_verification_service
from schemas.schemas import VerificationReportResponse
from services.verification import VerificationService

router = APIRouter(prefix="/api/v1/verify", tags=["Verification"])


@router.get(
    "/course/{course_id}",
    summary="Верификация курса",
    status_code=status.HTTP_200_OK,
    response_model=VerificationReportResponse,
)
async def verify_course(
    course_id: str = Path(..., description="ID курса в онтологии"),
    full: bool = Query(False, description="Включить redundancy и subsumption"),
    service: VerificationService = Depends(get_verification_service),
) -> dict:
    """Consistency + acyclicity + reachability; при full=true также redundancy/subsumption."""
    try:
        report = service.verify(course_id, include_subsumption=full)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return report.to_dict()
