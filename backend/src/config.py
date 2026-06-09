from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ProductSource = Literal["onebound", "justoneapi", "scraper", "mock"]

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

    # Vision (multimodal) — analyze Xiaohongshu outfit photos before planning
    vision_use_images: bool = Field(
        default=True,
        description="Send XHS note images to the LLM so it grounds outfits in real photos",
    )
    vision_model: str | None = Field(
        default=None,
        description="Multimodal model id for Vision Agent; falls back to OPENAI_MODEL",
    )
    vision_api_key: str | None = Field(
        default=None,
        description="API key for Vision Agent; falls back to DASHSCOPE_API_KEY then OPENAI_API_KEY",
    )
    vision_api_base: str | None = Field(
        default=None,
        description="OpenAI-compatible base URL for Vision (e.g. DashScope compatible-mode/v1)",
    )
    vision_max_images_per_note: int = Field(
        default=2,
        ge=1,
        le=6,
        description="Max images per note attached to the Vision LLM call",
    )

    # XHS Outfit Query Compiler — optional LLM keyword expansion (Step 3)
    xhs_query_llm_expand: bool = Field(
        default=False,
        description="When true, LLM may add 1-2 alternate XHS search phrases after rule compile",
    )

    # Product search: onebound | justoneapi | scraper | mock
    product_source: ProductSource = Field(
        default="onebound",
        description="onebound=万邦, justoneapi=Just One API, scraper=爬虫, mock=演示",
    )
    product_fallback_scraper: bool = Field(
        default=False,
        description="When true, try scraper if OneBound returns quota error 4013",
    )

    # OneBound Taobao API
    onebound_key: str | None = None
    onebound_secret: str | None = None
    onebound_max_calls_per_run: int = Field(default=40, ge=1)

    # Just One API — Taobao search (https://docs.justoneapi.com)
    justoneapi_token: str | None = None
    justoneapi_base_url: str = Field(
        default="https://api.justoneapi.com",
        description="Mainland CN optional: http://47.117.133.51:30015",
    )
    justoneapi_sort: str = Field(
        default="_sale",
        description="Taobao sort: _sale=销量(推荐), _bid=价格降序; bid=价格升序在部分关键词下会返回空列表",
    )
    justoneapi_max_calls_per_run: int = Field(
        default=40,
        ge=1,
        description="Max Taobao search API calls per planning run when PRODUCT_SOURCE=justoneapi",
    )
    justoneapi_xhs_notes_per_day: int = Field(
        default=3,
        ge=1,
        le=5,
        description="XHS reference notes shown per trip day in the report UI",
    )
    justoneapi_xhs_analysis_pool_per_day: int = Field(
        default=20,
        ge=1,
        le=20,
        description="Max XHS notes collected per day for vision trend analysis (top by likes)",
    )
    justoneapi_xhs_max_calls_per_run: int = Field(
        default=24,
        ge=1,
        description="Max XHS search+detail API calls per planning run",
    )
    justoneapi_xhs_fetch_detail: bool = Field(
        default=True,
        description="Fetch note detail for full image list after XHS search",
    )
    justoneapi_xhs_min_liked: int = Field(
        default=0,
        ge=0,
        description="Minimum liked_count to keep a XHS note (0 = no filter)",
    )

    # Taobao scraper (experimental)
    scraper_min_interval_sec: float = Field(default=2.0, ge=0.0)
    scraper_user_agent: str | None = None

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
    jimeng_i2i_req_key: str = "jimeng_i2i_v30"
    jimeng_image_width: int = Field(default=1328, ge=512, le=2048)
    jimeng_image_height: int = Field(default=1328, ge=512, le=2048)
    image_use_xhs_reference: bool = Field(
        default=False,
        description="Use Xiaohongshu outfit photos as Jimeng i2i reference for look images",
    )
    image_reference_fallback_direct: bool = Field(
        default=False,
        description="When AI generation fails, use XHS reference cover URL as look image",
    )

    # DashScope fallback (Tongyi Wanxiang)
    dashscope_api_key: str | None = None
    image_model: str = "wan2.2-t2i-flash"

    # Cache
    cache_dir: Path = Path(".cache")

    # API request/response recording (debug + mock replay source)
    api_record_enabled: bool = Field(
        default=True,
        description="When true, persist external API request/response pairs to api_record_dir",
    )
    api_record_dir: Path = Field(
        default=Path(".cache/api-recordings"),
        description="Directory for taobao/xhs/jimeng/deepseek API recordings",
    )

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
