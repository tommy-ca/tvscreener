from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class _PrefectEnv(BaseSettings):
    # Repo-specific defaults. Values can be provided via `.env` or environment.
    prefect_host: str = "127.0.0.1"
    prefect_port: int = 4200
    prefect_work_pool: str = "tvscreener"
    prefect_data_queue: str = "data"
    prefect_analytics_queue: str = "analytics"

    # Also accept Prefect's canonical env vars.
    prefect_api_url: str | None = Field(default=None, validation_alias="PREFECT_API_URL")
    prefect_home: str | None = Field(default=None, validation_alias="PREFECT_HOME")

    model_config = SettingsConfigDict(env_prefix="TVSCREENER_", extra="ignore")


@dataclass(frozen=True, slots=True)
class PrefectConfig:
    api_host: str
    api_port: int
    api_url: str
    prefect_home: Path
    work_pool: str
    data_work_queue: str
    analytics_work_queue: str


def load_config() -> PrefectConfig:
    load_dotenv(repo_root() / ".env", override=False)
    env = _PrefectEnv()

    host = env.prefect_host.strip()
    port = int(env.prefect_port)
    api_url = (env.prefect_api_url or f"http://{host}:{port}/api").strip()
    home = Path(env.prefect_home or (repo_root() / ".prefect-home")).resolve()
    pool = env.prefect_work_pool.strip()
    data_q = env.prefect_data_queue.strip()
    analytics_q = env.prefect_analytics_queue.strip()
    return PrefectConfig(
        api_host=host,
        api_port=port,
        api_url=api_url,
        prefect_home=home,
        work_pool=pool,
        data_work_queue=data_q,
        analytics_work_queue=analytics_q,
    )
