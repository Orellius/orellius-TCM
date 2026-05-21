import { useRef, useMemo } from "react";
import type { AgentState } from "../stores/pipelineStore";
import { usePipelineStore } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";
import { ChannelPopover } from "./ChannelPopover";

/** 3-letter codes for each agent */
const AGENT_CODES: Record<string, string> = {
  "agent.ingestion": "ING",
  "agent.analyst": "ANA",
  "agent.reviewer": "REV",
  "agent.media_handler": "MED",
  "agent.publisher": "PUB",
  "agent.system_daemon": "SYS",
};

const STATUS_DOT_COLOR: Record<string, string> = {
  idle: "bg-gray-500",
  running: "bg-[var(--accent-green)]",
  error: "bg-[var(--accent-red)]",
  waiting_review: "bg-[var(--accent-amber)]",
};

interface StatusRailProps {
  agents: AgentState[];
  isRunning: boolean;
  lang: "he" | "en";
  drawerOpen: boolean;
  onDrawerToggle: () => void;
  channelPopoverOpen: boolean;
  onChannelPopoverToggle: () => void;
}

export function StatusRail({
  agents,
  isRunning,
  lang,
  drawerOpen,
  onDrawerToggle,
  channelPopoverOpen,
  onChannelPopoverToggle,
}: StatusRailProps) {
  const messages = usePipelineStore((s) => s.messages);
  const setFeedStatusFilter = usePipelineStore((s) => s.setFeedStatusFilter);
  const feedStatusFilter = usePipelineStore((s) => s.feedStatusFilter);
  const { sourceChannels, targetChannel } = useSettingsStore();
  const channelAnchorRef = useRef<HTMLButtonElement>(null);

  const healthyCount = agents.filter((a) => a.status !== "error").length;
  const totalCount = agents.length;

  // Compute counters from messages
  const counts = useMemo(() => {
    const active = messages.filter((m) => m.status !== "archived");
    return {
      reviewing: active.filter((m) => m.status === "reviewing").length,
      published: active.filter((m) => m.status === "published").length,
      failed: active.filter((m) => m.status === "failed").length,
    };
  }, [messages]);

  const handleCounterClick = (filter: "reviewing" | "published" | "failed") => {
    setFeedStatusFilter(feedStatusFilter === filter ? "all" : filter);
  };

  return (
    <div className="flex h-8 items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 text-[11px]">
      {/* Left — Agent Pips */}
      <button
        onClick={onDrawerToggle}
        className="flex items-center gap-2 rounded px-1.5 py-0.5 transition-colors hover:bg-[var(--bg-tertiary)]"
        title={t("drawer.agents", lang)}
      >
        {agents.map((agent) => (
          <span key={agent.id} className="flex items-center gap-0.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT_COLOR[agent.status] ?? "bg-gray-500"} ${
                agent.status === "running" ? "animate-pulse" : ""
              }`}
            />
            <span className="font-mono text-[10px] text-[var(--text-secondary)]">
              {AGENT_CODES[agent.id] ?? "???"}
            </span>
          </span>
        ))}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={`ms-0.5 h-3 w-3 text-[var(--text-secondary)] transition-transform duration-200 ${
            drawerOpen ? "rotate-180" : ""
          }`}
        >
          <path
            fillRule="evenodd"
            d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Center — Channel Indicator */}
      <div className="relative">
        <button
          ref={channelAnchorRef}
          onClick={onChannelPopoverToggle}
          className="flex items-center gap-1.5 rounded px-1.5 py-0.5 transition-colors hover:bg-[var(--bg-tertiary)]"
        >
          <span className="text-[var(--text-secondary)]">
            {t("rail.src", lang)}:{sourceChannels.length}
          </span>
          <span className="text-[var(--text-secondary)]">→</span>
          <span className="text-[var(--text-primary)]">
            {targetChannel ? `@${targetChannel.replace(/^@/, "")}` : "—"}
          </span>
        </button>
        <ChannelPopover
          open={channelPopoverOpen}
          onClose={onChannelPopoverToggle}
          anchorRef={channelAnchorRef}
        />
      </div>

      {/* Right — Counters + Health */}
      <div className="flex items-center gap-2">
        {counts.reviewing > 0 && (
          <button
            onClick={() => handleCounterClick("reviewing")}
            className={`rounded px-1 py-0.5 font-medium transition-colors ${
              feedStatusFilter === "reviewing"
                ? "bg-yellow-500/20 text-yellow-400"
                : "text-yellow-400 hover:bg-yellow-500/10"
            }`}
          >
            R:{counts.reviewing}
          </button>
        )}
        <button
          onClick={() => handleCounterClick("published")}
          className={`rounded px-1 py-0.5 font-medium transition-colors ${
            feedStatusFilter === "published"
              ? "bg-green-500/20 text-green-400"
              : "text-green-400 hover:bg-green-500/10"
          }`}
        >
          P:{counts.published}
        </button>
        {counts.failed > 0 && (
          <button
            onClick={() => handleCounterClick("failed")}
            className={`rounded px-1 py-0.5 font-medium transition-colors ${
              feedStatusFilter === "failed"
                ? "bg-red-500/20 text-red-400"
                : "text-red-400 hover:bg-red-500/10"
            }`}
          >
            F:{counts.failed}
          </button>
        )}

        <div className="h-3 w-px bg-[var(--border-color)]" />

        {/* Health indicator */}
        <button
          onClick={onDrawerToggle}
          className="flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:bg-[var(--bg-tertiary)]"
          title={t("rail.health", lang)}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              !isRunning
                ? "bg-gray-500"
                : healthyCount === totalCount
                  ? "bg-[var(--accent-green)]"
                  : "bg-[var(--accent-amber)]"
            }`}
          />
          <span className="text-[var(--text-secondary)]">
            {healthyCount}/{totalCount}
          </span>
        </button>
      </div>
    </div>
  );
}
