"""Shared pipeline state that flows through the LangGraph agent graph."""

from typing import TypedDict


class MediaItem(TypedDict, total=False):
    file_id: str
    file_type: str  # "photo", "video", "document"
    local_path: str | None
    stamped_path: str | None
    # Watermark detection metadata (optional)
    watermark_detected: bool
    watermark_confidence: float
    watermark_original_path: str


class ExtractedFact(TypedDict):
    fact: str  # neutral factual statement in Hebrew
    category: str  # location|casualty|weapon|unit|timing|action|other


class AutoTags(TypedDict):
    event_type: str  # kinetic_strike|cyber_breach|movement_deployment|geopolitical|other
    region: str  # lowercase_snake_case English
    threat_level: str  # critical|high|medium|low|info
    entities: list[str]  # named entities


class GeoCountry(TypedDict):
    code: str  # ISO 3166-1 alpha-2
    name: str  # English name
    flag: str  # Emoji flag


class GeoContext(TypedDict, total=False):
    countries: list[GeoCountry]
    primary_country: GeoCountry | None
    locations: list[str]
    conflict_context: str | None
    conflict_level: str  # active_conflict | regional_tension | strategic_tension | none


class SourceTrustInfo(TypedDict):
    channel_id: str
    trust_level: str  # verified | trusted | neutral | suspect | untrusted
    accuracy_score: float  # 0.0-1.0
    total_posts: int
    corroborated_posts: int


class RelatedMessage(TypedDict):
    message_id: str
    title: str
    source_channel: str
    timestamp: float
    event_type: str
    threat_level: str
    countries: list[str]


class RawMetadata(TypedDict, total=False):
    raw_peer_id: int | None
    raw_message_id: int | None
    raw_json: dict
    forward_from: dict | None
    reply_to_msg_id: int | None
    edit_date: float | None
    edit_dates: list[dict]
    views: int | None
    reactions: list[dict] | None
    post_author: str | None
    grouped_id: int | None
    ttl_period: int | None


class PreprocessMeta(TypedDict, total=False):
    language: str
    keyword_matches: list[str]
    priority_score: float
    is_duplicate: bool
    duplicate_of: str | None


class FactCheckResult(TypedDict, total=False):
    risk_level: str  # "high" | "medium" | "low" | "none"
    confidence: float  # 0.0–1.0
    signals: list[str]  # credibility warning signals (Hebrew)
    reasoning: str  # brief explanation (Hebrew)
    flagged: bool  # True when risk is high or medium
    override_acknowledged: bool  # True after operator explicitly dismisses


class PipelineState(TypedDict):
    # Message identity
    message_id: str
    source_channel: str
    timestamp: float

    # Raw content from Telegram
    original_text: str
    media_items: list[MediaItem]

    # Translation output
    translated_text: str
    translation_approved: bool

    # Content classification (from analyst Pass 2)
    content_type: str  # intel|news|editorial|advertisement|spam|other

    # AI-extracted intelligence
    extracted_facts: list[ExtractedFact]
    auto_tags: AutoTags | None
    title: str  # 5-word punchy Hebrew headline from analyst
    suggested_template_id: str
    formatted_output: str
    suggested_intel_status: str

    # Content filtering
    content_filtered: bool  # True if auto-archived as ad/spam

    # Review
    review_notes: str
    approved: bool
    human_edited: bool

    # Media processing
    media_processed: bool

    # Geo-intelligence enrichment
    geo_context: GeoContext | None
    source_trust: SourceTrustInfo | None
    related_messages: list[RelatedMessage]
    situation_brief: str

    # Publishing
    published: bool
    publish_error: str

    # Ghost Engine deep metadata (optional — set by ingestion)
    raw_metadata: RawMetadata | None

    # Pre-processing metadata (optional — set by router)
    preprocess_meta: PreprocessMeta | None

    # Fact-check / disinformation assessment
    fact_check: FactCheckResult | None
