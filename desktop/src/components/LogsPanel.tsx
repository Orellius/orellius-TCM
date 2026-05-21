import { useEffect, useRef } from "react";
import { useLogStore, type LogLevel } from "../stores/logStore";
import { useSettingsStore } from "../stores/settingsStore";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "text-gray-400",
  INFO: "text-blue-400",
  WARNING: "text-amber-400",
  ERROR: "text-red-400",
  CRITICAL: "text-red-600 font-bold",
};

const LEVEL_BG: Record<string, string> = {
  DEBUG: "",
  INFO: "",
  WARNING: "",
  ERROR: "bg-red-950/20",
  CRITICAL: "bg-red-950/40",
};

const LEVELS: (LogLevel | "ALL")[] = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("en-GB", { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function shortenLogger(name: string): string {
  // "app.agents.analyst" → "analyst"
  const parts = name.split(".");
  return parts[parts.length - 1];
}

export function LogsPanel({ compact = false }: { compact?: boolean } = {}) {
  const lang = useSettingsStore((s) => s.language);
  const { entries, filterLevel, autoScroll, setFilterLevel, setAutoScroll, setEntries, clear } = useLogStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Fetch initial logs on mount
  useEffect(() => {
    api.getLogs(500).then((res) => {
      if (res.entries.length > 0) {
        setEntries(res.entries);
      }
    }).catch(() => {});
  }, [setEntries]);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [entries.length, autoScroll]);

  const filtered = filterLevel === "ALL"
    ? entries
    : entries.filter((e) => e.level === filterLevel);

  const handleClear = async () => {
    clear();
    try {
      await api.clearLogs();
    } catch {
      // Ignore
    }
  };

  const COMPACT_LEVELS: (LogLevel | "ALL")[] = ["ALL", "INFO", "WARNING", "ERROR"];

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className={`flex items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-secondary)] ${compact ? "px-3 py-1.5" : "px-6 py-2"}`}>
        <div className="flex items-center gap-2">
          {!compact && (
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              {t("logs.title", lang)}
            </h2>
          )}
          <span className="rounded-full bg-[var(--bg-tertiary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
            {filtered.length}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Level filter */}
          <div className="flex items-center gap-0.5">
            {(compact ? COMPACT_LEVELS : LEVELS).map((level) => (
              <button
                key={level}
                onClick={() => setFilterLevel(level)}
                className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                  filterLevel === level
                    ? "bg-[var(--accent-blue)] text-white"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                }`}
              >
                {level === "ALL" ? t("logs.all", lang) : level}
              </button>
            ))}
          </div>

          {!compact && (
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="h-3 w-3 rounded border-[var(--border-color)] accent-[var(--accent-blue)]"
              />
              {t("logs.auto_scroll", lang)}
            </label>
          )}

          {/* Clear */}
          <button
            onClick={handleClear}
            className={`rounded px-1.5 py-0.5 font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-tertiary)] ${compact ? "text-[10px]" : "text-xs"}`}
          >
            {t("logs.clear", lang)}
          </button>
        </div>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-auto bg-[var(--bg-primary)] font-mono text-xs" dir="ltr">
        {filtered.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-[10px] text-[var(--text-secondary)]">{t("logs.empty", lang)}</p>
          </div>
        ) : (
          <table className="w-full">
            <tbody>
              {filtered.map((entry, i) => (
                <tr
                  key={`${entry.timestamp}-${entry.logger}-${entry.level}-${i}`}
                  className={`border-b border-[var(--border-color)]/30 hover:bg-[var(--bg-secondary)] ${LEVEL_BG[entry.level] ?? ""}`}
                >
                  <td className={`whitespace-nowrap text-gray-500 ${compact ? "px-1.5 py-px text-[10px]" : "px-2 py-0.5"}`}>
                    {formatTime(entry.timestamp)}
                  </td>
                  <td className={`whitespace-nowrap ${compact ? "w-12 px-1 py-px text-[10px]" : "w-16 px-2 py-0.5"} ${LEVEL_COLORS[entry.level] ?? "text-gray-400"}`}>
                    {compact ? entry.level.slice(0, 4) : entry.level}
                  </td>
                  <td className={`whitespace-nowrap text-purple-400 ${compact ? "px-1 py-px text-[10px]" : "px-2 py-0.5"}`}>
                    {shortenLogger(entry.logger)}
                  </td>
                  <td className={`text-[var(--text-primary)] ${compact ? "px-1.5 py-px text-[10px]" : "px-2 py-0.5"}`}>
                    <span className="whitespace-pre-wrap break-all">{entry.message}</span>
                    {!compact && entry.exc_info && (
                      <pre className="mt-1 whitespace-pre-wrap text-red-400/80">{entry.exc_info}</pre>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
