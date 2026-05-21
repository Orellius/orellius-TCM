import { useState, useMemo } from "react";
import { usePipelineStore } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { toast } from "../stores/toastStore";
import { TabNav, type TabId } from "./TabNav";
import { MessageFeed } from "./MessageFeed";
import { MessageDossier } from "./MessageDossier";
import { StatusRail } from "./StatusRail";
import { AgentDrawer } from "./AgentDrawer";
import { SettingsPanel } from "./settings/SettingsPanel";
import type { SettingsCategoryId } from "./settings/types";
import { ArchivePanel } from "./ArchivePanel";
import { TemplateEditor } from "./TemplateEditor";
import { ReplacementsPanel } from "./ReplacementsPanel";
import { ChannelDiscovery } from "./ChannelDiscovery";
import { ChannelsPanel } from "./ChannelsPanel";
import { DashboardHome } from "./DashboardHome";
import { api } from "../lib/api";
import { t } from "../lib/i18n";
import packageJson from "../../package.json";

export function Dashboard() {
  const isRunning = usePipelineStore((s) => s.isRunning);
  const agents = usePipelineStore((s) => s.agents);
  const messages = usePipelineStore((s) => s.messages);
  const setRunning = usePipelineStore((s) => s.setRunning);
  const lang = useSettingsStore((s) => s.language);
  const [activeTab, setActiveTab] = useState<TabId>("home");
  const telegramConnected = useSettingsStore((s) => s.telegramConnected);
  const [settingsCategory, setSettingsCategory] = useState<SettingsCategoryId | undefined>();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [channelPopoverOpen, setChannelPopoverOpen] = useState(false);

  const navigateToSettings = (category?: SettingsCategoryId) => {
    setSettingsCategory(category);
    setActiveTab("settings");
  };

  // Compute badge counts for tab indicators
  const badges = useMemo(() => {
    const reviewing = messages.filter((m) => m.status === "reviewing").length;
    return reviewing > 0 ? { pipeline: reviewing } : {};
  }, [messages]);

  const handleTogglePipeline = async () => {
    try {
      if (isRunning) {
        await api.stopPipeline();
        setRunning(false);
        toast.success(t("success.pipeline_stopped", lang));
      } else {
        const res = await api.startPipeline();
        if (res.error) {
          toast.error(res.error);
          return;
        }
        setRunning(true);
        toast.success(t("success.pipeline_started", lang));
      }
    } catch (err) {
      console.error("Pipeline toggle failed:", err);
      toast.error(t("error.pipeline_toggle", lang));
    }
  };

  return (
    <div className="flex h-full w-full flex-col" dir={lang === "he" ? "rtl" : "ltr"}>
      {/* Top Bar */}
      <header className="flex items-center justify-between border-b border-[var(--border-color)] bg-[var(--bg-secondary)] px-5 py-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Orellius
          </h1>
          <span className={`h-2.5 w-2.5 rounded-full ${telegramConnected ? "bg-[var(--accent-green)]" : "bg-[var(--accent-red)]"}`} title={telegramConnected ? "Connected" : "Disconnected"} />
          <span className="text-[10px] text-[var(--text-secondary)]">v{packageJson.version}</span>
        </div>

        {/* Tabs */}
        <TabNav
          activeTab={activeTab}
          onTabChange={setActiveTab}
          lang={lang}
          badges={badges}
        />

        {/* Pipeline Controls */}
        <div className="flex items-center gap-3">
          <span className={`h-2 w-2 rounded-full ${isRunning ? "bg-[var(--accent-green)] animate-pulse" : "bg-[var(--text-secondary)]"}`} />
          <span className="text-xs text-[var(--text-secondary)]">
            {isRunning ? t("pipeline.active", lang) : t("pipeline.stopped", lang)}
          </span>
          <button
            onClick={handleTogglePipeline}
            className={`rounded-md px-4 py-2 text-sm font-medium text-white transition-colors ${
              isRunning
                ? "bg-[var(--accent-red)] hover:bg-red-600"
                : "bg-[var(--accent-green)] hover:bg-green-600"
            }`}
          >
            {isRunning ? t("btn.stop", lang) : t("btn.start", lang)}
          </button>
        </div>
      </header>

      {/* Tab Content */}
      {activeTab === "home" && (
        <DashboardHome
          lang={lang}
          onTabChange={setActiveTab}
          onTogglePipeline={handleTogglePipeline}
          onNavigateSettings={navigateToSettings}
        />
      )}

      {activeTab === "pipeline" && (
        <div className="flex flex-1 flex-col overflow-hidden">
          <StatusRail
            agents={agents}
            isRunning={isRunning}
            lang={lang}
            drawerOpen={drawerOpen}
            onDrawerToggle={() => setDrawerOpen((p) => !p)}
            channelPopoverOpen={channelPopoverOpen}
            onChannelPopoverToggle={() => setChannelPopoverOpen((p) => !p)}
          />
          <AgentDrawer agents={agents} isRunning={isRunning} isOpen={drawerOpen} lang={lang} />

          <div className="flex flex-1 overflow-hidden">
            <div className="flex w-[28rem] flex-col border-e border-[var(--border-color)] bg-[var(--bg-primary)]">
              <MessageFeed />
            </div>
            <main className="flex flex-1 flex-col overflow-hidden bg-[var(--bg-primary)]">
              <MessageDossier />
            </main>
          </div>
        </div>
      )}

      {activeTab === "channels" && (
        <div className="flex-1 overflow-auto">
          <ChannelsPanel />
        </div>
      )}
      {activeTab === "templates" && (
        <div className="flex flex-1 flex-col overflow-hidden">
          <TemplateEditor />
        </div>
      )}
      {activeTab === "replacements" && (
        <div className="flex-1 overflow-auto">
          <ReplacementsPanel />
        </div>
      )}
      {activeTab === "archive" && (
        <div className="flex-1 overflow-auto">
          <ArchivePanel />
        </div>
      )}
      {activeTab === "intel" && (
        <div className="flex-1 overflow-auto">
          <ChannelDiscovery />
        </div>
      )}
      {activeTab === "settings" && (
        <div className="flex-1 overflow-hidden">
          <SettingsPanel initialCategory={settingsCategory} />
        </div>
      )}
    </div>
  );
}
