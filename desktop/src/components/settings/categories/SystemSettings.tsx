import { useState, useEffect } from "react";
import { useSettingsStore } from "../../../stores/settingsStore";
import { t } from "../../../lib/i18n";
import { MonitorHealthPanel } from "../../MonitorHealthPanel";
import { LogsPanel } from "../../LogsPanel";

const API = "http://127.0.0.1:8000/api";

interface OllamaStatus {
  healthy: boolean;
  version?: string;
  installed_models: string[];
  loaded_models: string[];
  current_model: string | null;
}

const models = [
  { key: "settings.model_translator", model: "qwen2.5:32b" },
  { key: "settings.model_orchestrator", model: "llama3.3:70b" },
  { key: "settings.model_reviewer", model: "deepseek-r1:32b" },
  { key: "settings.model_daemon", model: "qwen2.5-coder:32b" },
];

export function SystemSettings() {
  const language = useSettingsStore((s) => s.language);
  const [ollamaStatus, setOllamaStatus] = useState<OllamaStatus | null>(null);

  useEffect(() => {
    fetch(`${API}/ollama/status`)
      .then((r) => r.json())
      .then(setOllamaStatus)
      .catch(() =>
        setOllamaStatus({ healthy: false, installed_models: [], loaded_models: [], current_model: null }),
      );
  }, []);

  return (
    <div className="space-y-8">
      {/* ── LLM Models ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.llm", language)}
        </h3>

        <p className="mb-3 text-xs text-[var(--text-secondary)]">
          {t("settings.llm_desc", language)}
        </p>

        <div className="mb-4 flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              ollamaStatus?.healthy ? "bg-[var(--accent-green)]" : "bg-[var(--accent-red)]"
            }`}
          />
          <span className="text-sm text-[var(--text-primary)]">
            {t("settings.ollama_status", language)}:{" "}
            {ollamaStatus?.healthy
              ? `${t("status.online", language)} (v${ollamaStatus.version ?? "?"})`
              : t("status.offline", language)}
          </span>
        </div>

        <div className="space-y-2">
          {models.map(({ key, model }) => {
            const installed = ollamaStatus?.installed_models?.some(
              (m) => m === model || m.startsWith(model.split(":")[0] + ":" + model.split(":")[1]),
            );
            const loaded = ollamaStatus?.loaded_models?.some(
              (m) => m === model || m.startsWith(model.split(":")[0]),
            );
            return (
              <div
                key={key}
                className="flex items-center justify-between rounded-md bg-[var(--bg-tertiary)] px-3 py-2"
              >
                <span className="text-sm text-[var(--text-primary)]">{t(key, language)}</span>
                <div className="flex items-center gap-2">
                  <code className="rounded bg-[var(--bg-primary)] px-2 py-0.5 text-xs text-[var(--accent-blue)]">
                    {model}
                  </code>
                  {installed ? (
                    <span
                      className={`h-2.5 w-2.5 rounded-full ${
                        loaded ? "bg-[var(--accent-green)] animate-pulse" : "bg-[var(--accent-green)]"
                      }`}
                      title={loaded ? "Loaded in VRAM" : "Installed"}
                    />
                  ) : (
                    <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-red)]" title="Not installed" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Health & Logs ── */}
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col overflow-hidden rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]">
          <div className="flex items-center gap-2 bg-[var(--bg-tertiary)]/50 px-3 py-2">
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none" className="shrink-0 text-[var(--accent-green)]">
              <rect x="2" y="3" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M5 9H7L8.5 7L10.5 12L12 9H15" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
              <line x1="7" y1="18" x2="13" y2="18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              <line x1="10" y1="15" x2="10" y2="18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className="text-[11px] font-semibold text-[var(--text-primary)]">
              {t("tab.monitor", language)}
            </span>
          </div>
          <div className="h-64 overflow-auto">
            <MonitorHealthPanel compact />
          </div>
        </div>
        <div className="flex flex-col overflow-hidden rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]">
          <div className="flex items-center gap-2 bg-[var(--bg-tertiary)]/50 px-3 py-2">
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none" className="shrink-0 text-[var(--accent-blue)]">
              <rect x="2" y="3" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
              <path d="M6 8L8.5 10.5L6 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              <line x1="10.5" y1="13" x2="14" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <span className="text-[11px] font-semibold text-[var(--text-primary)]">
              {t("tab.logs", language)}
            </span>
          </div>
          <div className="h-64 overflow-auto">
            <LogsPanel compact />
          </div>
        </div>
      </div>
    </div>
  );
}
