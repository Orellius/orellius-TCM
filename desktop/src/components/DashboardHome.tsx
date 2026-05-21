import { useState, useEffect } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { usePipelineStore } from "../stores/pipelineStore";
import { toast } from "../stores/toastStore";
import { t } from "../lib/i18n";
import type { TabId } from "./TabNav";
import type { SettingsCategoryId } from "./settings/types";

const API = "http://127.0.0.1:8000/api";

interface TelegramUser {
  id: number;
  first_name: string;
  last_name: string;
  phone: string;
  username: string;
}

type AuthState = "disconnected" | "awaiting_code" | "awaiting_2fa" | "connected" | "error";

interface DashboardHomeProps {
  lang: "he" | "en";
  onTabChange: (tab: TabId) => void;
  onTogglePipeline: () => void;
  onNavigateSettings: (category: SettingsCategoryId) => void;
}

export function DashboardHome({ lang, onTabChange, onTogglePipeline, onNavigateSettings }: DashboardHomeProps) {
  const sourceChannels = useSettingsStore((s) => s.sourceChannels);
  const targetChannel = useSettingsStore((s) => s.targetChannel);
  const isRunning = usePipelineStore((s) => s.isRunning);
  const messages = usePipelineStore((s) => s.messages);

  // Auth state
  const [authState, setAuthState] = useState<AuthState>("disconnected");
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState("");

  const processed = messages.filter((m) => m.status === "published" || m.status === "archived").length;
  const reviewing = messages.filter((m) => m.status === "reviewing").length;
  const published = messages.filter((m) => m.status === "published").length;

  // On mount: fetch Telegram status
  useEffect(() => {
    fetch(`${API}/telegram/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setAuthState(data.auth_state || "disconnected");
        if (data.user) setUser(data.user);
        if (data.connected) {
          useSettingsStore.getState().setTelegramConnected(true);
        }
      })
      .catch(() => {});
  }, []);

  /* ── Auth handlers ── */

  const handleConnect = async () => {
    const trimmedPhone = phone.trim();
    if (!trimmedPhone) {
      setAuthError(t("home.phone_label", lang));
      return;
    }
    setAuthError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: trimmedPhone }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.status === "error") {
        setAuthError(data.message || t("error.connect_failed", lang));
        setLoading(false);
        return;
      }

      setAuthState(data.status as AuthState);
      if (data.user) setUser(data.user);
      if (data.status === "connected") {
        useSettingsStore.getState().setTelegramConnected(true);
      }
      if (data.message) toast.info(data.message);
    } catch {
      toast.error(t("error.connect_failed", lang));
    }
    setLoading(false);
  };

  const handleSubmitCode = async () => {
    if (!code.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAuthState(data.status as AuthState);
      if (data.user) setUser(data.user);
      if (data.status === "connected") {
        useSettingsStore.getState().setTelegramConnected(true);
      }
      if (data.message) toast.info(data.message);
    } catch {
      toast.error(t("error.code_submit", lang));
    }
    setLoading(false);
  };

  const handleSubmit2FA = async () => {
    if (!password) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/2fa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAuthState(data.status as AuthState);
      if (data.user) setUser(data.user);
      if (data.status === "connected") {
        useSettingsStore.getState().setTelegramConnected(true);
      }
      if (data.message) toast.info(data.message);
    } catch {
      toast.error(t("error.2fa_submit", lang));
    }
    setLoading(false);
    setPassword("");
  };

  const handleDisconnect = async () => {
    try {
      await fetch(`${API}/telegram/disconnect`, { method: "POST" });
    } catch {
      /* ignore */
    }
    setAuthState("disconnected");
    setUser(null);
    useSettingsStore.getState().setTelegramConnected(false);
  };

  const connectionStatusText = () => {
    if (authState === "connected" && user) {
      const name = [user.first_name, user.last_name].filter(Boolean).join(" ") || "User";
      const handle = user.username ? ` (@${user.username})` : "";
      return `${t("connection.connected_as", lang)} ${name}${handle}`;
    }
    if (authState === "connected" && !user) {
      return `${t("connection.connected_as", lang)} ...`;
    }
    return t("connection.not_connected", lang);
  };

  /* ── Education block (inline) ── */

  function EducationBlock({ text }: { text: string }) {
    return (
      <div className="mb-4 flex gap-3 rounded-lg border-l-2 border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/5 px-4 py-3">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="mt-0.5 h-4 w-4 flex-shrink-0 text-[var(--accent-blue)]"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-sm italic text-[var(--text-secondary)]">{text}</p>
      </div>
    );
  }

  /* ── Connection widget sub-renderers ── */

  function ConnectedBar() {
    return (
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="h-3 w-3 rounded-full bg-[var(--accent-green)] animate-pulse" />
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {connectionStatusText()}
          </span>
        </div>
        <button
          onClick={handleDisconnect}
          className="rounded-md bg-[var(--accent-red)] px-3 py-1.5 text-xs font-medium text-white"
        >
          {t("btn.disconnect", lang)}
        </button>
      </div>
    );
  }

  function AuthFlow() {
    if (authState === "awaiting_code") {
      return (
        <>
          <EducationBlock text={t("home.verify_education", lang)} />
          <div className="flex gap-2">
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmitCode()}
              placeholder={t("home.code_placeholder", lang)}
              dir="ltr"
              className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
              autoFocus
            />
            <button
              onClick={handleSubmitCode}
              disabled={loading || !code.trim()}
              className="rounded-md bg-[var(--accent-green)] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {loading ? "..." : t("btn.submit", lang)}
            </button>
          </div>
        </>
      );
    }

    if (authState === "awaiting_2fa") {
      return (
        <>
          <EducationBlock text={t("home.twofa_education", lang)} />
          <div className="flex gap-2">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit2FA()}
              placeholder={t("home.twofa_placeholder", lang)}
              className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
              autoFocus
            />
            <button
              onClick={handleSubmit2FA}
              disabled={loading || !password}
              className="rounded-md bg-[var(--accent-green)] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {loading ? "..." : t("btn.submit", lang)}
            </button>
          </div>
        </>
      );
    }

    // disconnected / error — phone input
    return (
      <>
        <EducationBlock text={t("home.connect_education", lang)} />
        <div className="mb-3">
          <label className="mb-1.5 block text-sm font-medium text-[var(--text-primary)]">
            {t("home.phone_label", lang)}
          </label>
          <div className="flex gap-2">
            <input
              type="tel"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                setAuthError("");
              }}
              onKeyDown={(e) => e.key === "Enter" && handleConnect()}
              placeholder={t("home.phone_placeholder", lang)}
              dir="ltr"
              className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
            />
            <button
              onClick={handleConnect}
              disabled={loading || !phone.trim()}
              className="rounded-md bg-[var(--accent-blue)] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {loading ? t("connection.connecting", lang) : t("btn.connect", lang)}
            </button>
          </div>
          {authError && (
            <p className="mt-1.5 text-xs text-[var(--accent-red)]">{authError}</p>
          )}
        </div>
      </>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6">
      <h2 className="mb-6 text-lg font-bold text-[var(--text-primary)]">{t("home.title", lang)}</h2>

      {/* Connection — full width */}
      <div className="mb-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
        <h3 className="mb-4 text-sm font-semibold text-[var(--text-secondary)]">{t("home.connection", lang)}</h3>
        {authState === "connected" ? <ConnectedBar /> : <AuthFlow />}
      </div>

      {/* Pipeline + Channels — side by side */}
      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* -- Pipeline Status Card -- */}
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h3 className="mb-4 text-sm font-semibold text-[var(--text-secondary)]">{t("home.pipeline_status", lang)}</h3>
          <div className="mb-4 flex items-center gap-3">
            <span className={`h-3 w-3 rounded-full ${isRunning ? "bg-[var(--accent-green)] animate-pulse" : "bg-[var(--text-secondary)]"}`} />
            <span className="text-sm font-medium text-[var(--text-primary)]">
              {isRunning ? t("pipeline.active", lang) : t("pipeline.stopped", lang)}
            </span>
          </div>
          <div className="mb-4 grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-[var(--bg-primary)] p-3 text-center">
              <div className="text-xl font-bold text-[var(--text-primary)]">{processed}</div>
              <div className="text-[10px] text-[var(--text-secondary)]">{t("home.stats_processed", lang)}</div>
            </div>
            <div className="rounded-lg bg-[var(--bg-primary)] p-3 text-center">
              <div className="text-xl font-bold text-[var(--accent-amber)]">{reviewing}</div>
              <div className="text-[10px] text-[var(--text-secondary)]">{t("home.stats_reviewing", lang)}</div>
            </div>
            <div className="rounded-lg bg-[var(--bg-primary)] p-3 text-center">
              <div className="text-xl font-bold text-[var(--accent-green)]">{published}</div>
              <div className="text-[10px] text-[var(--text-secondary)]">{t("home.stats_published", lang)}</div>
            </div>
          </div>
          <button
            onClick={onTogglePipeline}
            className={`w-full rounded-md py-2 text-sm font-medium text-white transition-colors ${
              isRunning ? "bg-[var(--accent-red)] hover:bg-red-600" : "bg-[var(--accent-green)] hover:bg-green-600"
            }`}
          >
            {isRunning ? t("btn.stop", lang) : t("btn.start", lang)}
          </button>
        </div>

        {/* -- Channels Card -- */}
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
          <h3 className="mb-4 text-sm font-semibold text-[var(--text-secondary)]">{t("home.channels", lang)}</h3>
          {sourceChannels.length === 0 ? (
            <p className="text-xs text-[var(--text-secondary)]">{t("home.no_channels", lang)}</p>
          ) : (
            <div className="space-y-1.5">
              <div className="text-xs text-[var(--text-secondary)]">
                {sourceChannels.length} {t("channels.source", lang).toLowerCase()}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {sourceChannels.slice(0, 6).map((ch) => (
                  <span key={ch} className="rounded-md bg-[var(--bg-primary)] px-2 py-1 text-xs text-[var(--text-primary)]">
                    {ch.startsWith("@") ? ch : `@${ch}`}
                  </span>
                ))}
                {sourceChannels.length > 6 && (
                  <span className="rounded-md bg-[var(--bg-primary)] px-2 py-1 text-xs text-[var(--text-secondary)]">
                    +{sourceChannels.length - 6}
                  </span>
                )}
              </div>
              {targetChannel && (
                <div className="mt-2 text-xs text-[var(--text-secondary)]">
                  {t("channels.target", lang)}: <span className="font-medium text-[var(--text-primary)]">@{targetChannel}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions — full width, horizontal pills */}
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
        <h3 className="mb-4 text-sm font-semibold text-[var(--text-secondary)]">{t("home.quick_actions", lang)}</h3>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onTabChange("pipeline")}
            className="rounded-full border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-2 text-sm text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-tertiary)]"
          >
            {t("tab.pipeline", lang)}
          </button>
          <button
            onClick={() => onTabChange("settings")}
            className="rounded-full border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-2 text-sm text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-tertiary)]"
          >
            {t("home.open_settings", lang)}
          </button>
          <button
            onClick={() => onNavigateSettings("system")}
            className="rounded-full border border-[var(--border-color)] bg-[var(--bg-primary)] px-4 py-2 text-sm text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-tertiary)]"
          >
            {t("home.view_logs", lang)}
          </button>
        </div>
      </div>
    </div>
  );
}
