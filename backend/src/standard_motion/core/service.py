from standard_motion.core.models import Health
from standard_motion.core.settings import Settings


def check_health(settings: Settings) -> Health:
    configured = settings.model_api_key is not None
    return Health(
        status="ok",
        meta_api_key_configured=configured,
        meta_available=configured or settings.meta_replay is not None,
    )
