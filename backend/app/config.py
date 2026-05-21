from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from the project root (one level above backend/)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_phone: str = ""
    telegram_session_name: str = "orellius_session"

    # Target channel
    target_channel: str = ""

    # Source channels (comma-separated)
    source_channels: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://orellius:orellius_dev_pass@localhost:5432/orellius"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Ollama (local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_translator: str = "qwen2.5:32b"
    ollama_model_orchestrator: str = "llama3.3:70b"
    ollama_model_reviewer: str = "deepseek-r1:32b"
    ollama_model_daemon: str = "qwen2.5-coder:32b"

    # Publishing
    publish_delay_seconds: int = 2
    auto_publish: bool = False
    channel_signature: str = ""

    # Media
    media_dir: str = "media"
    stamp_enabled: bool = True
    stamp_image_path: str = "assets/stamps/watermark.png"
    stamp_opacity: int = 55  # 10-100 percentage
    stamp_size_pct: int = 30  # 10-50 % of image width
    stamp_position: str = "center"  # center|bottom-right|bottom-left|top-right|top-left

    # Watermark Removal
    watermark_removal_enabled: bool = False
    watermark_ref_dir: str = "assets/watermark_refs"
    watermark_confidence_threshold: float = 0.65
    watermark_quality_threshold: float = 0.7

    # Geo Enrichment
    geo_enrichment_enabled: bool = True
    escalation_window_hours: int = 6
    escalation_threshold: int = 3

    # Ghost Mode
    ghost_mode_enabled: bool = True
    suppress_read_receipts: bool = True
    suppress_online_status: bool = True

    # Channel Intelligence
    channel_discovery_enabled: bool = False
    history_scrape_depth: int = 100
    channel_scan_interval_hours: int = 24

    # Pre-Processing Pipeline
    keyword_filter_enabled: bool = True
    dedup_enabled: bool = True

    # Fact Checking
    fact_check_enabled: bool = True
    priority_keywords: str = ""

    # Pikud HaOref (Home Front Command) Alerts
    hfc_alerts_enabled: bool = False
    hfc_poll_interval: float = 0.5
    hfc_dedup_ttl: int = 300

    # API
    api_secret_token: str = ""

    # Observability
    sentry_dsn: str = ""

    # Stripe Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_ids: dict = {}  # {"pro": "price_xxx", "enterprise": "price_yyy"}

    # Pipeline
    pipeline_timeout_seconds: int = 600
    pipeline_max_concurrent: int = 5

    # Ollama Timeouts
    ollama_keep_alive: str = "10m"
    ollama_preload_timeout: int = 300
    ollama_unload_timeout: int = 30
    ollama_inference_timeout: int = 180

    # Ghost Engine
    ghost_offline_interval: int = 300

    # Telegram
    telegram_dialog_limit: int = 200

    # WebSocket
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765

    @property
    def source_channels_list(self) -> list[str]:
        return [ch.strip() for ch in self.source_channels.split(",") if ch.strip()]


settings = Settings()
