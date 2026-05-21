import { usePipelineStore } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { t, type Lang } from "../lib/i18n";

const SERVICE_ICONS: Record<string, string> = {
  redis: "R",
  postgres: "P",
  qdrant: "Q",
  ollama: "O",
  telegram: "T",
};

function ServiceCard({ name, status, errorCount, lang }: {
  name: string;
  status: string;
  errorCount: number;
  lang: Lang;
}) {
  const isHealthy = status === "healthy";
  const isUnknown = status === "unknown";

  return (
    <div className={`rounded-lg border p-4 transition-colors ${
      isHealthy
        ? "border-green-500/30 bg-green-500/5"
        : isUnknown
          ? "border-[var(--border-color)] bg-[var(--bg-tertiary)]"
          : "border-red-500/30 bg-red-500/5"
    }`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`flex h-8 w-8 items-center justify-center rounded-md text-sm font-bold ${
            isHealthy ? "bg-green-500/20 text-green-400" :
            isUnknown ? "bg-gray-500/20 text-gray-400" :
            "bg-red-500/20 text-red-400"
          }`}>
            {SERVICE_ICONS[name] ?? name[0].toUpperCase()}
          </span>
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)] capitalize">{name}</p>
            <p className={`text-[10px] font-medium ${
              isHealthy ? "text-green-400" : isUnknown ? "text-gray-400" : "text-red-400"
            }`}>
              {isHealthy ? t("monitor.healthy", lang) : isUnknown ? t("monitor.unknown", lang) : t("monitor.unhealthy", lang)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${
            isHealthy ? "bg-green-400" : isUnknown ? "bg-gray-400" : "bg-red-400 animate-pulse"
          }`} />
          {errorCount > 0 && (
            <span className="rounded-full bg-red-500/20 px-1.5 py-0.5 text-[9px] font-bold text-red-400">
              {errorCount}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function MonitorHealthPanel({ compact = false }: { compact?: boolean } = {}) {
  const lang = useSettingsStore((s) => s.language);
  const healthReport = usePipelineStore((s) => s.latestHealthReport);
  const insights = usePipelineStore((s) => s.daemonInsights);
  const agents = usePipelineStore((s) => s.agents);

  const daemonAgent = agents.find((a) => a.name === "System Daemon");
  const lastCheck = healthReport
    ? new Date(healthReport.timestamp * 1000).toLocaleTimeString(
        lang === "he" ? "he-IL" : "en-US",
        { hour: "2-digit", minute: "2-digit", second: "2-digit" },
      )
    : null;

  if (compact) {
    return (
      <div className="space-y-3 p-3">
        {/* Compact status bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {daemonAgent && (
              <span className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                daemonAgent.status === "running"
                  ? "bg-green-500/15 text-green-400"
                  : daemonAgent.status === "error"
                    ? "bg-red-500/15 text-red-400"
                    : "bg-gray-500/15 text-gray-400"
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${
                  daemonAgent.status === "running" ? "bg-green-400 animate-pulse" : "bg-gray-400"
                }`} />
                {daemonAgent.status === "running" ? t("monitor.healthy", lang) : t("monitor.unknown", lang)}
              </span>
            )}
          </div>
          {lastCheck && (
            <span className="text-[10px] text-[var(--text-secondary)]">{lastCheck}</span>
          )}
        </div>

        {/* Compact service pills */}
        {healthReport ? (
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(healthReport.services).map(([name, status]) => {
              const isHealthy = status === "healthy";
              const isUnknown = status === "unknown";
              return (
                <div
                  key={name}
                  className={`flex items-center gap-1.5 rounded-md px-2 py-1 ${
                    isHealthy ? "bg-green-500/10" : isUnknown ? "bg-[var(--bg-tertiary)]" : "bg-red-500/10"
                  }`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${
                    isHealthy ? "bg-green-400" : isUnknown ? "bg-gray-400" : "bg-red-400 animate-pulse"
                  }`} />
                  <span className="text-[10px] font-medium text-[var(--text-primary)] capitalize">{name}</span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-[10px] text-[var(--text-secondary)]">{t("monitor.waiting", lang)}</p>
        )}

        {/* Compact insights */}
        {insights.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">{t("monitor.insights", lang)}</p>
            {insights.slice(0, 2).map((insight) => (
              <div key={`${insight.timestamp}-${insight.agent}`} className="rounded-md border border-amber-500/20 bg-amber-500/5 px-2.5 py-1.5">
                <p className="text-[10px] text-[var(--text-primary)] line-clamp-2">{insight.suggestion}</p>
              </div>
            ))}
          </div>
        )}

        {/* Compact agent rows */}
        <div className="space-y-1">
          {agents.map((agent) => (
            <div key={agent.id} className="flex items-center justify-between rounded-md bg-[var(--bg-tertiary)]/50 px-2 py-1">
              <span className="text-[10px] font-medium text-[var(--text-primary)]">{t(agent.id, lang)}</span>
              <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium ${
                agent.status === "running" ? "bg-green-500/15 text-green-400" :
                agent.status === "error" ? "bg-red-500/15 text-red-400" :
                "bg-gray-500/15 text-gray-400"
              }`}>
                <span className={`h-1 w-1 rounded-full ${
                  agent.status === "running" ? "bg-green-400" : agent.status === "error" ? "bg-red-400" : "bg-gray-400"
                }`} />
                {t(`agents.${agent.status}`, lang)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-[var(--text-primary)]">
            {t("monitor.title", lang)}
          </h2>
          <p className="text-xs text-[var(--text-secondary)]">
            {t("monitor.desc", lang)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {daemonAgent && (
            <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium ${
              daemonAgent.status === "running"
                ? "bg-green-500/20 text-green-400"
                : daemonAgent.status === "error"
                  ? "bg-red-500/20 text-red-400"
                  : "bg-gray-500/20 text-gray-400"
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${
                daemonAgent.status === "running" ? "bg-green-400 animate-pulse" : "bg-gray-400"
              }`} />
              {t("monitor.daemon_status", lang)}: {t(`agents.${daemonAgent.status}`, lang)}
            </span>
          )}
          {lastCheck && (
            <span className="text-[10px] text-[var(--text-secondary)]">
              {t("monitor.last_check", lang)}: {lastCheck}
            </span>
          )}
        </div>
      </div>

      {/* Service Health Grid */}
      <section>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {t("monitor.services", lang)}
        </h3>
        {healthReport ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {Object.entries(healthReport.services).map(([name, status]) => (
              <ServiceCard
                key={name}
                name={name}
                status={status}
                errorCount={healthReport.error_counts[name] ?? 0}
                lang={lang}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)] p-8 text-center">
            <div className="space-y-2">
              <div className="mx-auto h-8 w-8 animate-pulse rounded-md bg-[var(--bg-secondary)]" />
              <p className="text-xs text-[var(--text-secondary)]">
                {t("monitor.waiting", lang)}
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Daemon Insights / Analysis Reports */}
      <section>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {t("monitor.insights", lang)}
        </h3>
        {insights.length === 0 ? (
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)] p-6 text-center">
            <p className="text-xs text-[var(--text-secondary)]">
              {t("monitor.no_insights", lang)}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {insights.map((insight) => {
              const time = new Date(insight.timestamp * 1000).toLocaleTimeString(
                lang === "he" ? "he-IL" : "en-US",
                { hour: "2-digit", minute: "2-digit" },
              );
              return (
                <div
                  key={`${insight.timestamp}-${insight.agent}`}
                  className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-400 uppercase">
                        {t("monitor.diagnosis", lang)}
                      </span>
                      <span className="text-xs font-medium text-[var(--text-primary)]">
                        {insight.agent}
                      </span>
                    </div>
                    <span className="text-[10px] text-[var(--text-secondary)]">{time}</span>
                  </div>
                  <div className="mb-2 rounded bg-red-500/10 px-3 py-1.5">
                    <p className="text-xs text-red-400 font-mono">{insight.error}</p>
                  </div>
                  <p className="text-xs text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
                    {insight.suggestion}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Agent Overview */}
      <section>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {t("monitor.agents_overview", lang)}
        </h3>
        <div className="rounded-lg border border-[var(--border-color)] overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--border-color)] bg-[var(--bg-tertiary)]">
                <th className="px-4 py-2 text-start font-medium text-[var(--text-secondary)]">
                  {t("monitor.agent_name", lang)}
                </th>
                <th className="px-4 py-2 text-start font-medium text-[var(--text-secondary)]">
                  {t("monitor.status", lang)}
                </th>
                <th className="px-4 py-2 text-start font-medium text-[var(--text-secondary)]">
                  {t("monitor.activity", lang)}
                </th>
                <th className="px-4 py-2 text-end font-medium text-[var(--text-secondary)]">
                  {t("monitor.processed", lang)}
                </th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id} className="border-b border-[var(--border-color)] last:border-b-0">
                  <td className="px-4 py-2.5 font-medium text-[var(--text-primary)]">
                    {t(agent.id, lang)}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      agent.status === "running" ? "bg-green-500/20 text-green-400" :
                      agent.status === "error" ? "bg-red-500/20 text-red-400" :
                      agent.status === "waiting_review" ? "bg-yellow-500/20 text-yellow-400" :
                      "bg-gray-500/20 text-gray-400"
                    }`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${
                        agent.status === "running" ? "bg-green-400 animate-pulse" :
                        agent.status === "error" ? "bg-red-400" :
                        "bg-gray-400"
                      }`} />
                      {t(`agents.${agent.status}`, lang)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--text-secondary)] truncate max-w-[200px]">
                    {agent.lastActivity || "—"}
                  </td>
                  <td className="px-4 py-2.5 text-end font-mono text-[var(--text-secondary)]">
                    {agent.messagesProcessed}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
