from typing import Annotated

from fastapi import APIRouter, Depends

from standard_motion.core.models import Health
from standard_motion.core.service import check_health
from standard_motion.core.settings import Settings, get_settings

router = APIRouter(tags=["core"])


@router.get("/health")
def get_health(settings: Annotated[Settings, Depends(get_settings)]) -> Health:
    return check_health(settings)
