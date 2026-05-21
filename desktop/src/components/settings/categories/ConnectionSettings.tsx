import { useState, useEffect, useCallback, useMemo } from "react";
import { useSettingsStore } from "../../../stores/settingsStore";
import { usePipelineStore } from "../../../stores/pipelineStore";
import { toast } from "../../../stores/toastStore";
import { t } from "../../../lib/i18n";
import { api } from "../../../lib/api";
import { Toggle } from "../shared/Toggle";
import { SettingRow } from "../shared/SettingRow";
import { SirenIcon } from "../shared/settingsIcons";

const API = "http://127.0.0.1:8000/api";

interface TelegramUser {
  id: number;
  first_name: string;
  last_name: string;
  phone: string;
  username: string;
}

interface TelegramChannel {
  id: number;
  title: string;
  username: string;
  participants: number;
  is_megagroup: boolean;
  is_creator: boolean;
  is_admin: boolean;
}

type AuthState = "disconnected" | "awaiting_code" | "awaiting_2fa" | "connected" | "error";

/** Normalize a channel identifier for comparison — strip leading @ and lowercase. */
function normalizeId(raw: string): string {
  return raw.replace(/^@/, "").trim().toLowerCase();
}

/** Build the canonical identifier for a Telegram channel object. */
function channelIdentifier(ch: TelegramChannel): string {
  return ch.username || String(ch.id);
}

export function ConnectionSettings() {
  const lang = useSettingsStore((s) => s.language);
  const { targetChannel, setSourceChannels, setTargetChannel } = useSettingsStore();

  const [authState, setAuthState] = useState<AuthState>("disconnected");
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [channels, setChannels] = useState<TelegramChannel[]>([]);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedSource, setSelectedSource] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [channelsLoading, setChannelsLoading] = useState(false);

  // Saved channels from backend (the "truth" for what's currently configured)
  const [savedChannels, setSavedChannels] = useState<string[]>([]);

  // HFC state
  const hfcRunning = usePipelineStore((s) => s.hfcRunning);
  const hfcGeoBlocked = usePipelineStore((s) => s.hfcGeoBlocked);
  const hfcPollerHealthy = usePipelineStore((s) => s.hfcPollerHealthy);
  const [hfcTesting, setHfcTesting] = useState(false);

  const ownedChannels = channels.filter((ch) => ch.is_creator || ch.is_admin);

  // Build a normalized lookup: normalizedId -> true, for fast checkbox matching
  const selectedNormalized = useMemo(() => {
    const map = new Map<string, string>();
    for (const id of selectedSource) {
      map.set(normalizeId(id), id);
    }
    return map;
  }, [selectedSource]);

  // Orphaned channels: saved in backend but not found in Telegram channel list
  const orphanedChannels = useMemo(() => {
    if (channels.length === 0) return [];
    const telegramIds = new Set(channels.map((ch) => normalizeId(channelIdentifier(ch))));
    return savedChannels.filter((ch) => !telegramIds.has(normalizeId(ch)));
  }, [channels, savedChannels]);

  // Whether user has unsaved changes
  const hasChanges = useMemo(() => {
    const savedSet = new Set(savedChannels.map(normalizeId));
    const currentSet = new Set([...selectedSource].map(normalizeId));
    if (savedSet.size !== currentSet.size) return true;
    for (const id of savedSet) {
      if (!currentSet.has(id)) return true;
    }
    return false;
  }, [savedChannels, selectedSource]);

  const fetchChannels = useCallback(async () => {
    setChannelsLoading(true);
    try {
      const res = await fetch(`${API}/telegram/channels`);
      if (!res.ok) {
        toast.error(t("error.generic", lang));
        return;
      }
      const data = await res.json();
      const fetched: TelegramChannel[] = data.channels || [];
      setChannels(fetched);
    } catch {
      toast.error(t("error.generic", lang));
      setChannels([]);
    } finally {
      setChannelsLoading(false);
    }
  }, [lang]);

  // Load saved channels from backend AND reconcile with selectedSource
  const loadSavedChannels = useCallback(async () => {
    try {
      const res = await fetch(`${API}/channels`);
      if (!res.ok) return;
      const data = await res.json();
      const saved: string[] = data.channels || [];
      setSavedChannels(saved);
      // Initialize selection from saved channels
      setSelectedSource(new Set(saved));
      setSourceChannels(saved);
    } catch {
      /* silent */
    }
  }, [setSourceChannels]);

  useEffect(() => {
    fetch(`${API}/telegram/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        setAuthState(data.auth_state || "disconnected");
        if (data.user) setUser(data.user);
        if (data.connected) fetchChannels();
      })
      .catch(() => {});

    loadSavedChannels();

    fetch(`${API}/settings`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.target_channel) setTargetChannel(data.target_channel);
      })
      .catch(() => {});
  }, [fetchChannels, loadSavedChannels, setTargetChannel]);

  /* ── Auth handlers ── */

  const handleConnect = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/connect`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAuthState(data.status);
      if (data.user) setUser(data.user);
      if (data.status === "connected") fetchChannels();
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
      setAuthState(data.status);
      if (data.user) setUser(data.user);
      if (data.status === "connected") fetchChannels();
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
      setAuthState(data.status);
      if (data.user) setUser(data.user);
      if (data.status === "connected") fetchChannels();
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
    setChannels([]);
  };

  /* ── Channel selection helpers ── */

  const isChannelSelected = (ch: TelegramChannel): boolean => {
    const id = channelIdentifier(ch);
    return selectedNormalized.has(normalizeId(id));
  };

  const toggleSource = (ch: TelegramChannel) => {
    const id = channelIdentifier(ch);
    const normId = normalizeId(id);
    const next = new Set(selectedSource);

    // Find and remove by normalized match (handles @prefix mismatches)
    const existing = selectedNormalized.get(normId);
    if (existing) {
      next.delete(existing);
    } else {
      next.add(id);
    }
    setSelectedSource(next);
  };

  const handleSelectAll = () => {
    const next = new Set(selectedSource);
    for (const ch of channels) {
      const id = channelIdentifier(ch);
      if (!selectedNormalized.has(normalizeId(id))) {
        next.add(id);
      }
    }
    setSelectedSource(next);
  };

  const handleDeselectAll = () => {
    // Only remove channels that are in the visible Telegram list
    const telegramNormIds = new Set(channels.map((ch) => normalizeId(channelIdentifier(ch))));
    const next = new Set<string>();
    // Keep orphaned channels (not in Telegram list) — they'll be handled separately
    for (const id of selectedSource) {
      if (!telegramNormIds.has(normalizeId(id))) {
        next.add(id);
      }
    }
    setSelectedSource(next);
  };

  const handleRemoveOrphaned = () => {
    const orphanNorm = new Set(orphanedChannels.map(normalizeId));
    const next = new Set<string>();
    for (const id of selectedSource) {
      if (!orphanNorm.has(normalizeId(id))) {
        next.add(id);
      }
    }
    setSelectedSource(next);
  };

  const handleSaveChannels = async () => {
    setSaving(true);
    try {
      // Save target channel
      await fetch(`${API}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_channel: targetChannel }),
      });

      // Compute diff against current backend state
      const currentRes = await fetch(`${API}/channels`);
      const currentData = await currentRes.json();
      const existing: string[] = currentData.channels || [];

      const existingNorm = new Map<string, string>();
      for (const ch of existing) existingNorm.set(normalizeId(ch), ch);

      const selectedNorm = new Map<string, string>();
      for (const ch of selectedSource) selectedNorm.set(normalizeId(ch), ch);

      // Remove channels no longer selected
      const toRemove = existing.filter((ch) => !selectedNorm.has(normalizeId(ch)));
      // Add channels newly selected
      const toAdd = [...selectedSource].filter((ch) => !existingNorm.has(normalizeId(ch)));

      const errors: string[] = [];

      for (const ch of toRemove) {
        try {
          await fetch(`${API}/channels/${encodeURIComponent(ch)}`, { method: "DELETE" });
        } catch {
          errors.push(`Remove ${ch}`);
        }
      }
      for (const ch of toAdd) {
        try {
          await fetch(`${API}/channels`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ channel: ch }),
          });
        } catch {
          errors.push(`Add ${ch}`);
        }
      }

      if (errors.length > 0) {
        toast.error(`${t("error.channels_save", lang)}: ${errors.join(", ")}`);
      } else {
        toast.success(t("success.channels_saved", lang));
      }

      // Re-sync from backend to confirm
      await loadSavedChannels();
    } catch {
      toast.error(t("error.channels_save", lang));
    }
    setSaving(false);
  };

  /* ── HFC handlers ── */

  const handleHfcToggle = async (enabled: boolean) => {
    try {
      if (enabled) {
        await api.hfcStart();
        usePipelineStore.setState({ hfcRunning: true });
      } else {
        await api.hfcStop();
        usePipelineStore.setState({ hfcRunning: false });
      }
    } catch {
      toast.error(t("error.generic", lang));
    }
  };

  const handleHfcTest = async () => {
    setHfcTesting(true);
    try {
      const res = await api.hfcTest();
      if (res.ok && res.connected) {
        toast.success(t("settings.hfc_test_ok", lang));
      } else if (res.geo_blocked) {
        toast.error(t("settings.hfc_geo_blocked", lang));
      } else {
        toast.error(res.error || t("error.generic", lang));
      }
    } catch {
      toast.error(t("error.generic", lang));
    }
    setHfcTesting(false);
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
    if (authState === "awaiting_code") return t("connection.enter_code", lang);
    if (authState === "awaiting_2fa") return t("connection.enter_2fa", lang);
    return t("connection.not_connected", lang);
  };

  // Count how many visible Telegram channels are selected
  const visibleSelectedCount = channels.filter((ch) => isChannelSelected(ch)).length;
  const allVisibleSelected = channels.length > 0 && visibleSelectedCount === channels.length;

  return (
    <div className="space-y-8">
      {/* ── Telegram Connection ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("connection.title", lang)}
        </h3>

        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={`h-3 w-3 rounded-full ${authState === "connected" ? "bg-[var(--accent-green)]" : "bg-[var(--text-secondary)]"}`}
              />
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {connectionStatusText()}
              </span>
            </div>
            {authState === "connected" ? (
              <button
                onClick={handleDisconnect}
                className="rounded-md bg-[var(--accent-red)] px-3 py-1.5 text-xs font-medium text-white"
              >
                {t("btn.disconnect", lang)}
              </button>
            ) : authState === "disconnected" || authState === "error" ? (
              <button
                onClick={handleConnect}
                disabled={loading}
                className="rounded-md bg-[var(--accent-blue)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              >
                {loading ? t("connection.connecting", lang) : t("btn.connect", lang)}
              </button>
            ) : null}
          </div>

          {authState === "awaiting_code" && (
            <div className="mt-4 flex gap-2">
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmitCode()}
                placeholder={t("connection.code_placeholder", lang)}
                className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                autoFocus
              />
              <button
                onClick={handleSubmitCode}
                disabled={loading || !code.trim()}
                className="rounded-md bg-[var(--accent-green)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {loading ? "..." : t("btn.submit", lang)}
              </button>
            </div>
          )}

          {authState === "awaiting_2fa" && (
            <div className="mt-4 flex gap-2">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit2FA()}
                placeholder={t("connection.2fa_placeholder", lang)}
                className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                autoFocus
              />
              <button
                onClick={handleSubmit2FA}
                disabled={loading || !password}
                className="rounded-md bg-[var(--accent-green)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {loading ? "..." : t("btn.submit", lang)}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── Channel Selection ── */}
      {authState === "connected" && (
        <div>
          {/* Source Channels */}
          <div className="mb-6">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                {t("channels.source", lang)}
              </h3>
              <div className="flex items-center gap-3">
                {channels.length > 0 && (
                  <>
                    <button
                      onClick={allVisibleSelected ? handleDeselectAll : handleSelectAll}
                      className="text-xs text-[var(--accent-blue)] hover:underline"
                    >
                      {allVisibleSelected
                        ? (lang === "he" ? "בטל הכל" : "Deselect All")
                        : (lang === "he" ? "בחר הכל" : "Select All")}
                    </button>
                    <span className="text-xs text-[var(--text-secondary)]">|</span>
                  </>
                )}
                <button
                  onClick={fetchChannels}
                  disabled={channelsLoading}
                  className="text-xs text-[var(--accent-blue)] hover:underline disabled:opacity-50"
                >
                  {channelsLoading ? "..." : t("btn.refresh", lang)}
                </button>
              </div>
            </div>
            <div className="max-h-60 space-y-1 overflow-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-2">
              {channelsLoading ? (
                <p className="p-3 text-center text-xs text-[var(--text-secondary)]">
                  {lang === "he" ? "טוען ערוצים..." : "Loading channels..."}
                </p>
              ) : channels.length === 0 ? (
                <p className="p-3 text-center text-xs text-[var(--text-secondary)]">
                  {t("channels.none_found", lang)}
                </p>
              ) : (
                channels.map((ch) => {
                  const selected = isChannelSelected(ch);
                  return (
                    <label
                      key={ch.id}
                      className={`flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 transition-colors ${
                        selected
                          ? "bg-[var(--accent-blue)]/5"
                          : "hover:bg-[var(--bg-tertiary)]"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleSource(ch)}
                        className="h-4 w-4 rounded border-[var(--border-color)] accent-[var(--accent-blue)]"
                      />
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-[var(--text-primary)]">{ch.title}</span>
                        {ch.username && (
                          <span className="ml-2 text-xs text-[var(--text-secondary)]">@{ch.username}</span>
                        )}
                      </div>
                      <span className="shrink-0 text-xs text-[var(--text-secondary)]">
                        {ch.participants > 0
                          ? `${ch.participants.toLocaleString()} ${t("channels.members", lang)}`
                          : ""}
                      </span>
                    </label>
                  );
                })
              )}
            </div>
            <div className="mt-1.5 flex items-center justify-between">
              <p className="text-xs text-[var(--text-secondary)]">
                {t("channels.selected", lang)}: {visibleSelectedCount}
                {orphanedChannels.length > 0 && (
                  <span className="text-amber-400">
                    {" "}+ {orphanedChannels.length} {lang === "he" ? "לא נמצאו בטלגרם" : "not found in Telegram"}
                  </span>
                )}
              </p>
              {hasChanges && (
                <span className="text-xs font-medium text-amber-400">
                  {lang === "he" ? "שינויים לא נשמרו" : "Unsaved changes"}
                </span>
              )}
            </div>
          </div>

          {/* Orphaned Channels Warning */}
          {orphanedChannels.length > 0 && (
            <div className="mb-6 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-medium text-amber-400">
                  {lang === "he"
                    ? `${orphanedChannels.length} ערוצים שמורים לא נמצאו ברשימת הטלגרם`
                    : `${orphanedChannels.length} saved channel(s) not found in your Telegram list`}
                </p>
                <button
                  onClick={handleRemoveOrphaned}
                  className="rounded-md bg-amber-600/20 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-600/30"
                >
                  {lang === "he" ? "הסר הכל" : "Remove All"}
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {orphanedChannels.map((ch) => (
                  <span
                    key={ch}
                    className="rounded-md bg-amber-600/10 px-2 py-0.5 text-xs text-amber-400"
                  >
                    {ch}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Target Channel */}
          <div className="mb-6">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              {t("channels.target", lang)}
            </h3>
            <p className="mb-2 text-xs text-[var(--text-secondary)]">
              {t("channels.owned_channels", lang)}
            </p>
            <div className="flex gap-2">
              <select
                value={targetChannel}
                onChange={(e) => setTargetChannel(e.target.value)}
                className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
              >
                <option value="">{t("channels.select_target", lang)}</option>
                {ownedChannels.length === 0 && (
                  <option value="" disabled>
                    {t("channels.no_owned", lang)}
                  </option>
                )}
                {ownedChannels.map((ch) => {
                  const identifier = ch.username ? `@${ch.username}` : String(ch.id);
                  return (
                    <option key={ch.id} value={ch.username || String(ch.id)}>
                      {ch.title} ({identifier})
                    </option>
                  );
                })}
              </select>
            </div>
          </div>

          {/* Save Channels */}
          <button
            onClick={handleSaveChannels}
            disabled={saving || (selectedSource.size === 0 && !targetChannel)}
            className={`rounded-md px-6 py-2 text-sm font-medium text-white disabled:opacity-50 transition-colors ${
              hasChanges
                ? "bg-[var(--accent-amber)] hover:bg-[var(--accent-amber)]/80"
                : "bg-[var(--accent-blue)]"
            }`}
          >
            {saving ? t("channels.saving", lang) : t("btn.save_channels", lang)}
          </button>
        </div>
      )}

      {/* ── HFC Alerts ── */}
      <div>
        <div className="mb-4 flex items-center gap-2 text-base font-semibold text-[var(--text-primary)]">
          <SirenIcon />
          {t("settings.hfc", lang)}
        </div>

        <div className="space-y-4">
          <SettingRow label={t("settings.hfc_enabled", lang)} description={t("settings.hfc_desc", lang)}>
            <Toggle checked={hfcRunning} onChange={handleHfcToggle} />
          </SettingRow>

          {hfcRunning && (
            <div className="space-y-1.5 ps-2">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-green-400 animate-pulse" />
                <span className="text-xs text-[var(--text-secondary)]">
                  {t("settings.hfc_running", lang)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${hfcPollerHealthy ? "bg-green-400" : "bg-amber-400 animate-pulse"}`}
                />
                <span className="text-xs text-[var(--text-secondary)]">
                  {t(hfcPollerHealthy ? "settings.hfc_poller_healthy" : "settings.hfc_poller_degraded", lang)}
                </span>
              </div>
            </div>
          )}

          {hfcGeoBlocked && (
            <div className="rounded-md bg-amber-600/10 px-3 py-2">
              <p className="text-xs font-medium text-amber-400">
                {t("settings.hfc_geo_blocked", lang)}
              </p>
            </div>
          )}

          <button
            onClick={handleHfcTest}
            disabled={hfcTesting}
            className="rounded-md bg-[var(--bg-tertiary)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)] hover:text-[var(--text-primary)] disabled:opacity-50"
          >
            {hfcTesting ? t("connection.sending", lang) : t("settings.hfc_test", lang)}
          </button>
        </div>
      </div>
    </div>
  );
}
