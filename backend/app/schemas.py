"""Pydantic request/response models for all API endpoints."""

from pydantic import BaseModel, Field

# ── Channels ──────────────────────────────────────────────────


class AddChannelRequest(BaseModel):
    channel: str = Field(..., min_length=1)


class DiscoverChannelsRequest(BaseModel):
    seed_channel: str = Field(..., min_length=1)
    depth: int = Field(default=1, ge=1, le=5)


class ProfileChannelRequest(BaseModel):
    channel: str = Field(..., min_length=1)


class ScrapeChannelRequest(BaseModel):
    channel: str = Field(..., min_length=1)
    limit: int | None = None


# ── Templates ─────────────────────────────────────────────────


class CreateTemplateRequest(BaseModel):
    model_config = {"extra": "allow"}


class UpdateTemplateRequest(BaseModel):
    model_config = {"extra": "allow"}


class ReorderTemplatesRequest(BaseModel):
    ordered_ids: list[str]


class ApplyTemplateRequest(BaseModel):
    template_id: str
    translated_text: str = ""
    extracted_facts: list[dict] = Field(default_factory=list)
    auto_tags: dict | None = None
    timestamp: float | int | None = None
    title: str = ""
    intel_status: str = ""


# ── Taxonomies ────────────────────────────────────────────────


class TaxonomyItemRequest(BaseModel):
    key: str = Field(..., min_length=1)
    name_en: str = Field(..., min_length=1)
    name_he: str = Field(..., min_length=1)


class UpdateTaxonomyItemRequest(BaseModel):
    key: str | None = None
    name_en: str | None = None
    name_he: str | None = None


# ── Replacements ──────────────────────────────────────────────


class AddReplacementRequest(BaseModel):
    find: str = Field(..., min_length=1)
    replace: str = ""
    enabled: bool = True


class UpdateReplacementRequest(BaseModel):
    find: str | None = None
    replace: str | None = None
    enabled: bool | None = None


# ── Review ────────────────────────────────────────────────────


class ApproveMessageRequest(BaseModel):
    edited_text: str | None = None
    included_media: list[str] | None = None


class BulkMessageRequest(BaseModel):
    message_ids: list[str] = Field(default_factory=list)


# ── Settings ──────────────────────────────────────────────────


class UpdateSettingsRequest(BaseModel):
    publish_delay: int | None = None
    auto_publish: bool | None = None
    stamp_enabled: bool | None = None
    stamp_image_path: str | None = None
    stamp_opacity: int | None = Field(default=None, ge=10, le=100)
    stamp_size_pct: int | None = Field(default=None, ge=10, le=50)
    stamp_position: str | None = None
    target_channel: str | None = None
    watermark_removal_enabled: bool | None = None
    watermark_confidence_threshold: float | None = None
    geo_enrichment_enabled: bool | None = None
    ghost_mode_enabled: bool | None = None
    suppress_read_receipts: bool | None = None
    suppress_online_status: bool | None = None
    keyword_filter_enabled: bool | None = None
    dedup_enabled: bool | None = None
    priority_keywords: str | None = None
    channel_signature: str | None = None
    fact_check_enabled: bool | None = None


# ── Watermark ─────────────────────────────────────────────────


class AddWatermarkRefRequest(BaseModel):
    channel: str = "global"
    image: str = Field(..., min_length=1, description="Base64-encoded image")
    filename: str = "ref.png"


class DeleteWatermarkRefRequest(BaseModel):
    channel: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)


# ── Telegram ──────────────────────────────────────────────────


class TelegramConnectRequest(BaseModel):
    phone: str = ""


class TelegramCodeRequest(BaseModel):
    code: str = Field(..., min_length=1)


class Telegram2FARequest(BaseModel):
    password: str = Field(..., min_length=1)


class TelegramTestSendRequest(BaseModel):
    channel: str = Field(..., min_length=1)
    text: str = "Orellius Manager - Test message"


# ── Source Trust ──────────────────────────────────────────────


class UpdateSourceTrustRequest(BaseModel):
    trust_level: str = Field(..., min_length=1)


# ── Pre-Processing ────────────────────────────────────────────


class UpdateKeywordsRequest(BaseModel):
    keywords: str = ""


# ── HFC ───────────────────────────────────────────────────────


class UpdateHfcTemplateRequest(BaseModel):
    template_body: str = Field(..., min_length=1)
