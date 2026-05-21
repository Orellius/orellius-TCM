import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { usePipelineStore, type MessageStatus, type PipelineMessage } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

const PAGE_SIZE = 8;

type ThreatFilter = "all" | "critical" | "high" | "medium" | "low" | "info";
type SourceFilter = "channels" | "hfc" | "all";

const STATUS_STYLES: Record<MessageStatus, { dot: string; text: string }> = {
  ingested: { dot: "bg-blue-400", text: "text-blue-400" },
  translating: { dot: "bg-amber-400 animate-pulse", text: "text-amber-400" },
  enriching: { dot: "bg-teal-400 animate-pulse", text: "text-teal-400" },
  reviewing: { dot: "bg-yellow-400 animate-pulse", text: "text-yellow-400" },
  processing_media: { dot: "bg-purple-400 animate-pulse", text: "text-purple-400" },
  publishing: { dot: "bg-cyan-400 animate-pulse", text: "text-cyan-400" },
  published: { dot: "bg-green-400", text: "text-green-400" },
  failed: { dot: "bg-red-500", text: "text-red-400" },
  publish_failed: { dot: "bg-red-500 animate-pulse", text: "text-red-400" },
  fact_checking: { dot: "bg-orange-400 animate-pulse", text: "text-orange-400" },
  archived: { dot: "bg-gray-500", text: "text-gray-400" },
};

const THREAT_BORDER: Record<string, string> = {
  critical: "border-s-red-500",
  high: "border-s-amber-500",
  medium: "border-s-blue-500",
  low: "border-s-green-500",
  info: "border-s-gray-500",
};

const THREAT_BADGE: Record<string, string> = {
  critical: "bg-red-600/20 text-red-400",
  high: "bg-amber-600/20 text-amber-400",
  medium: "bg-blue-600/20 text-blue-400",
  low: "bg-green-600/20 text-green-400",
  info: "bg-gray-600/20 text-gray-400",
};

const CONTENT_TYPE_BADGE: Record<string, { bg: string; label_key: string }> = {
  intel: { bg: "bg-emerald-600/20 text-emerald-400", label_key: "content.intel" },
  news: { bg: "bg-sky-600/20 text-sky-400", label_key: "content.news" },
  editorial: { bg: "bg-violet-600/20 text-violet-400", label_key: "content.editorial" },
  advertisement: { bg: "bg-orange-600/20 text-orange-400", label_key: "content.ad" },
  spam: { bg: "bg-red-600/20 text-red-400", label_key: "content.spam" },
};

/** Check if a status counts as "in progress" (pipeline working on it). */
function isInProgress(s: MessageStatus): boolean {
  return s === "ingested" || s === "translating" || s === "enriching" || s === "fact_checking" || s === "processing_media" || s === "publishing";
}

/** Check if a message is empty/junk (no useful content). */
function isEmptyMessage(m: PipelineMessage): boolean {
  const hasText = !!(m.originalText?.trim() || m.translatedText?.trim());
  const hasMedia = (m.mediaUrls?.length ?? 0) > 0;
  const hasTitle = !!m.title?.trim();
  // Only filter if there's literally nothing AND it's past ingestion
  // (don't filter messages still being processed — they may get content)
  if (isInProgress(m.status)) return false;
  return !hasText && !hasMedia && !hasTitle;
}

export function MessageFeed() {
  const allMessages = usePipelineStore((s) => s.messages);
  const selectedId = usePipelineStore((s) => s.selectedMessageId);
  const selectMessage = usePipelineStore((s) => s.selectMessage);
  const lang = useSettingsStore((s) => s.language);

  const statusFilter = usePipelineStore((s) => s.feedStatusFilter);
  const setStatusFilter = usePipelineStore((s) => s.setFeedStatusFilter);
  const [threatFilter, setThreatFilter] = useState<ThreatFilter>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("channels");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false);
  const bulkMenuRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Close bulk menu on click outside
  useEffect(() => {
    if (!bulkMenuOpen) return;
    const handler = (e: MouseEvent) => {
      if (bulkMenuRef.current && !bulkMenuRef.current.contains(e.target as Node)) {
        setBulkMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [bulkMenuOpen]);

  // Filter out archived + empty junk, then apply user filters
  const messages = useMemo(() => {
    let filtered = allMessages.filter((m) => m.status !== "archived" && !isEmptyMessage(m));

    // Source filter: separate HFC alerts from channel messages
    if (sourceFilter === "channels") {
      filtered = filtered.filter((m) => !m.hfcAlert);
    } else if (sourceFilter === "hfc") {
      filtered = filtered.filter((m) => m.hfcAlert === true);
    }

    if (statusFilter !== "all") {
      if (statusFilter === "in_progress") {
        filtered = filtered.filter((m) => isInProgress(m.status));
      } else {
        filtered = filtered.filter((m) => m.status === statusFilter);
      }
    }

    if (threatFilter !== "all") {
      filtered = filtered.filter((m) => m.autoTags?.threat_level === threatFilter);
    }

    return filtered;
  }, [allMessages, statusFilter, threatFilter, sourceFilter]);

  // Counts for filter badges
  const counts = useMemo(() => {
    const active = allMessages.filter((m) => m.status !== "archived" && !isEmptyMessage(m));
    const channels = active.filter((m) => !m.hfcAlert);
    const hfc = active.filter((m) => m.hfcAlert === true);
    return {
      all: active.length,
      channels: channels.length,
      hfc: hfc.length,
      reviewing: active.filter((m) => m.status === "reviewing").length,
      in_progress: active.filter((m) => isInProgress(m.status)).length,
      published: active.filter((m) => m.status === "published").length,
      failed: active.filter((m) => m.status === "failed").length,
    };
  }, [allMessages]);

  // Reset visible count when messages list shrinks
  useEffect(() => {
    if (visibleCount > messages.length && messages.length <= PAGE_SIZE) {
      setVisibleCount(PAGE_SIZE);
    }
  }, [messages.length, visibleCount]);

  // IntersectionObserver to load more when sentinel becomes visible
  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelCallback = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) observerRef.current.disconnect();
      if (!node) return;

      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting) {
            setVisibleCount((prev) => Math.min(prev + PAGE_SIZE, messages.length));
          }
        },
        { root: scrollRef.current, threshold: 0.1 },
      );
      observerRef.current.observe(node);
    },
    [messages.length],
  );

  const visibleMessages = messages.slice(0, visibleCount);
  const hasMore = visibleCount < messages.length;

  const clearAllMessages = usePipelineStore((s) => s.clearAllMessages);

  const handleBulkArchive = async () => {
    const ids = allMessages.filter((m) => m.status !== "archived").map((m) => m.id);
    if (!ids.length) return;
    setBulkMenuOpen(false);
    // Immediately clear from UI for responsiveness
    clearAllMessages();
    try {
      await api.bulkArchive(ids);
    } catch (e) {
      console.error("Bulk archive failed:", e);
    }
  };


  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-[var(--border-color)] px-3 py-2.5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t("feed.title", lang)}
          </h2>
          <div className="flex items-center gap-1.5">
            {counts.reviewing > 0 && (
              <span className="flex items-center gap-1 rounded-full bg-yellow-500/20 px-2 py-0.5 text-[10px] font-medium text-yellow-400">
                <span className="h-1.5 w-1.5 rounded-full bg-yellow-400 animate-pulse" />
                {counts.reviewing}
              </span>
            )}
            {/* Bulk actions menu */}
            {counts.all > 0 && (
              <div className="relative" ref={bulkMenuRef}>
                <button
                  onClick={() => setBulkMenuOpen((p) => !p)}
                  className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                  title={t("feed.bulk_actions", lang)}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                    <path d="M8 2a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM8 6.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM9.5 12.5a1.5 1.5 0 1 0-3 0 1.5 1.5 0 0 0 3 0Z" />
                  </svg>
                </button>
                {bulkMenuOpen && (
                  <div className="absolute end-0 top-full z-20 mt-1 w-44 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] shadow-lg">
                    <button
                      onClick={handleBulkArchive}
                      className="w-full px-3 py-2 text-start text-xs font-medium text-amber-400 hover:bg-[var(--bg-tertiary)] transition-colors first:rounded-t-lg last:rounded-b-lg"
                    >
                      {t("feed.archive_all", lang)}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Source tabs: Channels / HFC Alerts / All */}
        <div className="flex rounded-md bg-[var(--bg-tertiary)] p-0.5 mb-2">
          {([
            { key: "channels" as SourceFilter, label: t("feed.source.channels", lang), count: counts.channels },
            { key: "hfc" as SourceFilter, label: t("feed.source.hfc", lang), count: counts.hfc },
            { key: "all" as SourceFilter, label: t("feed.source.all", lang), count: counts.all },
          ]).map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setSourceFilter(key)}
              className={`flex-1 rounded px-2 py-1 text-[10px] font-medium transition-colors ${
                sourceFilter === key
                  ? key === "hfc"
                    ? "bg-red-600 text-white"
                    : "bg-[var(--accent-blue)] text-white"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              {label}{count > 0 ? ` (${count})` : ""}
            </button>
          ))}
        </div>

        {/* Status filter chips */}
        <div className="flex flex-wrap gap-1">
          <FilterChip
            label={t("feed.filter.all", lang)}
            count={counts.all}
            active={statusFilter === "all"}
            onClick={() => setStatusFilter("all")}
          />
          <FilterChip
            label={t("feed.filter.reviewing", lang)}
            count={counts.reviewing}
            active={statusFilter === "reviewing"}
            onClick={() => setStatusFilter("reviewing")}
            color="yellow"
          />
          <FilterChip
            label={t("feed.filter.in_progress", lang)}
            count={counts.in_progress}
            active={statusFilter === "in_progress"}
            onClick={() => setStatusFilter("in_progress")}
            color="blue"
          />
          <FilterChip
            label={t("feed.filter.published", lang)}
            count={counts.published}
            active={statusFilter === "published"}
            onClick={() => setStatusFilter("published")}
            color="green"
          />
          <FilterChip
            label={t("feed.filter.failed", lang)}
            count={counts.failed}
            active={statusFilter === "failed"}
            onClick={() => setStatusFilter("failed")}
            color="red"
          />
        </div>

        {/* Threat level filter (only for channel messages) */}
        {sourceFilter !== "hfc" && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {(["all", "critical", "high", "medium", "low"] as ThreatFilter[]).map((level) => (
              <button
                key={level}
                onClick={() => setThreatFilter(level === threatFilter ? "all" : level)}
                className={`rounded px-1.5 py-0.5 text-[9px] font-medium transition-colors ${
                  threatFilter === level
                    ? level === "all"
                      ? "bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
                      : `${THREAT_BADGE[level]}`
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                }`}
              >
                {level === "all"
                  ? t("feed.threat.all", lang)
                  : t(`tag.threat.${level}`, lang)}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Message list */}
      <div ref={scrollRef} className="flex-1 overflow-auto">
        {messages.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-[var(--text-secondary)]">
            {statusFilter !== "all" || threatFilter !== "all"
              ? t("feed.no_match", lang)
              : t("feed.empty", lang)}
          </p>
        ) : (
          <div className="divide-y divide-[var(--border-color)]">
            {visibleMessages.map((msg) => (
              <MessageCard
                key={msg.id}
                msg={msg}
                isSelected={msg.id === selectedId}
                lang={lang}
                onSelect={() => selectMessage(msg.id === selectedId ? null : msg.id)}
              />
            ))}

            {hasMore && (
              <div
                ref={sentinelCallback}
                className="flex items-center justify-center py-3"
              >
                <span className="text-[10px] text-[var(--text-secondary)]">
                  {lang === "he"
                    ? `עוד ${messages.length - visibleCount} הודעות...`
                    : `${messages.length - visibleCount} more...`}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Message card ───────────────────────────────────────────── */

function MessageCard({
  msg,
  isSelected,
  lang,
  onSelect,
}: {
  msg: PipelineMessage;
  isSelected: boolean;
  lang: "he" | "en";
  onSelect: () => void;
}) {
  const style = STATUS_STYLES[msg.status] ?? STATUS_STYLES.ingested;
  const isReview = msg.status === "reviewing";
  const isHfcAlert = msg.hfcAlert === true;
  const threat = msg.autoTags?.threat_level;
  const threatBorder = threat ? THREAT_BORDER[threat] ?? "border-s-transparent" : "border-s-transparent";

  const time = new Date(msg.timestamp * 1000).toLocaleTimeString(
    lang === "he" ? "he-IL" : "en-US",
    { hour: "2-digit", minute: "2-digit" },
  );

  return (
    <button
      onClick={onSelect}
      className={`w-full px-4 py-3 text-start transition-colors border-s-2 ${
        isSelected
          ? "bg-[var(--accent-blue)]/15 border-s-[var(--accent-blue)]"
          : isReview
            ? `bg-yellow-500/5 hover:bg-yellow-500/10 ${isHfcAlert ? "border-s-red-500" : threatBorder}`
            : `hover:bg-[var(--bg-tertiary)] ${isHfcAlert ? "border-s-red-500" : threatBorder}`
      }`}
    >
      {/* Row 1: channel + threat + time */}
      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
          {msg.sourceTrust && (
            <TrustDot level={msg.sourceTrust.trust_level} />
          )}
          <span className="truncate text-xs font-medium text-[var(--text-primary)]">
            {msg.sourceChannel}
          </span>
          {isHfcAlert && (
            <span className="rounded-full bg-red-600/20 px-1.5 py-0.5 text-[9px] font-bold text-red-400">
              {t("hfc.alert_badge", lang)}
            </span>
          )}
          {msg.geoContext?.countries && msg.geoContext.countries.length > 0 && (
            <span className="text-[10px] shrink-0">
              {msg.geoContext.countries.map((c: { flag: string }) => c.flag).join("")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {threat && threat !== "info" && (
            <span className={`rounded px-1 py-px text-[8px] font-bold uppercase ${THREAT_BADGE[threat] ?? ""}`}>
              {t(`tag.threat.${threat}`, lang)}
            </span>
          )}
          <span className="text-[10px] text-[var(--text-secondary)]">{time}</span>
        </div>
      </div>

      {/* Row 2: title or preview */}
      {msg.title ? (
        <p className="mt-1 truncate text-xs font-semibold text-[var(--text-primary)]" dir="auto">
          {msg.title}
        </p>
      ) : (
        <p className="mt-1 line-clamp-2 text-xs text-[var(--text-secondary)]" dir="auto">
          {msg.translatedText || msg.originalText}
        </p>
      )}

      {/* Row 3: status + content type + event type + media indicator */}
      <div className="mt-1 flex items-center justify-between gap-1">
        <span className={`text-[10px] font-medium ${style.text}`}>
          {t(`feed.status.${msg.status}`, lang)}
        </span>
        <div className="flex items-center gap-1">
          {msg.contentType && CONTENT_TYPE_BADGE[msg.contentType] && (
            <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${CONTENT_TYPE_BADGE[msg.contentType].bg}`}>
              {t(CONTENT_TYPE_BADGE[msg.contentType].label_key, lang)}
            </span>
          )}
          {(msg.mediaUrls?.length ?? 0) > 0 && (
            <span className="inline-flex items-center gap-0.5 text-amber-400" title="Has media">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                <path fillRule="evenodd" d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4Zm10.5 5.707a.5.5 0 0 0-.146-.353l-2.5-2.5a.5.5 0 0 0-.708 0L7.5 8.5 6.354 7.354a.5.5 0 0 0-.708 0l-2.5 2.5A.5.5 0 0 0 3.5 10.5v1a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5v-1.293ZM6.5 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
              </svg>
              <span className="text-[9px] font-medium">{msg.mediaUrls!.length}</span>
            </span>
          )}
          {msg.autoTags?.event_type && (
            <span className="rounded-full bg-blue-600/20 px-1.5 py-0.5 text-[9px] font-medium text-blue-400">
              {t(`tag.event.${msg.autoTags.event_type}`, lang)}
            </span>
          )}
          {msg.factCheck?.flagged && (
            <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${
              msg.factCheck.risk_level === "high"
                ? "bg-red-600/20 text-red-400"
                : "bg-amber-600/20 text-amber-400"
            }`}>
              {t("factcheck.flagged_badge", lang)}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

/* ── Trust dot ─────────────────────────────────────────────── */

const TRUST_DOT_COLORS: Record<string, string> = {
  verified: "bg-green-400",
  trusted: "bg-emerald-400",
  neutral: "bg-gray-400",
  suspect: "bg-amber-400",
  untrusted: "bg-red-400",
};

function TrustDot({ level }: { level: string }) {
  const color = TRUST_DOT_COLORS[level] ?? TRUST_DOT_COLORS.neutral;
  return (
    <span
      className={`h-1.5 w-1.5 shrink-0 rounded-full ${color}`}
      title={`Trust: ${level}`}
    />
  );
}

/* ── Filter chip ────────────────────────────────────────────── */

function FilterChip({
  label,
  count,
  active,
  onClick,
  color,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  color?: "yellow" | "green" | "red" | "blue";
}) {
  const colorClasses = {
    yellow: active ? "bg-yellow-500/20 text-yellow-400" : "",
    green: active ? "bg-green-500/20 text-green-400" : "",
    red: active ? "bg-red-500/20 text-red-400" : "",
    blue: active ? "bg-blue-500/20 text-blue-400" : "",
  };

  return (
    <button
      onClick={onClick}
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors ${
        active
          ? color
            ? colorClasses[color]
            : "bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
          : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
      }`}
    >
      {label}
      {count > 0 && (
        <span className="ms-1 opacity-70">{count}</span>
      )}
    </button>
  );
}

