import type { AgentState } from "../stores/pipelineStore";
import { t } from "../lib/i18n";

interface AgentDrawerProps {
  agents: AgentState[];
  isRunning: boolean;
  isOpen: boolean;
  lang: "he" | "en";
}

const STATUS_DOT: Record<string, string> = {
  idle: "bg-gray-500",
  running: "bg-[var(--accent-green)]",
  error: "bg-[var(--accent-red)]",
  waiting_review: "bg-[var(--accent-amber)]",
};

export function AgentDrawer({ agents, isRunning, isOpen, lang }: AgentDrawerProps) {
  const healthyCount = agents.filter((a) => a.status !== "error").length;
  const totalCount = agents.length;

  return (
    <div
      className={`overflow-hidden transition-all duration-200 ease-in-out border-b border-[var(--border-color)] bg-[var(--bg-secondary)] ${
        isOpen ? "max-h-[240px]" : "max-h-0 border-b-0"
      }`}
    >
      <div className="p-3">
        {/* Agent cards grid */}
        <div className="grid grid-cols-6 gap-3">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="rounded-md bg-[var(--bg-tertiary)] px-2.5 py-2"
            >
              <div className="flex items-center justify-between">
                <span className="truncate text-xs font-medium text-[var(--text-primary)]">
                  {t(agent.id, lang)}
                </span>
                <StatusBadge status={agent.status} lang={lang} />
              </div>
              {(agent.lastActivity || agent.messagesProcessed > 0) && (
                <div className="mt-1 flex items-center justify-between text-[9px] text-[var(--text-secondary)]">
                  <span className="truncate">{agent.lastActivity}</span>
                  {agent.messagesProcessed > 0 && (
                    <span className="shrink-0 ms-1">{agent.messagesProcessed}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Health section */}
        <div className="mt-3 flex items-center gap-4 rounded-md bg-[var(--bg-tertiary)] px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              {t("health.pipeline", lang)}
            </span>
            <span
              className={`text-[10px] font-medium ${
                isRunning ? "text-[var(--accent-green)]" : "text-[var(--text-secondary)]"
              }`}
            >
              {isRunning ? t("health.online", lang) : t("health.offline", lang)}
            </span>
          </div>

          <div className="h-3 w-px bg-[var(--border-color)]" />

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[var(--text-secondary)]">
              {t("health.agents_healthy", lang)}
            </span>
            <span className="text-[10px] font-medium text-[var(--text-primary)]">
              {healthyCount}/{totalCount}
            </span>
          </div>

          <div className="h-3 w-px bg-[var(--border-color)]" />

          {/* Per-agent health dots */}
          <div className="flex items-center gap-1.5">
            {agents.map((agent) => (
              <span
                key={agent.id}
                title={`${t(agent.id, lang)}: ${t(`agents.${agent.status}`, lang)}`}
                className={`h-2 w-2 rounded-full ${STATUS_DOT[agent.status] ?? "bg-gray-500"} ${
                  agent.status === "running" ? "animate-pulse" : ""
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status, lang }: { status: string; lang: "he" | "en" }) {
  const colors: Record<string, string> = {
    idle: "bg-gray-500",
    running: "bg-[var(--accent-green)]",
    error: "bg-[var(--accent-red)]",
    waiting_review: "bg-[var(--accent-amber)]",
  };

  const statusKey = `agents.${status}` as const;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium text-white ${
        colors[status] ?? "bg-gray-500"
      }`}
    >
      <span
        className={`h-1 w-1 rounded-full bg-white ${status === "running" ? "animate-pulse" : ""}`}
      />
      {t(statusKey, lang)}
    </span>
  );
}
