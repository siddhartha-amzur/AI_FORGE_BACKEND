from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.dataframe_qa import DataframeQARequest, DataframeQAResponse
from app.services.dataframe_agent_service import DataframeAgentError, answer_question_from_source

router = APIRouter(prefix="/dataframe", tags=["Dataframe QA"])


@router.post("/analyze", response_model=DataframeQAResponse)
async def analyze_dataframe(
    payload: DataframeQARequest,
    current_user: User = Depends(get_current_user),
):
    _ = current_user

    try:
        result = await answer_question_from_source(
            question=payload.question,
            google_sheet_url=payload.google_sheet_url,
            file_path=payload.file_path,
        )
    except DataframeAgentError as exc:
        raise HTTPException(status_code=400, detail={"error": "dataframe_analysis_failed", "message": str(exc)}) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"error": "dataframe_analysis_error", "message": str(exc)}) from exc

    return DataframeQAResponse(**result)
