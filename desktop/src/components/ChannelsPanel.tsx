import { useState, useEffect, useCallback } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { toast } from "../stores/toastStore";
import { t } from "../lib/i18n";

const API = "http://127.0.0.1:8000/api";

interface TelegramChannel {
  id: number;
  title: string;
  username: string;
  participants: number;
  is_megagroup: boolean;
  is_creator: boolean;
  is_admin: boolean;
}

export function ChannelsPanel() {
  const {
    language,
    targetChannel,
    setSourceChannels,
    setTargetChannel,
  } = useSettingsStore();

  const [connected, setConnected] = useState(false);
  const [channels, setChannels] = useState<TelegramChannel[]>([]);
  const [selectedSource, setSelectedSource] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  const ownedChannels = channels.filter((ch) => ch.is_creator || ch.is_admin);

  const fetchChannels = useCallback(async () => {
    try {
      const res = await fetch(`${API}/telegram/channels`);
      if (!res.ok) return;
      const data = await res.json();
      setChannels(data.channels || []);
    } catch {
      setChannels([]);
    }
  }, []);

  useEffect(() => {
    // Telegram connection status
    fetch(`${API}/telegram/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        const isConnected = data.auth_state === "connected" || data.connected;
        setConnected(!!isConnected);
        if (isConnected) fetchChannels();
      })
      .catch(() => {});

    // Load saved channel config
    fetch(`${API}/channels`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.channels?.length) {
          setSelectedSource(new Set(data.channels));
          setSourceChannels(data.channels);
        }
      })
      .catch(() => {});

    // Load saved target channel
    fetch(`${API}/settings`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.target_channel) {
          setTargetChannel(data.target_channel);
        }
      })
      .catch(() => {});
  }, [fetchChannels, setSourceChannels, setTargetChannel]);

  const toggleSource = (identifier: string) => {
    const next = new Set(selectedSource);
    if (next.has(identifier)) next.delete(identifier);
    else next.add(identifier);
    setSelectedSource(next);
  };

  const handleTestSend = async () => {
    if (!targetChannel) return;
    toast.info(t("connection.sending", language));
    try {
      const res = await fetch(`${API}/telegram/test-send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: targetChannel, text: "Orellius Monitor - Test message" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.ok) {
        toast.success(t("success.send_success", language));
      } else {
        toast.error(data.error || t("error.send_failed", language));
      }
    } catch {
      toast.error(t("error.send_failed", language));
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Save target channel
      await fetch(`${API}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_channel: targetChannel }),
      });

      // Sync source channels
      const currentRes = await fetch(`${API}/channels`);
      const currentData = await currentRes.json();
      const existing: string[] = currentData.channels || [];

      for (const ch of existing) {
        if (!selectedSource.has(ch)) {
          await fetch(`${API}/channels/${encodeURIComponent(ch)}`, { method: "DELETE" });
        }
      }
      for (const ch of selectedSource) {
        if (!existing.includes(ch)) {
          await fetch(`${API}/channels`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ channel: ch }),
          });
        }
      }

      setSourceChannels(Array.from(selectedSource));
      toast.success(t("settings.saved", language));
    } catch {
      toast.error(t("error.settings_save", language));
    }
    setSaving(false);
  };

  if (!connected) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <div className="mb-3 text-4xl opacity-20">📡</div>
        <p className="text-sm text-[var(--text-secondary)]">
          {t("channels.go_connection", language)}
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto p-6">
      <h2 className="mb-6 text-lg font-bold text-[var(--text-primary)]">
        {t("channels.title", language)}
      </h2>

      <div className="grid grid-cols-2 gap-6 flex-1">
        {/* ── Source Channels ── */}
        <div className="flex flex-col">
          <div className="mb-2 flex items-center justify-between">
            <label className="text-sm font-medium text-[var(--text-primary)]">
              {t("channels.source", language)}
            </label>
            <button
              onClick={fetchChannels}
              className="text-xs font-medium text-[var(--accent-blue)] transition-opacity hover:opacity-80"
            >
              {t("btn.refresh", language)}
            </button>
          </div>
          <div className="flex-1 min-h-0 space-y-0.5 overflow-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)] p-1.5">
            {channels.length === 0 ? (
              <p className="p-3 text-center text-xs text-[var(--text-secondary)]">
                {t("channels.none_found", language)}
              </p>
            ) : (
              channels.map((ch) => {
                const identifier = ch.username || String(ch.id);
                return (
                  <label
                    key={ch.id}
                    className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 hover:bg-[var(--bg-secondary)]"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSource.has(identifier)}
                      onChange={() => toggleSource(identifier)}
                      className="h-4 w-4 rounded border-[var(--border-color)] accent-[var(--accent-blue)]"
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-[var(--text-primary)]">{ch.title}</span>
                      {ch.username && (
                        <span className="ml-2 text-xs text-[var(--text-secondary)]">
                          @{ch.username}
                        </span>
                      )}
                    </div>
                    <span className="flex-shrink-0 text-xs text-[var(--text-secondary)]">
                      {ch.participants > 0
                        ? `${ch.participants.toLocaleString()} ${t("channels.members", language)}`
                        : ""}
                    </span>
                  </label>
                );
              })
            )}
          </div>
          <p className="mt-1.5 text-xs text-[var(--text-secondary)]">
            {t("channels.selected", language)}: {selectedSource.size}
          </p>
        </div>

        {/* ── Target Channel ── */}
        <div className="flex flex-col">
          <label className="mb-1 block text-sm font-medium text-[var(--text-primary)]">
            {t("channels.target", language)}
          </label>
          <p className="mb-2 text-xs text-[var(--text-secondary)]">
            {t("channels.owned_channels", language)}
          </p>
          <div className="flex gap-2">
            <select
              value={targetChannel}
              onChange={(e) => setTargetChannel(e.target.value)}
              className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
            >
              <option value="">{t("channels.select_target", language)}</option>
              {ownedChannels.length === 0 && (
                <option value="" disabled>
                  {t("channels.no_owned", language)}
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
            <button
              onClick={handleTestSend}
              disabled={!targetChannel}
              className="rounded-md bg-[var(--accent-amber)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {t("btn.test_send", language)}
            </button>
          </div>
        </div>
      </div>

      {/* Save */}
      <div className="mt-6 flex items-center gap-3 border-t border-[var(--border-color)] pt-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-[var(--accent-blue)] px-6 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? t("channels.saving", language) : t("btn.save", language)}
        </button>
      </div>
    </div>
  );
}
