from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]

# What Standard Motion is scored against: blind Reference labels, or, with none given, the
# success flag each source ships (the Dataset outcome), which also lifts the blind gate.
GroundTruth = Literal["reference_labels", "dataset_outcome"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    model_api_key: SecretStr | None = None
    meta_base_url: str = "https://api.meta.ai/v1"
    meta_budget_usd: float = 5.0  # hard stop on total recorded Meta API spend
    data_dir: Path = REPO_ROOT / "data"
    # Read droid_100 from a local copy laid out like the repo (test fixtures), not the Hub.
    droid100_root: Path | None = None
    droid101_root: Path | None = None  # likewise for droid_1.0.1
    ingest_concurrency: int = 4  # Episodes transcoded at once
    # Serve Meta calls from responses recorded by `RecordingTransport` instead of the network
    # (e2e does); no API key needed.
    meta_replay: Path | None = None
    ground_truth: GroundTruth = "reference_labels"

    @field_validator("model_api_key", mode="before")
    @classmethod
    def _blank_key_is_no_key(cls, value: object) -> object:
        return None if value == "" else value  # so MODEL_API_KEY= turns Meta off (e2e does)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "standard-motion.db"

    @property
    def cost_log_path(self) -> Path:
        return self.data_dir / "meta_costs.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
