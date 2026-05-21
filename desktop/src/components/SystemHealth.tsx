import { usePipelineStore } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";

export function SystemHealth() {
  const agents = usePipelineStore((s) => s.agents);
  const isRunning = usePipelineStore((s) => s.isRunning);
  const lang = useSettingsStore((s) => s.language);

  const healthyCount = agents.filter((a) => a.status !== "error").length;
  const totalCount = agents.length;

  return (
    <div className="p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        {t("health.title", lang)}
      </h2>

      <div className="space-y-3">
        {/* Overall Status */}
        <div className="rounded-md bg-[var(--bg-tertiary)] p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">{t("health.pipeline", lang)}</span>
            <span className={`text-xs font-medium ${isRunning ? "text-[var(--accent-green)]" : "text-[var(--text-secondary)]"}`}>
              {isRunning ? t("health.online", lang) : t("health.offline", lang)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">{t("health.agents_healthy", lang)}</span>
            <span className="text-xs font-medium text-[var(--text-primary)]">
              {healthyCount}/{totalCount}
            </span>
          </div>
        </div>

        {/* Per-Agent Health */}
        {agents.map((agent) => (
          <div key={agent.id} className="rounded-md bg-[var(--bg-tertiary)] p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-[var(--text-primary)]">{t(agent.id, lang)}</span>
              <HealthDot status={agent.status} />
            </div>
            {agent.lastActivity && (
              <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">{agent.lastActivity}</p>
            )}
            <p className="text-xs text-[var(--text-secondary)]">
              {t("health.processed", lang)}: {agent.messagesProcessed}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function HealthDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    idle: "bg-gray-400",
    running: "bg-[var(--accent-green)]",
    error: "bg-[var(--accent-red)]",
    waiting_review: "bg-[var(--accent-amber)]",
  };

  return <span className={`h-2.5 w-2.5 rounded-full ${colors[status] ?? "bg-gray-400"}`} />;
}
