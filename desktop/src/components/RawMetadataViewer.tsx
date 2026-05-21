import { useState } from "react";
import { t, type Lang } from "../lib/i18n";

interface RawMetadata {
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

/** Collapsible JSON tree node for rendering nested metadata. */
function JsonNode({ label, value, depth = 0 }: { label: string; value: unknown; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 1);

  if (value === null || value === undefined) {
    return (
      <div className="flex items-baseline gap-1.5" style={{ paddingInlineStart: depth * 16 }}>
        <span className="text-xs text-[var(--text-secondary)]">{label}:</span>
        <span className="text-xs italic text-gray-500">null</span>
      </div>
    );
  }

  if (typeof value === "object" && !Array.isArray(value)) {
    const entries = Object.entries(value as Record<string, unknown>);
    return (
      <div style={{ paddingInlineStart: depth * 16 }}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <span className="w-3 text-center font-mono">{expanded ? "\u25BE" : "\u25B8"}</span>
          <span>{label}</span>
          <span className="text-gray-600">{`{${entries.length}}`}</span>
        </button>
        {expanded && entries.map(([k, v]) => (
          <JsonNode key={k} label={k} value={v} depth={depth + 1} />
        ))}
      </div>
    );
  }

  if (Array.isArray(value)) {
    return (
      <div style={{ paddingInlineStart: depth * 16 }}>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <span className="w-3 text-center font-mono">{expanded ? "\u25BE" : "\u25B8"}</span>
          <span>{label}</span>
          <span className="text-gray-600">{`[${value.length}]`}</span>
        </button>
        {expanded && value.map((item, i) => (
          <JsonNode key={i} label={String(i)} value={item} depth={depth + 1} />
        ))}
      </div>
    );
  }

  // Primitive values
  const colorClass =
    typeof value === "number"
      ? "text-blue-400"
      : typeof value === "boolean"
        ? "text-amber-400"
        : "text-green-400";

  return (
    <div className="flex items-baseline gap-1.5" style={{ paddingInlineStart: depth * 16 }}>
      <span className="text-xs text-[var(--text-secondary)]">{label}:</span>
      <span className={`text-xs font-mono ${colorClass}`}>
        {typeof value === "string" ? `"${value.length > 120 ? value.slice(0, 120) + "..." : value}"` : String(value)}
      </span>
    </div>
  );
}

export function RawMetadataViewer({
  metadata,
  lang,
}: {
  metadata: RawMetadata | null | undefined;
  lang: Lang;
}) {
  const [expanded, setExpanded] = useState(false);

  if (!metadata) return null;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        <span className="flex items-center gap-2">
          <span className="font-mono">{expanded ? "\u25BE" : "\u25B8"}</span>
          {t("dossier.raw_metadata", lang)}
        </span>
        <span className="rounded bg-[var(--bg-primary)] px-1.5 py-0.5 text-[10px] font-mono text-gray-500">
          JSON
        </span>
      </button>
      {expanded && (
        <div className="border-t border-[var(--border-color)] px-3 py-2 max-h-80 overflow-y-auto space-y-0.5">
          {/* Quick summary badges */}
          <div className="flex flex-wrap gap-1.5 pb-2 mb-2 border-b border-[var(--border-color)]">
            {metadata.views != null && (
              <span className="rounded bg-blue-500/10 px-1.5 py-0.5 text-[10px] text-blue-400">
                {metadata.views.toLocaleString()} views
              </span>
            )}
            {metadata.reactions && metadata.reactions.length > 0 && (
              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-400">
                {metadata.reactions.map((r) => `${r.emoticon || "?"}${r.count}`).join(" ")}
              </span>
            )}
            {metadata.forward_from && (
              <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">
                Forwarded
              </span>
            )}
            {metadata.edit_date && (
              <span className="rounded bg-orange-500/10 px-1.5 py-0.5 text-[10px] text-orange-400">
                Edited
              </span>
            )}
            {metadata.post_author && (
              <span className="rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] text-green-400">
                by {metadata.post_author}
              </span>
            )}
          </div>

          {/* Full JSON tree */}
          {Object.entries(metadata).map(([key, value]) => (
            <JsonNode key={key} label={key} value={value} />
          ))}
        </div>
      )}
    </div>
  );
}
