import { useState, useEffect, useRef, useCallback } from "react";
import { usePipelineStore, type PipelineMessage } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { api } from "../lib/api";
import { t, translateRegion, REGION_KEYS, type Lang } from "../lib/i18n";
import { COUNTRY_NAMES } from "../lib/countries";
import { MediaLightbox } from "./MediaLightbox";
import { DossierSkeleton } from "./Skeleton";
import { RawMetadataViewer } from "./RawMetadataViewer";
import { TelegramEditor } from "./TelegramEditor";

// ── Tag Chips ────────────────────────────────────────────────

function TagChip({ label, color = "bg-gray-700" }: { label: string; color?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full ${color} px-2.5 py-0.5 text-xs font-medium text-white`}>
      {label}
    </span>
  );
}

const THREAT_COLORS: Record<string, string> = {
  critical: "bg-red-600",
  high: "bg-amber-600",
  medium: "bg-blue-600",
  low: "bg-green-600",
  info: "bg-gray-500",
};

function ThreatLevelChip({ level, lang }: { level: string; lang: Lang }) {
  const color = THREAT_COLORS[level] || "bg-gray-500";
  return <TagChip label={t(`tag.threat.${level}`, lang)} color={color} />;
}

// ── Intel Status Options ─────────────────────────────────────

const INTEL_STATUSES = [
  { value: "verified", labelKey: "intel_status.verified" },
  { value: "non_official", labelKey: "intel_status.non_official" },
  { value: "foreign_sources", labelKey: "intel_status.foreign_sources" },
];

// ── Status Bar ───────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  ingested: "text-blue-400 bg-blue-500/10",
  translating: "text-amber-400 bg-amber-500/10",
  enriching: "text-teal-400 bg-teal-500/10",
  fact_checking: "text-orange-400 bg-orange-500/10",
  reviewing: "text-yellow-400 bg-yellow-500/10",
  processing_media: "text-purple-400 bg-purple-500/10",
  publishing: "text-cyan-400 bg-cyan-500/10",
  published: "text-green-400 bg-green-500/10",
  failed: "text-red-400 bg-red-500/10",
  publish_failed: "text-red-400 bg-red-500/10",
  archived: "text-gray-400 bg-gray-500/10",
};

// ── Template type ────────────────────────────────────────────

interface TemplateOption {
  id: string;
  name_en: string;
  name_he: string;
}

// ── Uploaded media item ──────────────────────────────────────

interface UploadedMedia {
  id: string;
  file: File;
  previewUrl: string;
}

// ── Main Dossier ─────────────────────────────────────────────

export function MessageDossier() {
  const selectedId = usePipelineStore((s) => s.selectedMessageId);
  const messages = usePipelineStore((s) => s.messages);
  const lang = useSettingsStore((s) => s.language);

  const message = messages.find((m) => m.id === selectedId) ?? null;

  if (!message) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="mb-2 text-3xl opacity-20">📋</div>
          <p className="text-sm text-[var(--text-secondary)]">{t("dossier.empty", lang)}</p>
        </div>
      </div>
    );
  }

  // Show skeleton ONLY if the message has no usable content yet.
  // Otherwise, show the dossier view with a processing banner.
  const isProcessing = message.status === "ingested" || message.status === "translating" || message.status === "enriching" || message.status === "fact_checking";
  const hasContent = !!(message.originalText?.trim() || message.translatedText?.trim() || (message.mediaUrls?.length ?? 0) > 0 || message.title?.trim());

  if (isProcessing && !hasContent) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border-color)] px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-400 animate-pulse">
              {t(`feed.status.${message.status}`, lang)}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              {message.sourceChannel}
            </span>
          </div>
          <span className="font-mono text-[10px] text-[var(--text-secondary)]">
            {message.id.slice(0, 8)}
          </span>
        </div>
        <DossierSkeleton />
      </div>
    );
  }

  return <DossierView message={message} lang={lang} isProcessing={isProcessing} />;
}

// ── Collapsible Section ─────────────────────────────────────

function DossierSection({
  id,
  title,
  defaultOpen = true,
  children,
}: {
  id: string;
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const storageKey = `dossier_section_${id}`;
  const [open, setOpen] = useState(() => {
    const saved = localStorage.getItem(storageKey);
    return saved !== null ? saved === "true" : defaultOpen;
  });

  const toggle = () => {
    const next = !open;
    setOpen(next);
    localStorage.setItem(storageKey, String(next));
  };

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] overflow-hidden">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors"
      >
        {title}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`h-4 w-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        >
          <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
        </svg>
      </button>
      {open && (
        <div className="border-t border-[var(--border-color)] px-4 py-3 space-y-3">
          {children}
        </div>
      )}
    </div>
  );
}

// ── Mini Toggle ─────────────────────────────────────────────

function MiniToggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  label: string;
}) {
  return (
    <label className="inline-flex items-center gap-1.5 cursor-pointer">
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-4 w-7 flex-shrink-0 rounded-full transition-colors ${
          checked ? "bg-[var(--accent-blue)]" : "bg-[var(--bg-tertiary)]"
        }`}
      >
        <span
          className={`absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-3.5" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className="text-[10px] text-[var(--text-secondary)]">{label}</span>
    </label>
  );
}

// ── AI Badge ────────────────────────────────────────────────

function AiBadge() {
  return (
    <span className="inline-flex items-center rounded-full bg-purple-600/20 px-1.5 py-0.5 text-[9px] font-bold text-purple-400">
      AI
    </span>
  );
}

// ── Dossier View ────────────────────────────────────────────

function DossierView({ message, lang, isProcessing = false }: { message: PipelineMessage; lang: Lang; isProcessing?: boolean }) {
  const [editedText, setEditedText] = useState("");
  const [useRichEditor, setUseRichEditor] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isApplyingTemplate, setIsApplyingTemplate] = useState(false);

  // Template dropdown state
  const [templates, setTemplates] = useState<TemplateOption[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [appliedTemplateId, setAppliedTemplateId] = useState<string | null>(null);

  // Editable title (AI-generated, human-editable)
  const [editedTitle, setEditedTitle] = useState("");

  // Intel status selector
  const [intelStatus, setIntelStatus] = useState("");

  // Lightbox state
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);
  // Track which lightbox source (source thumbnails vs post media)
  const [lightboxUrls, setLightboxUrls] = useState<string[]>([]);
  // Watermark before/after toggle
  const [showWmOriginal, setShowWmOriginal] = useState(false);

  // ── Post Media state ───────────────────────────────────
  // Server media included in the post (auto-populated from message.mediaUrls)
  const [includedServerMedia, setIncludedServerMedia] = useState<string[]>([]);
  // Server media that was removed by the operator
  const [excludedServerMedia, setExcludedServerMedia] = useState<string[]>([]);
  // Uploaded media (local files added by user)
  const [uploadedMedia, setUploadedMedia] = useState<UploadedMedia[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Dynamic taxonomy lists
  const [eventTypes, setEventTypes] = useState<Array<{ key: string; name_en: string; name_he: string }>>([]);
  const [threatLevels, setThreatLevels] = useState<Array<{ key: string; name_en: string; name_he: string }>>([]);

  useEffect(() => {
    api.getEventTypes().then((r) => setEventTypes(r.event_types)).catch(() => {});
    api.getThreatLevels().then((r) => setThreatLevels(r.threat_levels)).catch(() => {});
  }, []);

  // Entity toggle state
  const [includeEntities, setIncludeEntities] = useState(true);
  // Track editable tag overrides
  const [editedEventType, setEditedEventType] = useState("");
  const [editedThreatLevel, setEditedThreatLevel] = useState("");
  const [editedRegion, setEditedRegion] = useState("");
  // AI auto-apply ref
  const hasAutoApplied = useRef(false);
  // Guard against stale async template responses when switching messages
  const messageIdRef = useRef(message.id);

  // Fact check / disinformation dialog state
  const [disinfoDialogOpen, setDisinfoDialogOpen] = useState(false);
  const [isAcknowledging, setIsAcknowledging] = useState(false);

  // Load templates once
  useEffect(() => {
    api.getTemplates().then((res) => {
      setTemplates(res.templates as TemplateOption[]);
    }).catch(() => {});
  }, []);

  // Reset state when message changes — auto-populate post media
  useEffect(() => {
    messageIdRef.current = message.id;
    setEditedText(message.formattedOutput || message.translatedText || "");
    setAppliedTemplateId(null);
    setSelectedTemplate("");
    setEditedTitle(message.title || "");
    setIntelStatus("");
    // Auto-include all message media in the post
    setIncludedServerMedia([...(message.mediaUrls ?? [])]);
    setExcludedServerMedia([]);
    setShowWmOriginal(false);
    setIncludeEntities(true);
    setEditedEventType("");
    setEditedThreatLevel("");
    setEditedRegion("");
    hasAutoApplied.current = false;
    // Clean up uploaded media previews
    setUploadedMedia((prev) => {
      prev.forEach((m) => URL.revokeObjectURL(m.previewUrl));
      return [];
    });
  }, [message.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync includedServerMedia when mediaUrls updates (e.g. enriched data arrives
  // after initial render), while respecting user-excluded items
  useEffect(() => {
    const incoming = message.mediaUrls ?? [];
    if (incoming.length === 0) return;
    setIncludedServerMedia((prev) => {
      // If already populated, merge new URLs not explicitly excluded
      if (prev.length > 0) {
        const newUrls = incoming.filter(
          (url) => !prev.includes(url) && !excludedServerMedia.includes(url),
        );
        return newUrls.length > 0 ? [...prev, ...newUrls] : prev;
      }
      // First population — include all
      return [...incoming];
    });
  }, [message.mediaUrls]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-apply AI suggestions when message enters review
  useEffect(() => {
    if (
      message.status === "reviewing" &&
      !hasAutoApplied.current &&
      message.suggestedTemplateId &&
      templates.length > 0
    ) {
      hasAutoApplied.current = true;
      setSelectedTemplate(message.suggestedTemplateId);
      handleApplyTemplate(message.suggestedTemplateId);
      if (message.suggestedIntelStatus) {
        setIntelStatus(message.suggestedIntelStatus);
      }
    }
  }, [message.status, message.suggestedTemplateId, message.suggestedIntelStatus, templates.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      uploadedMedia.forEach((m) => URL.revokeObjectURL(m.previewUrl));
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const hasAutoTags = message.autoTags !== null && message.autoTags !== undefined;
  const hasFacts = message.extractedFacts !== null && message.extractedFacts !== undefined && message.extractedFacts.length > 0;
  const isReviewable = message.status === "reviewing";
  const canArchive = message.status === "failed" || message.status === "published";
  const statusStyle = STATUS_COLORS[message.status] ?? STATUS_COLORS.ingested;

  const hasPostMedia = includedServerMedia.length > 0 || uploadedMedia.length > 0;
  const hasExcluded = excludedServerMedia.length > 0;

  const isFlagged = message.factCheck?.flagged === true;
  const isAcknowledged = message.factCheck?.override_acknowledged === true;
  const disinfoBlocked = isFlagged && !isAcknowledged;

  const time = new Date(message.timestamp * 1000).toLocaleString(
    lang === "he" ? "he-IL" : "en-US",
    { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" },
  );

  const openLightbox = (urls: string[], index: number) => {
    setLightboxUrls(urls);
    setLightboxIndex(index);
    setLightboxOpen(true);
  };

  // ── Post media management ──────────────────────────────

  const removeServerMedia = (url: string) => {
    setIncludedServerMedia((prev) => prev.filter((u) => u !== url));
    setExcludedServerMedia((prev) => [...prev, url]);
  };

  const restoreServerMedia = (url: string) => {
    setExcludedServerMedia((prev) => prev.filter((u) => u !== url));
    setIncludedServerMedia((prev) => [...prev, url]);
  };

  // ── File upload handlers ───────────────────────────────

  const addFiles = useCallback((files: FileList | File[]) => {
    const newItems: UploadedMedia[] = Array.from(files)
      .filter((f) => f.type.startsWith("image/") || f.type.startsWith("video/"))
      .map((file) => ({
        id: crypto.randomUUID(),
        file,
        previewUrl: URL.createObjectURL(file),
      }));
    setUploadedMedia((prev) => [...prev, ...newItems]);
  }, []);

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
      e.target.value = "";
    }
  };

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === "file" && (item.type.startsWith("image/") || item.type.startsWith("video/"))) {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }

    if (files.length > 0) {
      e.preventDefault();
      addFiles(files);
    }
  }, [addFiles]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  }, [addFiles]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const removeUploadedMedia = (id: string) => {
    setUploadedMedia((prev) => {
      const item = prev.find((m) => m.id === id);
      if (item) URL.revokeObjectURL(item.previewUrl);
      return prev.filter((m) => m.id !== id);
    });
  };

  // ── Template data builder ─────────────────────────────

  const getTemplateData = useCallback(() => {
    const tags = message.autoTags ? { ...message.autoTags } : null;
    if (tags) {
      if (editedEventType) tags.event_type = editedEventType;
      if (editedThreatLevel) tags.threat_level = editedThreatLevel;
      if (editedRegion) tags.region = editedRegion;
      if (!includeEntities) tags.entities = [];
    }
    return {
      translated_text: message.translatedText || "",
      extracted_facts: message.extractedFacts || [],
      auto_tags: tags,
      timestamp: message.timestamp ? Math.floor(message.timestamp) : null,
      title: editedTitle,
      intel_status: intelStatus,
    };
  }, [message.autoTags, message.translatedText, message.extractedFacts, message.timestamp, editedTitle, intelStatus, includeEntities, editedEventType, editedThreatLevel, editedRegion]);

  // ── Template & action handlers ─────────────────────────

  const handleApplyTemplate = useCallback(async (templateId: string) => {
    if (!templateId) {
      setEditedText(message.translatedText || "");
      setAppliedTemplateId(null);
      return;
    }

    const callMessageId = message.id;
    setIsApplyingTemplate(true);
    try {
      const data = getTemplateData();
      const result = await api.applyTemplate(message.id, templateId, data);
      // Discard stale response if the user switched to a different message
      if (messageIdRef.current !== callMessageId) return;
      if (result.formatted_output != null) {
        setEditedText(result.formatted_output);
        setAppliedTemplateId(templateId);
      }
    } catch (err) {
      console.error("Apply template failed:", err);
    } finally {
      if (messageIdRef.current === callMessageId) {
        setIsApplyingTemplate(false);
      }
    }
  }, [message.id, message.translatedText, getTemplateData]);

  const handleTemplateChange = (templateId: string) => {
    setSelectedTemplate(templateId);
    handleApplyTemplate(templateId);
  };

  // Re-apply template live when editable fields change.
  useEffect(() => {
    if (appliedTemplateId) {
      handleApplyTemplate(appliedTemplateId);
    }
  }, [appliedTemplateId, handleApplyTemplate, editedEventType, editedThreatLevel, editedRegion, includeEntities, intelStatus]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleTitleBlur = () => {
    if (appliedTemplateId) handleApplyTemplate(appliedTemplateId);
  };

  const handleIntelStatusChange = (value: string) => {
    setIntelStatus(value);
    // useEffect watches intelStatus and re-applies the template automatically
  };

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      await api.approveMessage(
        message.id,
        editedText !== message.translatedText ? editedText : undefined,
        includedServerMedia,
      );
    } catch (err) {
      console.error("Approve failed:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    setIsSubmitting(true);
    try {
      await api.rejectMessage(message.id);
    } catch (err) {
      console.error("Reject failed:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArchive = async () => {
    try {
      await api.archiveMessage(message.id);
    } catch (err) {
      console.error("Archive failed:", err);
    }
  };

  const handleDelete = async () => {
    try {
      await api.deleteMessage(message.id);
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  const handleAcknowledgeDisinfo = async () => {
    setIsAcknowledging(true);
    try {
      await api.acknowledgeDisinfo(message.id);
      setDisinfoDialogOpen(false);
    } catch (err) {
      console.error("Acknowledge disinfo failed:", err);
    } finally {
      setIsAcknowledging(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-auto">
      {/* ── Header Bar ─────────────────────────── */}
      <div className="flex items-center justify-between border-b border-[var(--border-color)] px-6 py-3">
        <div className="flex items-center gap-3">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusStyle}`}>
            {t(`feed.status.${message.status}`, lang)}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--text-secondary)]">
              {time}
            </span>
            {message.sourceTrust && (
              <TrustBadge level={message.sourceTrust.trust_level} lang={lang} />
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Preprocess badges */}
          {message.preprocessMeta?.language && message.preprocessMeta.language !== "unknown" && (
            <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-medium text-indigo-400">
              {message.preprocessMeta.language}
            </span>
          )}
          {message.preprocessMeta?.keyword_matches && message.preprocessMeta.keyword_matches.length > 0 && (
            <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
              {message.preprocessMeta.keyword_matches.join(", ")}
            </span>
          )}
          {message.preprocessMeta?.priority_score != null && message.preprocessMeta.priority_score > 0 && (
            <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] font-medium text-red-400">
              P+{message.preprocessMeta.priority_score}
            </span>
          )}
          {message.preprocessMeta?.is_duplicate && (
            <span className="rounded bg-orange-500/10 px-1.5 py-0.5 text-[10px] font-medium text-orange-400">
              {t("preprocess.duplicate", lang)}
            </span>
          )}
          <span className="font-mono text-[10px] text-[var(--text-secondary)]">
            {message.id.slice(0, 8)}
          </span>
        </div>
      </div>

      {/* ── Processing Banner ────────────────────── */}
      {isProcessing && (
        <div className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/5 px-6 py-2">
          <svg className="h-3.5 w-3.5 animate-spin text-amber-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          <span className="text-xs font-medium text-amber-400">
            {t(`feed.status.${message.status}`, lang)}...
          </span>
        </div>
      )}

      {/* ── Disinformation Alert Banner ──────────── */}
      {isFlagged && (
        <div className={`border-b px-6 py-3 ${
          message.factCheck!.risk_level === "high"
            ? "border-red-500/30 bg-red-600/10"
            : "border-amber-500/30 bg-amber-600/10"
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`h-5 w-5 ${
                message.factCheck!.risk_level === "high" ? "text-red-400" : "text-amber-400"
              }`}>
                <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495ZM10 6a.75.75 0 0 1 .75.75v3.5a.75.75 0 0 1-1.5 0v-3.5A.75.75 0 0 1 10 6Zm0 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clipRule="evenodd" />
              </svg>
              <span className={`text-sm font-bold ${
                message.factCheck!.risk_level === "high" ? "text-red-400" : "text-amber-400"
              }`}>
                {t(`factcheck.risk.${message.factCheck!.risk_level}`, lang)}
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                ({t("factcheck.confidence", lang)}: {Math.round(message.factCheck!.confidence * 100)}%)
              </span>
            </div>
            {isAcknowledged ? (
              <span className="rounded-full bg-green-600/20 px-2.5 py-0.5 text-[10px] font-bold text-green-400">
                {t("factcheck.acknowledged", lang)}
              </span>
            ) : (
              <button
                onClick={() => setDisinfoDialogOpen(true)}
                className={`rounded-md px-3 py-1.5 text-xs font-bold text-white transition-colors ${
                  message.factCheck!.risk_level === "high"
                    ? "bg-red-600 hover:bg-red-700"
                    : "bg-amber-600 hover:bg-amber-700"
                }`}
              >
                {lang === "he" ? "בטל נעילה" : "Override"}
              </button>
            )}
          </div>
          {/* Reasoning */}
          {message.factCheck!.reasoning && (
            <p className="mt-2 text-xs text-[var(--text-secondary)]" dir="auto">
              <span className="font-semibold">{t("factcheck.reasoning", lang)}:</span>{" "}
              {message.factCheck!.reasoning}
            </p>
          )}
          {/* Warning signals */}
          {message.factCheck!.signals.length > 0 && (
            <div className="mt-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                {t("factcheck.signals", lang)}
              </span>
              <div className="mt-1 flex flex-wrap gap-1">
                {message.factCheck!.signals.map((signal, i) => (
                  <span key={i} className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    message.factCheck!.risk_level === "high"
                      ? "bg-red-600/20 text-red-400"
                      : "bg-amber-600/20 text-amber-400"
                  }`}>
                    {signal}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Scrollable Content ─────────────────── */}
      <div className="flex-1 space-y-4 overflow-auto p-6">

        {/* ── Section 1: Source Intelligence ── */}
        <DossierSection id="source" title={t("dossier.section.source", lang)}>
          {/* Original text block */}
          <section>
          <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
            <p className="text-sm leading-relaxed text-[var(--text-primary)] opacity-80" dir="auto">
              {message.originalText}
            </p>
            {/* Source media thumbnails — clickable for lightbox, X to exclude from post */}
            {(message.mediaUrls?.length ?? 0) > 0 && (
              <div className="mt-3 grid grid-cols-3 gap-2">
                {(message.mediaUrls ?? []).map((url, i) => {
                  const isVideo = /\.(mp4|mov|webm|avi)$/i.test(url);
                  const isExcluded = excludedServerMedia.includes(url);
                  return (
                    <div
                      key={i}
                      className={`group relative aspect-square overflow-hidden rounded-md border transition-all ${
                        isExcluded
                          ? "border-red-500/40 opacity-40 grayscale"
                          : "border-[var(--border-color)] hover:border-[var(--accent-blue)] hover:ring-2 hover:ring-[var(--accent-blue)]/30"
                      }`}
                    >
                      <button
                        onClick={() => openLightbox(message.mediaUrls ?? [], i)}
                        className="h-full w-full"
                      >
                        {isVideo ? (
                          <div className="flex h-full w-full items-center justify-center bg-[var(--bg-secondary)]">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-6 w-6 text-[var(--text-secondary)]">
                              <path fillRule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clipRule="evenodd" />
                            </svg>
                          </div>
                        ) : (
                          <img
                            src={`http://127.0.0.1:8000/media/${url}`}
                            alt={`media-${i}`}
                            className="h-full w-full object-cover"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                          />
                        )}
                      </button>
                      {/* X to exclude / + to restore */}
                      {isExcluded ? (
                        <button
                          onClick={() => restoreServerMedia(url)}
                          className="absolute -top-1 -end-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-green-600 text-white shadow"
                          title={t("dossier.media_restore", lang)}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                            <path d="M8.75 3.75a.75.75 0 0 0-1.5 0v3.5h-3.5a.75.75 0 0 0 0 1.5h3.5v3.5a.75.75 0 0 0 1.5 0v-3.5h3.5a.75.75 0 0 0 0-1.5h-3.5v-3.5Z" />
                          </svg>
                        </button>
                      ) : (
                        <button
                          onClick={() => removeServerMedia(url)}
                          className="absolute -top-1 -end-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-white shadow transition-opacity opacity-70 hover:opacity-100"
                          title={t("dossier.media_remove", lang)}
                        >
                          <XIcon />
                        </button>
                      )}
                      {/* Watermark detection badge */}
                      {message.watermarkDetected && !isVideo && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowWmOriginal((prev) => !prev);
                          }}
                          className="absolute bottom-0 start-0 z-10 rounded-tr-md bg-amber-600/90 px-1.5 py-0.5 text-[8px] font-bold text-white uppercase"
                          title={showWmOriginal ? t("dossier.wm_cleaned", lang) : t("dossier.wm_original", lang)}
                        >
                          WM {Math.round((message.watermarkConfidence ?? 0) * 100)}%
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {/* Watermark before/after toggle bar */}
            {message.watermarkDetected && message.watermarkOriginalPath && (
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={() => setShowWmOriginal((prev) => !prev)}
                  className={`rounded-md px-3 py-1 text-[10px] font-medium transition-colors ${
                    showWmOriginal
                      ? "bg-amber-600/20 text-amber-400"
                      : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)]"
                  }`}
                >
                  {showWmOriginal ? t("dossier.wm_original", lang) : t("dossier.wm_cleaned", lang)}
                </button>
                <span className="text-[10px] text-[var(--text-secondary)]">
                  {t("dossier.wm_badge", lang)} — {Math.round((message.watermarkConfidence ?? 0) * 100)}%
                </span>
              </div>
            )}
          </div>
        </section>
        </DossierSection>

        {/* ── Section 2: AI Analysis ── */}
        <DossierSection id="analysis" title={t("dossier.section.analysis", lang)}>
        {/* ── Auto Tags ─────────────────────────── */}
        {hasAutoTags && (
          <section>
            <div className="flex items-center justify-between">
              <SectionLabel text={t("review.tags", lang)} />
              {isReviewable && (
                <MiniToggle
                  checked={includeEntities}
                  onChange={(val) => setIncludeEntities(val)}
                  label={t("dossier.include_entities", lang)}
                />
              )}
            </div>
            {isReviewable ? (
              <div className="space-y-2.5">
                <div className="grid grid-cols-3 gap-3">
                  {/* Event Type dropdown */}
                  <select
                    value={editedEventType || message.autoTags!.event_type}
                    onChange={(e) => setEditedEventType(e.target.value)}
                    className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                  >
                    {eventTypes.map((et) => (
                      <option key={et.key} value={et.key}>{lang === "he" ? et.name_he : et.name_en}</option>
                    ))}
                  </select>
                  {/* Threat Level dropdown */}
                  <select
                    value={editedThreatLevel || message.autoTags!.threat_level}
                    onChange={(e) => setEditedThreatLevel(e.target.value)}
                    className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                  >
                    {threatLevels.map((tl) => (
                      <option key={tl.key} value={tl.key}>{lang === "he" ? tl.name_he : tl.name_en}</option>
                    ))}
                  </select>
                  {/* Region dropdown */}
                  <select
                    value={editedRegion || message.autoTags!.region}
                    onChange={(e) => setEditedRegion(e.target.value)}
                    className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                  >
                    {REGION_KEYS
                      .slice()
                      .sort((a, b) => translateRegion(a, lang).localeCompare(translateRegion(b, lang), lang === "he" ? "he" : "en"))
                      .map((key) => (
                        <option key={key} value={key}>{translateRegion(key, lang)}</option>
                      ))}
                  </select>
                </div>
                {/* Entities still as chips + content type chip */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {message.contentType && message.contentType !== "other" && (
                    <TagChip
                      label={t(`content.${message.contentType === "advertisement" ? "ad" : message.contentType}`, lang)}
                      color={
                        message.contentType === "intel" ? "bg-emerald-600"
                        : message.contentType === "news" ? "bg-sky-600"
                        : message.contentType === "editorial" ? "bg-violet-600"
                        : message.contentType === "advertisement" ? "bg-orange-600"
                        : message.contentType === "spam" ? "bg-red-600"
                        : "bg-gray-600"
                      }
                    />
                  )}
                  {message.autoTags!.entities.map((entity, i) => (
                    <TagChip key={i} label={entity} color="bg-gray-600" />
                  ))}
                </div>
              </div>
            ) : (
              /* Read-only view for non-reviewable messages */
              <div className="flex flex-wrap items-center gap-1.5">
                {message.contentType && message.contentType !== "other" && (
                  <TagChip
                    label={t(`content.${message.contentType === "advertisement" ? "ad" : message.contentType}`, lang)}
                    color={
                      message.contentType === "intel" ? "bg-emerald-600"
                      : message.contentType === "news" ? "bg-sky-600"
                      : message.contentType === "editorial" ? "bg-violet-600"
                      : message.contentType === "advertisement" ? "bg-orange-600"
                      : message.contentType === "spam" ? "bg-red-600"
                      : "bg-gray-600"
                    }
                  />
                )}
                <TagChip
                  label={t(`tag.event.${message.autoTags!.event_type}`, lang)}
                  color="bg-blue-600"
                />
                {message.autoTags!.region && (
                  <TagChip label={translateRegion(message.autoTags!.region, lang)} color="bg-purple-600" />
                )}
                <ThreatLevelChip level={message.autoTags!.threat_level} lang={lang} />
                {message.autoTags!.entities.map((entity, i) => (
                  <TagChip key={i} label={entity} color="bg-gray-600" />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ── Geo Context ──────────────────────── */}
        {message.geoContext && message.geoContext.countries?.length > 0 && (
          <section>
            <SectionLabel text={t("dossier.geo_context", lang)} />
            <div className="space-y-2">
              {/* Country flag pills */}
              <div className="flex flex-wrap gap-1.5">
                {message.geoContext.countries.map((country) => (
                  <span
                    key={country.code}
                    className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-tertiary)] border border-[var(--border-color)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)]"
                  >
                    <span className="text-sm">{country.flag}</span>
                    {lang === "he"
                      ? (COUNTRY_NAMES[country.code]?.he ?? country.name)
                      : country.name}
                  </span>
                ))}
              </div>
              {/* Conflict context alert bar */}
              {message.geoContext.conflict_context && (
                <div
                  className={`rounded-md px-3 py-2 text-xs font-medium ${
                    message.geoContext.conflict_level === "active_conflict"
                      ? "bg-red-600/15 text-red-400 border border-red-600/30"
                      : message.geoContext.conflict_level === "regional_tension"
                        ? "bg-amber-600/15 text-amber-400 border border-amber-600/30"
                        : "bg-blue-600/15 text-blue-400 border border-blue-600/30"
                  }`}
                >
                  <span className="font-bold">
                    {t(`dossier.conflict.${message.geoContext.conflict_level}`, lang)}
                  </span>
                  {" — "}
                  {message.geoContext.conflict_context}
                </div>
              )}
              {/* Location chips */}
              {message.geoContext.locations?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {message.geoContext.locations.map((loc, i) => (
                    <span
                      key={i}
                      className="rounded bg-[var(--bg-secondary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]"
                    >
                      {loc}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}

        {/* ── Situation Awareness ──────────────── */}
        {(message.situationBrief || (message.relatedMessages && message.relatedMessages.length > 0)) && (
          <section>
            <SectionLabel text={t("dossier.situation", lang)} />
            <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-4 space-y-3">
              {/* Situation brief */}
              {message.situationBrief && (
                <p className={`text-xs font-semibold ${
                  message.situationBrief.startsWith("DEVELOPING")
                    ? "text-red-400"
                    : "text-[var(--text-secondary)]"
                }`}>
                  {message.situationBrief}
                </p>
              )}
              {/* Related posts list */}
              {message.relatedMessages && message.relatedMessages.length > 0 ? (
                <div className="space-y-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    {t("dossier.related_posts", lang)} ({message.relatedMessages.length})
                  </span>
                  {message.relatedMessages.map((rel) => {
                    const relTime = new Date(rel.timestamp * 1000).toLocaleString(
                      lang === "he" ? "he-IL" : "en-US",
                      { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" },
                    );
                    return (
                      <div
                        key={rel.message_id}
                        className="flex items-center justify-between rounded-md bg-[var(--bg-secondary)] px-2.5 py-1.5"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs shrink-0">
                            {rel.countries?.map((c: string) =>
                              [...c.toUpperCase()].map((ch) => String.fromCodePoint(0x1f1e6 + ch.charCodeAt(0) - 65)).join("")
                            ).join(" ")}
                          </span>
                          <span className="truncate text-xs text-[var(--text-primary)]">
                            {rel.title || rel.source_channel}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {rel.threat_level && rel.threat_level !== "info" && (
                            <span className={`rounded px-1 py-px text-[8px] font-bold uppercase ${
                              rel.threat_level === "critical" ? "bg-red-600/20 text-red-400"
                                : rel.threat_level === "high" ? "bg-amber-600/20 text-amber-400"
                                  : rel.threat_level === "medium" ? "bg-blue-600/20 text-blue-400"
                                    : "bg-green-600/20 text-green-400"
                            }`}>
                              {rel.threat_level}
                            </span>
                          )}
                          <span className="text-[10px] text-[var(--text-secondary)]">{relTime}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-[10px] text-[var(--text-secondary)]">
                  {t("dossier.no_related", lang)}
                </p>
              )}
            </div>
          </section>
        )}

        {/* ── Extracted Facts ───────────────────── */}
        {hasFacts && (
          <section>
            <SectionLabel text={t("review.facts", lang)} />
            <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
              <ol className="list-inside list-decimal space-y-1 text-sm text-[var(--text-primary)]" dir="rtl">
                {message.extractedFacts!.map((fact, i) => (
                  <li key={i} className="leading-relaxed">
                    <span>{fact.fact}</span>
                    <span className="mr-1.5 rounded bg-[var(--bg-secondary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
                      {t(`fact.category.${fact.category}`, lang)}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        )}

        {/* ── Raw Metadata (collapsible JSON tree) ─── */}
        {message.rawMetadata && (
          <section>
            <RawMetadataViewer metadata={message.rawMetadata} lang={lang} />
          </section>
        )}

        {/* ── Review Notes ──────────────────────── */}
        {message.reviewNotes && (
          <section>
            <SectionLabel text={t("dossier.review_notes", lang)} />
            <p className="whitespace-pre-wrap rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-3 text-xs text-[var(--text-secondary)]">
              {message.reviewNotes}
            </p>
          </section>
        )}
        </DossierSection>

        {/* ── Section 3: Post Editor ── */}
        <DossierSection id="editor" title={t("dossier.section.editor", lang)}>
        {/* ── Title + Template (2-col grid) ────────── */}
        {(message.translatedText || message.formattedOutput) && (
          <section>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <SectionLabel text={t("dossier.title", lang)} />
                <input
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  onBlur={handleTitleBlur}
                  readOnly={!isReviewable}
                  dir="rtl"
                  placeholder={t("dossier.title_placeholder", lang)}
                  className="h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm font-semibold text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                />
              </div>
              {templates.length > 0 ? (
                <div>
                  <div className="flex items-center gap-1.5">
                    <SectionLabel text={t("dossier.template", lang)} />
                    {isApplyingTemplate && (
                      <span className="text-[10px] text-[var(--text-secondary)] animate-pulse">
                        {lang === "he" ? "מעדכן..." : "Updating..."}
                      </span>
                    )}
                    {selectedTemplate && selectedTemplate === message.suggestedTemplateId && <AiBadge />}
                    {appliedTemplateId && (
                      <span className="shrink-0 rounded-full bg-green-600/20 px-2 py-0.5 text-[10px] font-medium text-green-400">
                        {t("review.template_applied", lang)}
                      </span>
                    )}
                  </div>
                  <select
                    value={selectedTemplate}
                    onChange={(e) => handleTemplateChange(e.target.value)}
                    disabled={isApplyingTemplate}
                    className="h-9 w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none disabled:opacity-50"
                  >
                    <option value="">{t("dossier.no_template", lang)}</option>
                    {templates.map((tpl) => (
                      <option key={tpl.id} value={tpl.id}>
                        {lang === "he" ? tpl.name_he : tpl.name_en}
                        {tpl.id === message.suggestedTemplateId ? " ★" : ""}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div />
              )}
            </div>
          </section>
        )}

        {/* ── Intel Status ─────────────────────── */}
        {(message.translatedText || message.formattedOutput) && (
          <section>
            <div className="flex items-center gap-1.5">
              <SectionLabel text={t("dossier.intel_status", lang)} />
              {intelStatus && intelStatus === message.suggestedIntelStatus && <AiBadge />}
            </div>
            <select
              value={intelStatus}
              onChange={(e) => handleIntelStatusChange(e.target.value)}
              disabled={!isReviewable}
              className="h-9 w-full max-w-xs rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none disabled:opacity-50"
            >
              <option value="">{t("dossier.no_status", lang)}</option>
              {INTEL_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {t(s.labelKey, lang)}
                </option>
              ))}
            </select>
          </section>
        )}

        {/* ── Editable Output ───────────────────── */}
        {(message.translatedText || message.formattedOutput) && (
          <section>
            <SectionLabel
              text={appliedTemplateId ? t("review.formatted_output", lang) : t("dossier.output", lang)}
            />
            <div className="mb-1.5 flex items-center justify-end gap-2">
              <span className="text-xs text-[var(--text-secondary)]">Rich editor</span>
              <button
                onClick={() => setUseRichEditor((prev) => !prev)}
                className={`relative h-5 w-9 rounded-full transition-colors ${useRichEditor ? "bg-[var(--accent-blue)]" : "bg-[var(--border-color)]"}`}
              >
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${useRichEditor ? "left-[18px]" : "left-0.5"}`} />
              </button>
            </div>
            {useRichEditor ? (
              <TelegramEditor
                content={editedText}
                onChange={setEditedText}
                readOnly={!isReviewable}
                dir="rtl"
                rows={appliedTemplateId ? 14 : 6}
              />
            ) : (
              <textarea
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                onPaste={handlePaste}
                readOnly={!isReviewable}
                dir="rtl"
                className="w-full resize-y rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-3 text-sm leading-relaxed text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none disabled:opacity-60"
                rows={appliedTemplateId ? 14 : 6}
              />
            )}
          </section>
        )}

        {/* ── Post Media (auto-populated + upload) ────── */}
        {((message.mediaUrls?.length ?? 0) > 0 || isReviewable) && (
          <section>
            <div className="flex items-center justify-between">
              <SectionLabel text={t("dossier.post_media", lang)} />
              {hasPostMedia && (
                <span className="text-[10px] text-[var(--text-secondary)]">
                  {includedServerMedia.length + uploadedMedia.length} {t("dossier.media_included", lang)}
                </span>
              )}
            </div>

            <div className="rounded-md border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
              {/* Included media grid */}
              {hasPostMedia && (
                <div className="grid grid-cols-3 gap-2">
                  {/* Server media (from original message) */}
                  {includedServerMedia.map((url, i) => {
                    const isVideo = /\.(mp4|mov|webm|avi)$/i.test(url);
                    return (
                      <div key={`srv-${url}`} className="group relative aspect-square overflow-hidden rounded-md border border-[var(--border-color)]">
                        {isVideo ? (
                          <div
                            className="flex h-full w-full cursor-pointer items-center justify-center bg-[var(--bg-secondary)]"
                            onClick={() => openLightbox(includedServerMedia, i)}
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-6 w-6 text-[var(--text-secondary)]">
                              <path fillRule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clipRule="evenodd" />
                            </svg>
                          </div>
                        ) : (
                          <img
                            src={`http://127.0.0.1:8000/media/${url}`}
                            alt={`post-media-${i}`}
                            className="h-full w-full cursor-pointer object-cover"
                            onClick={() => openLightbox(includedServerMedia, i)}
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                          />
                        )}
                        {/* Remove button — always visible */}
                        <button
                          onClick={() => removeServerMedia(url)}
                          className="absolute -top-1 -end-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-white shadow transition-opacity opacity-70 hover:opacity-100"
                          title={t("dossier.media_remove", lang)}
                        >
                          <XIcon />
                        </button>
                        {/* "Included" badge */}
                        <div className="absolute bottom-0 inset-x-0 bg-green-600/80 py-0.5 text-center text-[8px] font-bold text-white uppercase">
                          {t("dossier.media_in_post", lang)}
                        </div>
                      </div>
                    );
                  })}

                  {/* Uploaded media (user-added) */}
                  {uploadedMedia.map((item) => {
                    const isVideo = item.file.type.startsWith("video/");
                    return (
                      <div key={item.id} className="group relative aspect-square overflow-hidden rounded-md border border-dashed border-[var(--accent-blue)]">
                        {isVideo ? (
                          <video src={item.previewUrl} className="h-full w-full object-cover" />
                        ) : (
                          <img src={item.previewUrl} alt="" className="h-full w-full object-cover" />
                        )}
                        <button
                          onClick={() => removeUploadedMedia(item.id)}
                          className="absolute -top-1 -end-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-white opacity-0 shadow transition-opacity group-hover:opacity-100"
                        >
                          <XIcon />
                        </button>
                        <div className="absolute bottom-0 inset-x-0 bg-blue-600/80 py-0.5 text-center text-[8px] font-bold text-white uppercase">
                          {t("dossier.media_uploaded", lang)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Excluded (removed) server media — can re-add */}
              {hasExcluded && (
                <div className={hasPostMedia ? "mt-3 border-t border-[var(--border-color)] pt-3" : ""}>
                  <span className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    {t("dossier.media_excluded", lang)}
                  </span>
                  <div className="grid grid-cols-3 gap-2">
                    {excludedServerMedia.map((url) => {
                      const isVideo = /\.(mp4|mov|webm|avi)$/i.test(url);
                      return (
                        <button
                          key={`exc-${url}`}
                          onClick={() => restoreServerMedia(url)}
                          className="group relative aspect-square overflow-hidden rounded-md border border-[var(--border-color)] opacity-40 transition-opacity hover:opacity-80"
                          title={t("dossier.media_restore", lang)}
                        >
                          {isVideo ? (
                            <div className="flex h-full w-full items-center justify-center bg-[var(--bg-secondary)]">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5 text-[var(--text-secondary)]">
                                <path fillRule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clipRule="evenodd" />
                              </svg>
                            </div>
                          ) : (
                            <img
                              src={`http://127.0.0.1:8000/media/${url}`}
                              alt=""
                              className="h-full w-full object-cover grayscale"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                            />
                          )}
                          {/* Re-add overlay */}
                          <div className="absolute inset-0 flex items-center justify-center bg-black/30 transition-colors group-hover:bg-black/50">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5 text-white">
                              <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
                            </svg>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Upload zone (only in review) */}
              {isReviewable && (
                <div
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onPaste={handlePaste}
                  className={`${hasPostMedia || hasExcluded ? "mt-3 border-t border-[var(--border-color)] pt-3" : ""} text-center`}
                >
                  <button
                    onClick={handleFileSelect}
                    className="inline-flex items-center gap-2 rounded-md bg-[var(--bg-secondary)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)] hover:text-[var(--text-primary)]"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                      <path d="M9.25 13.25a.75.75 0 0 0 1.5 0V4.636l2.955 3.129a.75.75 0 0 0 1.09-1.03l-4.25-4.5a.75.75 0 0 0-1.09 0l-4.25 4.5a.75.75 0 1 0 1.09 1.03L9.25 4.636v8.614Z" />
                      <path d="M3.5 12.75a.75.75 0 0 0-1.5 0v2.5A2.75 2.75 0 0 0 4.75 18h10.5A2.75 2.75 0 0 0 18 15.25v-2.5a.75.75 0 0 0-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5Z" />
                    </svg>
                    {t("dossier.upload_btn", lang)}
                  </button>
                  <p className="mt-1.5 text-[10px] text-[var(--text-secondary)]">
                    {t("dossier.upload_hint", lang)}
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*,video/*"
                    multiple
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </div>
              )}

              {/* Empty state (no media at all) */}
              {!hasPostMedia && !hasExcluded && !isReviewable && (
                <p className="text-center text-xs text-[var(--text-secondary)]">
                  {t("dossier.no_media", lang)}
                </p>
              )}
            </div>
          </section>
        )}
        </DossierSection>
      </div>

      {/* ── Action Bar ─────────────────────────── */}
      <div className="flex items-center justify-between border-t border-[var(--border-color)] px-6 py-3">
        {/* Primary actions: Approve + Reject */}
        <div className="flex items-center gap-2">
          {isReviewable && (
            <>
              <button
                onClick={disinfoBlocked ? () => setDisinfoDialogOpen(true) : handleApprove}
                disabled={isSubmitting}
                className={`h-9 rounded-md px-5 text-sm font-medium text-white transition-colors disabled:opacity-50 ${
                  disinfoBlocked
                    ? "bg-red-600 hover:bg-red-700"
                    : "bg-[var(--accent-green)] hover:bg-green-600"
                }`}
              >
                {disinfoBlocked ? t("factcheck.disinfo_suspect", lang) : t("review.approve", lang)}
              </button>
              <button
                onClick={handleReject}
                disabled={isSubmitting}
                className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)] disabled:opacity-50"
              >
                {t("review.reject", lang)}
              </button>
            </>
          )}
        </div>
        {/* Secondary actions: Archive + Delete */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--text-secondary)]">
            {message.id}
          </span>
          {canArchive && (
            <button
              onClick={handleArchive}
              className="h-9 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-4 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)]"
            >
              {t("btn.archive", lang)}
            </button>
          )}
          <button
            onClick={handleDelete}
            className="h-9 rounded-md bg-red-900/30 px-4 text-sm font-medium text-red-400 transition-colors hover:bg-red-900/50"
          >
            {t("btn.delete", lang)}
          </button>
        </div>
      </div>

      {/* ── Media Lightbox ────────────────────── */}
      {lightboxOpen && lightboxUrls.length > 0 && (
        <MediaLightbox
          urls={lightboxUrls}
          currentIndex={lightboxIndex}
          onClose={() => setLightboxOpen(false)}
          onNavigate={setLightboxIndex}
        />
      )}

      {/* ── Disinformation Confirmation Dialog ── */}
      {disinfoDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="mx-4 w-full max-w-md rounded-xl border border-red-600/30 bg-[var(--bg-secondary)] p-6 shadow-2xl">
            <div className="mb-4 flex justify-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-600/20">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-8 w-8 text-red-400">
                  <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003ZM12 8.25a.75.75 0 0 1 .75.75v3.75a.75.75 0 0 1-1.5 0V9a.75.75 0 0 1 .75-.75Zm0 8.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            <h3 className="mb-2 text-center text-lg font-bold text-red-400">
              {t("factcheck.override_confirm", lang)}
            </h3>
            <p className="mb-6 text-center text-sm text-[var(--text-secondary)]">
              {message.factCheck?.reasoning}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDisinfoDialogOpen(false)}
                className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] py-2.5 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)]"
              >
                {t("factcheck.override_cancel", lang)}
              </button>
              <button
                onClick={handleAcknowledgeDisinfo}
                disabled={isAcknowledging}
                className="flex-1 rounded-md bg-red-600 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {isAcknowledging
                  ? (lang === "he" ? "מאשר..." : "Confirming...")
                  : t("factcheck.override_btn", lang)}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────

const TRUST_STYLES: Record<string, { bg: string; label_key: string }> = {
  verified: { bg: "bg-green-600/20 text-green-400 border-green-600/30", label_key: "trust.verified" },
  trusted: { bg: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30", label_key: "trust.trusted" },
  neutral: { bg: "bg-gray-600/20 text-gray-400 border-gray-600/30", label_key: "trust.neutral" },
  suspect: { bg: "bg-amber-600/20 text-amber-400 border-amber-600/30", label_key: "trust.suspect" },
  untrusted: { bg: "bg-red-600/20 text-red-400 border-red-600/30", label_key: "trust.untrusted" },
};

function TrustBadge({ level, lang }: { level: string; lang: "he" | "en" }) {
  const style = TRUST_STYLES[level] ?? TRUST_STYLES.neutral;
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${style.bg}`}>
      {t(style.label_key, lang)}
    </span>
  );
}

function SectionLabel({ text }: { text: string }) {
  return (
    <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
      {text}
    </h3>
  );
}

function XIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
      <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
    </svg>
  );
}
