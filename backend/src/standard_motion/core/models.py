from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    meta_api_key_configured: bool
    # Steps that call Meta can run: a key is set, or a replay of the API answers in its place.
    meta_available: bool
