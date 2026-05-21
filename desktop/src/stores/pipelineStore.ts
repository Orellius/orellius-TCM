import { create } from "zustand";
import { api } from "../lib/api";

export type AgentStatus = "idle" | "running" | "error" | "waiting_review";

/**
 * REST fallback: fetch enriched data for a message when WS delivery may have failed.
 * Debounced per message_id — only one in-flight request at a time.
 */
const _enrichFetching = new Set<string>();
async function _fetchEnrichedFallback(messageId: string, storeSetter: (fn: (s: PipelineStore) => Partial<PipelineStore>) => void) {
  if (_enrichFetching.has(messageId)) return;
  _enrichFetching.add(messageId);
  try {
    const data = await api.getEnrichedData(messageId);
    if (!data.ok) return;
    storeSetter((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId
          ? {
              ...m,
              status: (data.status as MessageStatus) ?? m.status,
              translatedText: (data.translatedText as string) ?? m.translatedText,
              contentType: (data.contentType as ContentType) ?? m.contentType,
              extractedFacts: (data.extractedFacts as ExtractedFact[]) ?? m.extractedFacts,
              autoTags: (data.autoTags as AutoTags) ?? m.autoTags,
              title: (data.title as string) ?? m.title,
              suggestedTemplateId: (data.suggestedTemplateId as string) ?? m.suggestedTemplateId,
              suggestedIntelStatus: (data.suggestedIntelStatus as string) ?? m.suggestedIntelStatus,
              formattedOutput: (data.formattedOutput as string) ?? m.formattedOutput,
              reviewNotes: (data.reviewNotes as string) ?? m.reviewNotes,
              geoContext: (data.geoContext as GeoContext) ?? m.geoContext,
              sourceTrust: (data.sourceTrust as SourceTrustInfo) ?? m.sourceTrust,
              relatedMessages: (data.relatedMessages as RelatedMessage[]) ?? m.relatedMessages,
              situationBrief: (data.situationBrief as string) ?? m.situationBrief,
              rawMetadata: (data.rawMetadata as RawMetadata) ?? m.rawMetadata,
              preprocessMeta: (data.preprocessMeta as PreprocessMeta) ?? m.preprocessMeta,
              factCheck: (data.factCheck as FactCheckResult) ?? m.factCheck,
              hfcAlert: (data.hfcAlert as boolean) ?? m.hfcAlert,
              hfcAutoPublished: (data.hfcAutoPublished as boolean) ?? m.hfcAutoPublished,
            }
          : m,
      ),
    }));
  } catch {
    // REST fallback is best-effort
  } finally {
    _enrichFetching.delete(messageId);
  }
}

export interface ExtractedFact {
  fact: string;
  category: string;
}

export interface AutoTags {
  event_type: string;
  region: string;
  threat_level: string;
  entities: string[];
}

export interface GeoCountry {
  code: string;
  name: string;
  flag: string;
}

export interface GeoContext {
  countries: GeoCountry[];
  primary_country: GeoCountry | null;
  locations: string[];
  conflict_context: string | null;
  conflict_level: string; // active_conflict | regional_tension | strategic_tension | none
}

export interface SourceTrustInfo {
  channel_id: string;
  trust_level: string; // verified | trusted | neutral | suspect | untrusted
  accuracy_score: number;
  total_posts: number;
  corroborated_posts: number;
}

export interface RelatedMessage {
  message_id: string;
  title: string;
  source_channel: string;
  timestamp: number;
  event_type: string;
  threat_level: string;
  countries: string[];
}

export type MessageStatus =
  | "ingested"
  | "translating"
  | "fact_checking"
  | "reviewing"
  | "processing_media"
  | "enriching"
  | "publishing"
  | "published"
  | "publish_failed"
  | "failed"
  | "archived";

export type ContentType = "intel" | "news" | "editorial" | "advertisement" | "spam" | "other" | null;

export interface RawMetadata {
  raw_peer_id: number | null;
  raw_message_id: number | null;
  raw_json: Record<string, unknown>;
  forward_from: Record<string, unknown> | null;
  reply_to_msg_id: number | null;
  edit_date: number | null;
  edit_dates: Array<{ timestamp: number; text: string; edit_date: number | null }>;
  views: number | null;
  reactions: Array<{ count: number; emoticon?: string; custom_emoji_id?: number }> | null;
  post_author: string | null;
  grouped_id: number | null;
  ttl_period: number | null;
}

export interface PreprocessMeta {
  language: string;
  keyword_matches: string[];
  priority_score: number;
  is_duplicate: boolean;
  duplicate_of: string | null;
}

export interface FactCheckResult {
  risk_level: string;    // "high" | "medium" | "low" | "none"
  confidence: number;    // 0.0–1.0
  signals: string[];     // credibility warning signals (Hebrew)
  reasoning: string;     // brief explanation (Hebrew)
  flagged: boolean;      // True when risk is high or medium
  override_acknowledged: boolean;  // True after operator explicitly dismisses
}

export interface PipelineMessage {
  id: string;
  sourceChannel: string;
  originalText: string;
  translatedText: string | null;
  mediaUrls: string[];
  status: MessageStatus;
  timestamp: number;
  contentType: ContentType;
  extractedFacts: ExtractedFact[] | null;
  autoTags: AutoTags | null;
  title: string | null;
  suggestedTemplateId: string | null;
  suggestedIntelStatus: string | null;
  formattedOutput: string | null;
  reviewNotes: string | null;
  // Geo-intelligence enrichment
  geoContext: GeoContext | null;
  sourceTrust: SourceTrustInfo | null;
  relatedMessages: RelatedMessage[];
  situationBrief: string;
  // Watermark detection metadata (optional, set by media handler)
  watermarkDetected?: boolean;
  watermarkConfidence?: number;
  watermarkOriginalPath?: string;
  // Ghost Engine deep metadata
  rawMetadata?: RawMetadata | null;
  // Pre-processing metadata
  preprocessMeta?: PreprocessMeta | null;
  // Fact check / disinformation assessment
  factCheck?: FactCheckResult | null;
  // HFC (Pikud HaOref) alert flag
  hfcAlert?: boolean;
  // HFC auto-published (bypasses all gates, no review needed)
  hfcAutoPublished?: boolean;
}

export interface AgentState {
  /** Stable ID used as i18n key: "agent.ingestion", "agent.analyst", etc. */
  id: string;
  /** English fallback name (for backend event matching) */
  name: string;
  status: AgentStatus;
  lastActivity: string;
  messagesProcessed: number;
}

type StatusFilter = "all" | "reviewing" | "published" | "failed" | "in_progress";

export interface HealthReport {
  timestamp: number;
  services: Record<string, string>;
  error_counts: Record<string, number>;
}

export interface DaemonInsight {
  timestamp: number;
  agent: string;
  error: string;
  suggestion: string;
}

interface PipelineStore {
  // Pipeline status
  isRunning: boolean;
  agents: AgentState[];

  // Unified message list (single source of truth)
  messages: PipelineMessage[];

  // Selected message for dossier view
  selectedMessageId: string | null;

  // Feed status filter (shared so StatusRail can drive MessageFeed)
  feedStatusFilter: StatusFilter;

  // Health monitoring
  latestHealthReport: HealthReport | null;
  daemonInsights: DaemonInsight[];

  // HFC (Pikud HaOref) state
  hfcRunning: boolean;
  hfcGeoBlocked: boolean;
  hfcPollerHealthy: boolean;

  // Actions
  updateFromEvent: (event: Record<string, unknown>) => void;
  setRunning: (running: boolean) => void;
  selectMessage: (id: string | null) => void;
  removeMessage: (id: string) => void;
  setFeedStatusFilter: (filter: StatusFilter) => void;
  clearAllMessages: () => void;
}

/**
 * Check if the user is actively reviewing a message (selected message is in "reviewing" status).
 * When true, incoming review_requests must NOT steal focus.
 */
function _isUserBusy(state: { messages: PipelineMessage[]; selectedMessageId: string | null }): boolean {
  if (!state.selectedMessageId) return false;
  const selected = state.messages.find((m) => m.id === state.selectedMessageId);
  return selected?.status === "reviewing";
}

/**
 * Normalize a raw WS payload into a safe PipelineMessage.
 * Ensures all required array/string fields have defaults so downstream
 * components never crash on undefined.
 */
function normalizePipelineMessage(raw: Record<string, unknown>): PipelineMessage {
  return {
    id: "",
    sourceChannel: "",
    originalText: "",
    translatedText: null,
    mediaUrls: [],
    status: "ingested" as MessageStatus,
    timestamp: Date.now() / 1000,
    contentType: null,
    extractedFacts: null,
    autoTags: null,
    title: null,
    suggestedTemplateId: null,
    suggestedIntelStatus: null,
    formattedOutput: null,
    reviewNotes: null,
    geoContext: null,
    sourceTrust: null,
    relatedMessages: [],
    situationBrief: "",
    ...(raw as object),
  } as PipelineMessage;
}

export const usePipelineStore = create<PipelineStore>((set) => ({
  isRunning: false,
  agents: [
    { id: "agent.ingestion", name: "Ingestion", status: "idle", lastActivity: "", messagesProcessed: 0 },
    { id: "agent.analyst", name: "Analyst", status: "idle", lastActivity: "", messagesProcessed: 0 },
    { id: "agent.reviewer", name: "Reviewer", status: "idle", lastActivity: "", messagesProcessed: 0 },
    { id: "agent.media_handler", name: "Media Handler", status: "idle", lastActivity: "", messagesProcessed: 0 },
    { id: "agent.publisher", name: "Publisher", status: "idle", lastActivity: "", messagesProcessed: 0 },
    { id: "agent.fact_checker", name: "Fact Checker", status: "idle", lastActivity: "", messagesProcessed: 0 },
    { id: "agent.system_daemon", name: "System Daemon", status: "idle", lastActivity: "", messagesProcessed: 0 },
  ],
  messages: [],
  selectedMessageId: null,
  feedStatusFilter: "all",
  latestHealthReport: null,
  daemonInsights: [],
  hfcRunning: false,
  hfcGeoBlocked: false,
  hfcPollerHealthy: true,

  setRunning: (running) => set({ isRunning: running }),

  setFeedStatusFilter: (filter) => set({ feedStatusFilter: filter }),

  selectMessage: (id) => set({ selectedMessageId: id }),

  clearAllMessages: () =>
    set({ messages: [], selectedMessageId: null }),

  removeMessage: (id) =>
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== id),
      selectedMessageId: state.selectedMessageId === id ? null : state.selectedMessageId,
    })),

  updateFromEvent: (event) => {
    const type = event.type as string;

    switch (type) {
      case "agent_status":
        set((state) => ({
          agents: state.agents.map((a) =>
            a.name === event.agent
              ? {
                  ...a,
                  status: event.status as AgentStatus,
                  lastActivity: (event.activity as string) || a.lastActivity,
                  messagesProcessed: a.messagesProcessed + ((event.messagesProcessed as number) || 0),
                }
              : a,
          ),
        }));
        break;

      case "new_message": {
        const incoming = normalizePipelineMessage(event.message as Record<string, unknown>);
        set((state) => {
          const idx = state.messages.findIndex((m) => m.id === incoming.id);
          if (idx !== -1) {
            // Upsert: wave-coalesced HFC alerts re-emit the same feed_id
            const updated = [...state.messages];
            updated[idx] = { ...updated[idx], ...incoming };
            return { messages: updated };
          }
          return {
            messages: [incoming, ...state.messages].slice(0, 200),
          };
        });
        break;
      }

      case "message_update": {
        const updateMsgId = event.message_id as string;
        const updates = event.updates as Record<string, unknown> | undefined;
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === updateMsgId
              ? { ...m, ...(updates as object) }
              : m,
          ),
        }));
        // If status just changed to "reviewing" but translatedText is missing,
        // the enriched WS event was likely corrupted — fetch via REST
        if (updates?.status === "reviewing") {
          setTimeout(() => {
            const msg = usePipelineStore.getState().messages.find((m) => m.id === updateMsgId);
            if (msg && !msg.translatedText) {
              _fetchEnrichedFallback(updateMsgId, set);
            }
          }, 800);
        }
        break;
      }

      case "review_request": {
        const reviewMsgId = (event.message_id as string) || (event.message as Record<string, unknown>)?.id as string;
        const reviewPayload = event.message as Record<string, unknown> | undefined;

        set((state) => {
          const exists = state.messages.some((m) => m.id === reviewMsgId);
          const busy = _isUserBusy(state);

          if (exists && reviewPayload) {
            return {
              messages: state.messages.map((m) =>
                m.id === reviewMsgId
                  ? {
                      ...m,
                      status: "reviewing" as MessageStatus,
                      translatedText: (reviewPayload.translatedText as string) ?? m.translatedText,
                      extractedFacts: (reviewPayload.extractedFacts as ExtractedFact[]) ?? m.extractedFacts,
                      autoTags: (reviewPayload.autoTags as AutoTags) ?? m.autoTags,
                      title: (reviewPayload.title as string) ?? m.title,
                      suggestedTemplateId: (reviewPayload.suggestedTemplateId as string) ?? m.suggestedTemplateId,
                      suggestedIntelStatus: (reviewPayload.suggestedIntelStatus as string) ?? m.suggestedIntelStatus,
                      formattedOutput: (reviewPayload.formattedOutput as string) ?? m.formattedOutput,
                      mediaUrls: (reviewPayload.mediaUrls as string[]) ?? m.mediaUrls,
                    }
                  : m,
              ),
              // Only auto-select if user is NOT currently reviewing another message
              selectedMessageId: busy ? state.selectedMessageId : reviewMsgId,
            };
          } else if (reviewPayload) {
            return {
              messages: [normalizePipelineMessage(reviewPayload), ...state.messages].slice(0, 200),
              selectedMessageId: busy ? state.selectedMessageId : reviewMsgId,
            };
          }

          return state;
        });

        // REST fallback: if the WS enriched data was corrupted/lost, fetch via REST.
        // Deferred to let any pending WS events settle first.
        if (reviewMsgId) {
          setTimeout(() => {
            const msg = usePipelineStore.getState().messages.find((m) => m.id === reviewMsgId);
            if (msg && msg.status === "reviewing" && !msg.translatedText) {
              _fetchEnrichedFallback(reviewMsgId, set);
            }
          }, 500);
        }
        break;
      }

      case "message_delete": {
        const deleteId = event.message_id as string;
        set((state) => ({
          messages: state.messages.filter((m) => m.id !== deleteId),
          selectedMessageId: state.selectedMessageId === deleteId ? null : state.selectedMessageId,
        }));
        break;
      }

      case "pipeline_status":
        set({ isRunning: event.running as boolean });
        break;

      case "health_report":
        set({
          latestHealthReport: {
            timestamp: event.timestamp as number,
            services: event.services as Record<string, string>,
            error_counts: event.error_counts as Record<string, number>,
          },
        });
        break;

      case "daemon_insight":
        set((state) => ({
          daemonInsights: [
            {
              timestamp: event.timestamp as number,
              agent: event.agent as string,
              error: event.error as string,
              suggestion: event.suggestion as string,
            },
            ...state.daemonInsights,
          ].slice(0, 50),
        }));
        break;

      case "hfc_status":
        set({
          hfcRunning: event.running as boolean,
          hfcGeoBlocked: event.geo_blocked as boolean,
          hfcPollerHealthy: (event.poller_healthy as boolean) ?? true,
        });
        break;
    }
  },
}));
