"""抓取服务的环境变量配置。"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取抓取器配置。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    fetcher_host: str = "0.0.0.0"
    fetcher_port: int = 8081
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        """拆开逗号分隔的 CORS 来源。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def get_settings() -> Settings:
    """读取当前环境中的配置。"""
    return Settings()
