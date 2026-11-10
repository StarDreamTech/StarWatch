"""调度服务的环境变量配置。"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from starwatch_core.constants import (
    RATE_LIMIT_DEFAULT_REQUESTS,
    RATE_LIMIT_DEFAULT_WINDOW_SECONDS,
)

MONGO_SELECTION_TIMEOUT_MS = 5_000
SEARCH_MAX_LENGTH = 100


class Settings(BaseSettings):
    """从环境变量读取调度器配置。不在代码里写死地址或密钥。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "starwatch"
    scheduler_host: str = "0.0.0.0"
    scheduler_port: int = 8080
    scheduler_enabled: bool = True
    scheduler_poll_seconds: float = 1
    scheduler_batch_size: int = 20
    scheduler_max_concurrency: int = 8
    scheduler_load_concurrency: int = 1
    fetcher_base_url: str = "http://localhost:8081"
    fetcher_timeout_seconds: float = 90
    app_timezone: str = "Asia/Shanghai"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    rate_limit_requests: int = RATE_LIMIT_DEFAULT_REQUESTS
    rate_limit_window_seconds: int = RATE_LIMIT_DEFAULT_WINDOW_SECONDS

    @property
    def cors_origin_list(self) -> list[str]:
        """拆开逗号分隔的 CORS 来源。空字符串会被丢掉。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def get_settings() -> Settings:
    """读取当前环境中的配置。"""
    return Settings()
