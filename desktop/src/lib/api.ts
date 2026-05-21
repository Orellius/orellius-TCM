const API_BASE = (import.meta.env.VITE_API_BASE as string) ?? "http://127.0.0.1:8000/api";

const DEFAULT_TIMEOUT = 30_000;

/** Get stored auth token (empty = dev mode, no auth needed). */
function getToken(): string {
  return localStorage.getItem("orellius_api_token") ?? "";
}

async function request<T>(path: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT, ...fetchOptions } = options ?? {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers,
      ...fetchOptions,
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    return res.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`Request to ${path} timed out after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  getTelegramStatus: () =>
    request<{
      connected: boolean;
      auth_state: string;
      user: { id: number; first_name: string; last_name: string; phone: string; username: string } | null;
    }>("/telegram/status"),

  startPipeline: () => request<{ ok: boolean; error?: string }>("/pipeline/start", { method: "POST" }),

  stopPipeline: () => request<{ ok: boolean }>("/pipeline/stop", { method: "POST" }),

  getStatus: () =>
    request<{
      running: boolean;
      agents: Record<string, string>;
      queue_size: number;
    }>("/pipeline/status"),

  approveMessage: (messageId: string, editedText?: string, includedMedia?: string[]) =>
    request<{ ok: boolean; error?: string }>(`/review/${messageId}/approve`, {
      method: "POST",
      body: JSON.stringify({
        edited_text: editedText,
        included_media: includedMedia,
      }),
    }),

  rejectMessage: (messageId: string) => request<{ ok: boolean }>(`/review/${messageId}/reject`, { method: "POST" }),

  archiveMessage: (messageId: string) => request<{ ok: boolean }>(`/review/${messageId}/archive`, { method: "POST" }),

  restoreMessage: (messageId: string) => request<{ ok: boolean }>(`/review/${messageId}/restore`, { method: "POST" }),

  deleteMessage: (messageId: string) => request<{ ok: boolean }>(`/review/${messageId}`, { method: "DELETE" }),

  acknowledgeDisinfo: (messageId: string) =>
    request<{ ok: boolean; error?: string }>(`/review/${messageId}/acknowledge-disinfo`, { method: "POST" }),

  bulkArchive: (messageIds: string[]) =>
    request<{ ok: boolean; count: number }>("/review/bulk/archive", {
      method: "POST",
      body: JSON.stringify({ message_ids: messageIds }),
    }),

  bulkDelete: (messageIds: string[]) =>
    request<{ ok: boolean; count: number }>("/review/bulk/delete", {
      method: "POST",
      body: JSON.stringify({ message_ids: messageIds }),
    }),

  getTemplates: () =>
    request<{
      templates: Array<{
        id: string;
        name_en: string;
        name_he: string;
        matching_event_types: string[];
        matching_threat_levels: string[];
        priority: number;
      }>;
    }>("/templates"),

  applyTemplate: (
    messageId: string,
    templateId: string,
    messageData: {
      translated_text: string;
      extracted_facts: Array<{ fact: string; category: string }>;
      auto_tags: { event_type: string; region: string; threat_level: string; entities: string[] } | null;
      timestamp: number | null;
      title: string;
      intel_status: string;
    },
  ) =>
    request<{ ok: boolean; formatted_output: string }>(`/review/${messageId}/apply-template`, {
      method: "POST",
      body: JSON.stringify({ template_id: templateId, ...messageData }),
    }),

  createTemplate: (data: Record<string, unknown>) =>
    request<{ ok: boolean; template: Record<string, unknown> }>("/templates", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateTemplate: (templateId: string, data: Record<string, unknown>) =>
    request<{ ok: boolean; template: Record<string, unknown> }>(`/templates/${encodeURIComponent(templateId)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteTemplate: (templateId: string) =>
    request<{ ok: boolean }>(`/templates/${encodeURIComponent(templateId)}`, { method: "DELETE" }),

  resetTemplates: () =>
    request<{ ok: boolean; templates: unknown[] }>("/templates/reset", { method: "POST" }),

  resetTaxonomies: () =>
    request<{ ok: boolean; event_types: unknown[]; threat_levels: unknown[] }>("/taxonomies/reset", { method: "POST" }),

  // Phrase replacements
  getReplacements: () =>
    request<{ replacements: Array<{ find: string; replace: string; enabled: boolean }> }>("/replacements"),

  addReplacement: (find: string, replace: string) =>
    request<{ ok: boolean }>("/replacements", {
      method: "POST",
      body: JSON.stringify({ find, replace, enabled: true }),
    }),

  updateReplacement: (index: number, data: { find?: string; replace?: string; enabled?: boolean }) =>
    request<{ ok: boolean }>(`/replacements/${index}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteReplacement: (index: number) =>
    request<{ ok: boolean }>(`/replacements/${index}`, { method: "DELETE" }),

  getLogs: (limit = 200, level?: string) =>
    request<{
      entries: Array<{
        timestamp: number;
        level: string;
        logger: string;
        message: string;
        exc_info?: string;
      }>;
    }>(`/logs?limit=${limit}${level ? `&level=${level}` : ""}`),

  clearLogs: () => request<{ ok: boolean }>("/logs", { method: "DELETE" }),

  getChannels: () => request<{ channels: string[] }>("/channels"),

  addChannel: (channel: string) =>
    request<{ ok: boolean }>("/channels", {
      method: "POST",
      body: JSON.stringify({ channel }),
    }),

  removeChannel: (channel: string) => request<{ ok: boolean }>(`/channels/${encodeURIComponent(channel)}`, { method: "DELETE" }),

  getSettings: () =>
    request<{
      publish_delay: number;
      auto_publish: boolean;
      stamp_enabled: boolean;
      stamp_image_path: string;
      stamp_opacity: number;
      stamp_size_pct: number;
      stamp_position: string;
      target_channel: string;
      watermark_removal_enabled: boolean;
      watermark_confidence_threshold: number;
      ghost_mode_enabled: boolean;
      suppress_read_receipts: boolean;
      suppress_online_status: boolean;
      keyword_filter_enabled: boolean;
      dedup_enabled: boolean;
      priority_keywords: string;
      channel_signature: string;
      fact_check_enabled: boolean;
    }>("/settings"),

  updateSettings: (body: Record<string, unknown>) =>
    request<{ ok: boolean }>("/settings", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  // Watermark references
  getWatermarkRefs: () =>
    request<{
      references: Array<{ channel: string; filename: string; path: string }>;
    }>("/watermark/references"),

  addWatermarkRef: (channel: string, image: string, filename: string) =>
    request<{ ok: boolean; path: string }>("/watermark/add-reference", {
      method: "POST",
      body: JSON.stringify({ channel, image, filename }),
    }),

  deleteWatermarkRef: (channel: string, filename: string) =>
    request<{ ok: boolean }>("/watermark/reference", {
      method: "DELETE",
      body: JSON.stringify({ channel, filename }),
    }),

  // Ghost Mode
  enableGhost: () => request<{ ok: boolean; status?: Record<string, unknown> }>("/ghost/enable", { method: "POST" }),
  disableGhost: () => request<{ ok: boolean }>("/ghost/disable", { method: "POST" }),
  getGhostStatus: () => request<{ enabled: boolean }>("/ghost/status"),

  // Channel Intelligence
  discoverChannels: (seedChannel: string, depth = 1) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<{ ok: boolean; channels: any[] }>("/channels/discover", {
      method: "POST",
      body: JSON.stringify({ seed_channel: seedChannel, depth }),
    }),

  profileChannel: (channel: string) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<{ ok: boolean; profile: any }>("/channels/profile", {
      method: "POST",
      body: JSON.stringify({ channel }),
    }),

  scrapeChannel: (channel: string, limit?: number) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<{ ok: boolean; messages: any[] }>("/channels/scrape", {
      method: "POST",
      body: JSON.stringify({ channel, limit }),
    }),

  getChannelProfiles: () =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    request<{ profiles: Record<string, any> }>("/channels/profiles"),

  // Pre-Processing Keywords
  getKeywords: () => request<{ keywords: string[]; raw: string }>("/preprocess/keywords"),

  updateKeywords: (keywords: string) =>
    request<{ ok: boolean }>("/preprocess/keywords", {
      method: "PUT",
      body: JSON.stringify({ keywords }),
    }),

  // Raw Metadata
  getRawMetadata: (messageId: string) =>
    request<{ ok: boolean; raw_metadata: Record<string, unknown> | null; preprocess_meta: Record<string, unknown> | null }>(
      `/messages/${messageId}/raw`,
    ),

  // Enriched data (REST fallback when WS delivery fails)
  getEnrichedData: (messageId: string) =>
    request<Record<string, unknown>>(`/messages/${messageId}/enriched`),

  // Event Types (taxonomies)
  getEventTypes: () =>
    request<{ event_types: Array<{ key: string; name_en: string; name_he: string }> }>("/event-types"),

  createEventType: (data: { key: string; name_en: string; name_he: string }) =>
    request<{ ok: boolean }>("/event-types", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateEventType: (key: string, data: Partial<{ key: string; name_en: string; name_he: string }>) =>
    request<{ ok: boolean }>(`/event-types/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteEventType: (key: string) =>
    request<{ ok: boolean }>(`/event-types/${encodeURIComponent(key)}`, { method: "DELETE" }),

  // Threat Levels (taxonomies)
  getThreatLevels: () =>
    request<{ threat_levels: Array<{ key: string; name_en: string; name_he: string }> }>("/threat-levels"),

  createThreatLevel: (data: { key: string; name_en: string; name_he: string }) =>
    request<{ ok: boolean }>("/threat-levels", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateThreatLevel: (key: string, data: Partial<{ key: string; name_en: string; name_he: string }>) =>
    request<{ ok: boolean }>(`/threat-levels/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteThreatLevel: (key: string) =>
    request<{ ok: boolean }>(`/threat-levels/${encodeURIComponent(key)}`, { method: "DELETE" }),

  // Template reorder
  reorderTemplates: (orderedIds: string[]) =>
    request<{ ok: boolean }>("/templates/reorder", {
      method: "PUT",
      body: JSON.stringify({ ordered_ids: orderedIds }),
    }),

  // Pikud HaOref (HFC) Alerts
  hfcStart: () => request<{ ok: boolean }>("/hfc/start", { method: "POST" }),

  hfcStop: () => request<{ ok: boolean }>("/hfc/stop", { method: "POST" }),

  hfcStatus: () =>
    request<{
      running: boolean;
      geo_blocked: boolean;
      last_poll: number | null;
      alert_count: number;
      poller_healthy: boolean;
      avg_response_ms: number;
      polls_total: number;
    }>("/hfc/status"),

  hfcTest: () =>
    request<{ ok: boolean; connected: boolean; geo_blocked?: boolean; error?: string }>("/hfc/test", { method: "POST" }),

  hfcTestMock: () =>
    request<{ ok: boolean; published: boolean; publish_error?: string; formatted: string; telegram_msg_ids?: number[] }>("/hfc/test-mock", { method: "POST" }),

  hfcDeleteMock: () =>
    request<{ ok: boolean; deleted_count: number; message?: string }>("/hfc/test-mock", { method: "DELETE" }),

  getHfcTemplates: () =>
    request<{
      templates: Record<string, { category: string; name_he: string; emoji: string; template_body: string }>;
    }>("/hfc/templates"),

  updateHfcTemplate: (category: string, body: { template_body: string }) =>
    request<{ ok: boolean }>(`/hfc/templates/${encodeURIComponent(category)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
};
