from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ — fixed path, independent of cwd (Streamlit, pytest, CLI)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_ROOT / ".env"


def load_project_env(*, override: bool = True) -> None:
    """
    Load ``backend/.env`` into ``os.environ``.

    With ``override=True`` (default), values from the project ``.env`` replace
    stale system/user environment variables such as ``OPENAI_API_KEY``. This
    prevents Windows/Cursor global keys from shadowing the project config.
    """
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=override)


# Apply on import so all entry points (CLI, Streamlit, tests) behave the same.
load_project_env(override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (OpenAI-compatible)
    openai_api_key: str | None = None
    openai_api_base: str = "https://api.deepseek.com/v1"
    openai_model: str = "deepseek-chat"

    # OneBound Taobao API
    onebound_key: str | None = None
    onebound_secret: str | None = None
    onebound_max_calls_per_run: int = Field(default=8, ge=1)

    # AMap (Gaode) Web Service — geocoding + weather
    amap_api_key: str | None = None

    # Image generation
    image_provider: str = Field(
        default="jimeng",
        description="jimeng (Volcengine), dashscope, or none",
    )
    skip_image_generation: bool = Field(
        default=False,
        description="When true, skip Jimeng/DashScope calls (for faster local testing)",
    )

    # Volcengine / Jimeng AI (即梦文生图 3.1)
    volcengine_access_key: str | None = None
    volcengine_secret_key: str | None = None
    jimeng_req_key: str = "jimeng_t2i_v31"
    jimeng_image_width: int = Field(default=1328, ge=512, le=2048)
    jimeng_image_height: int = Field(default=1328, ge=512, le=2048)

    # DashScope fallback (Tongyi Wanxiang)
    dashscope_api_key: str | None = None
    image_model: str = "wan2.2-t2i-flash"

    # Cache
    cache_dir: Path = Path(".cache")

    def validate_llm(self) -> None:
        if not self.openai_api_key:
            raise ValidationError.from_exception_data(
                "Settings",
                [{"type": "missing", "loc": ("openai_api_key",), "input": None, "msg": "Field required"}],
            )

    def validate_onebound(self) -> None:
        missing = [
            name
            for name, value in (
                ("onebound_key", self.onebound_key),
                ("onebound_secret", self.onebound_secret),
            )
            if not value
        ]
        if missing:
            raise ValidationError.from_exception_data(
                "Settings",
                [
                    {
                        "type": "missing",
                        "loc": (field,),
                        "input": None,
                        "msg": "Field required",
                    }
                    for field in missing
                ],
            )

    def validate_amap(self) -> None:
        if not self.amap_api_key:
            raise ValidationError.from_exception_data(
                "Settings",
                [
                    {
                        "type": "missing",
                        "loc": ("amap_api_key",),
                        "input": None,
                        "msg": "Field required",
                    }
                ],
            )

    def validate_dashscope(self) -> None:
        if not self.dashscope_api_key:
            raise ValidationError.from_exception_data(
                "Settings",
                [
                    {
                        "type": "missing",
                        "loc": ("dashscope_api_key",),
                        "input": None,
                        "msg": "Field required",
                    }
                ],
            )

    def validate_jimeng(self) -> None:
        missing = [
            name
            for name, value in (
                ("volcengine_access_key", self.volcengine_access_key),
                ("volcengine_secret_key", self.volcengine_secret_key),
            )
            if not value
        ]
        if missing:
            raise ValidationError.from_exception_data(
                "Settings",
                [
                    {
                        "type": "missing",
                        "loc": (field,),
                        "input": None,
                        "msg": "Field required",
                    }
                    for field in missing
                ],
            )


def key_fingerprint(value: str | None, *, length: int = 4) -> str:
    """Return a safe suffix for logs/UI (never print full secrets)."""
    if not value:
        return "none"
    if len(value) <= length:
        return "*" * len(value)
    return value[-length:]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Reload ``backend/.env`` and refresh the cached settings singleton."""
    get_settings.cache_clear()
    load_project_env(override=True)
    return get_settings()
