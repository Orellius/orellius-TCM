import { useState } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { toast } from "../stores/toastStore";
import { api } from "../lib/api";
import { t, type Lang } from "../lib/i18n";

interface DiscoveredChannel {
  channel_id: string | null;
  title: string;
  username: string | null;
  discovery_method: string;
  discovered_from: string;
  depth: number;
}

interface ChannelProfile {
  channel: string;
  message_count: number;
  posts_per_hour: number;
  peak_hours: number[];
  hour_distribution: Record<number, number>;
  media_distribution: Record<string, number>;
  top_forward_sources: Record<string, number>;
  avg_views: number;
  date_range: { oldest: string | null; newest: string | null };
  profiled_at: number;
  error?: string;
}

interface HistoryMessage {
  message_id: number;
  date: string | null;
  text: string;
  has_media: boolean;
  media_type: string;
  views: number | null;
}

export function ChannelDiscovery() {
  const lang = useSettingsStore((s) => s.language);

  const [seedChannel, setSeedChannel] = useState("");
  const [depth, setDepth] = useState(1);
  const [discovering, setDiscovering] = useState(false);
  const [discovered, setDiscovered] = useState<DiscoveredChannel[]>([]);

  const [profiles, setProfiles] = useState<Record<string, ChannelProfile>>({});
  const [profilingChannel, setProfilingChannel] = useState<string | null>(null);

  const [historyChannel, setHistoryChannel] = useState<string | null>(null);
  const [historyMessages, setHistoryMessages] = useState<HistoryMessage[]>([]);
  const [scraping, setScraping] = useState(false);

  const handleDiscover = async () => {
    if (!seedChannel.trim()) return;
    setDiscovering(true);
    setDiscovered([]);
    try {
      const res = await api.discoverChannels(seedChannel.trim(), depth);
      setDiscovered(res.channels || []);
    } catch {
      toast.error(t("error.discover_failed", lang));
    } finally {
      setDiscovering(false);
    }
  };

  const handleProfile = async (channel: string) => {
    setProfilingChannel(channel);
    try {
      const res = await api.profileChannel(channel);
      setProfiles((prev) => ({ ...prev, [channel]: res.profile }));
    } catch {
      toast.error(t("error.profile_failed", lang));
    } finally {
      setProfilingChannel(null);
    }
  };

  const handleScrape = async (channel: string) => {
    setHistoryChannel(channel);
    setScraping(true);
    setHistoryMessages([]);
    try {
      const res = await api.scrapeChannel(channel);
      setHistoryMessages(res.messages || []);
    } catch {
      toast.error(t("error.scrape_failed", lang));
    } finally {
      setScraping(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-auto p-6">
      <h2 className="mb-2 text-lg font-bold text-[var(--text-primary)]">
        {t("intel.title", lang)}
      </h2>
      <p className="mb-6 text-xs text-[var(--text-secondary)]">
        {t("intel.desc", lang)}
      </p>

      {/* Seed Input */}
      <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {t("intel.discover", lang)}
        </h3>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-xs text-[var(--text-secondary)]">
              {t("intel.seed_channel", lang)}
            </label>
            <input
              type="text"
              value={seedChannel}
              onChange={(e) => setSeedChannel(e.target.value)}
              placeholder="@channel_name"
              className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
              onKeyDown={(e) => e.key === "Enter" && handleDiscover()}
            />
          </div>
          <div className="w-20">
            <label className="mb-1 block text-xs text-[var(--text-secondary)]">
              {t("intel.depth", lang)}
            </label>
            <input
              type="number"
              min={1}
              max={3}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
            />
          </div>
          <button
            onClick={handleDiscover}
            disabled={discovering || !seedChannel.trim()}
            className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {discovering ? t("intel.discovering", lang) : t("intel.discover_btn", lang)}
          </button>
        </div>
      </div>

      {/* Discovered Channels */}
      {discovered.length > 0 && (
        <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t("intel.discovered", lang)} ({discovered.length})
          </h3>
          <div className="space-y-2">
            {discovered.map((ch, i) => (
              <div
                key={ch.channel_id ?? ch.username ?? `disc-${i}`}
                className="flex items-center justify-between rounded-md bg-[var(--bg-tertiary)] px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {ch.username ? `@${ch.username}` : ch.title}
                  </span>
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      ch.discovery_method === "forward"
                        ? "bg-purple-500/10 text-purple-400"
                        : "bg-blue-500/10 text-blue-400"
                    }`}
                  >
                    {ch.discovery_method}
                  </span>
                  <span className="text-[10px] text-[var(--text-secondary)]">
                    {t("intel.from_source", lang)} {ch.discovered_from}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => handleProfile(ch.username || ch.channel_id || "")}
                    disabled={profilingChannel === (ch.username || ch.channel_id)}
                    className="rounded bg-[var(--bg-primary)] px-2 py-1 text-[10px] font-medium text-[var(--accent-blue)] transition-colors hover:bg-[var(--accent-blue)] hover:text-white disabled:opacity-50"
                  >
                    {t("intel.profile_btn", lang)}
                  </button>
                  <button
                    onClick={() => handleScrape(ch.username || ch.channel_id || "")}
                    disabled={scraping}
                    className="rounded bg-[var(--bg-primary)] px-2 py-1 text-[10px] font-medium text-[var(--accent-green)] transition-colors hover:bg-[var(--accent-green)] hover:text-white disabled:opacity-50"
                  >
                    {t("intel.scrape_btn", lang)}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Channel Profiles */}
      {Object.keys(profiles).length > 0 && (
        <div className="mb-6 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t("intel.profiles", lang)}
          </h3>
          <div className="space-y-3">
            {Object.entries(profiles).map(([ch, profile]) => (
              <ProfileCard key={ch} profile={profile} lang={lang} />
            ))}
          </div>
        </div>
      )}

      {/* History Scrape Results */}
      {historyChannel && (
        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t("intel.history", lang)}: {historyChannel}
            {scraping && <span className="ml-2 text-amber-400 animate-pulse">...</span>}
          </h3>
          {historyMessages.length > 0 ? (
            <div className="max-h-96 space-y-1 overflow-y-auto">
              {historyMessages.map((msg) => (
                <div
                  key={msg.message_id}
                  className="flex items-start gap-2 rounded bg-[var(--bg-tertiary)] px-2 py-1.5 text-xs"
                >
                  <span className="shrink-0 text-[var(--text-secondary)] font-mono w-12">
                    #{msg.message_id}
                  </span>
                  <span className="shrink-0 text-[var(--text-secondary)] w-16">
                    {msg.date ? new Date(msg.date).toLocaleTimeString() : "?"}
                  </span>
                  {msg.has_media && (
                    <span className="shrink-0 rounded bg-blue-500/10 px-1 text-[10px] text-blue-400">
                      {msg.media_type}
                    </span>
                  )}
                  <span className="text-[var(--text-primary)] line-clamp-1">
                    {msg.text || "(no text)"}
                  </span>
                  {msg.views != null && (
                    <span className="ms-auto shrink-0 text-[var(--text-secondary)]">
                      {msg.views.toLocaleString()} views
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            !scraping && (
              <p className="text-xs text-[var(--text-secondary)]">{t("intel.no_history", lang)}</p>
            )
          )}
        </div>
      )}
    </div>
  );
}

/** Profile card for a single channel. */
function ProfileCard({ profile, lang }: { profile: ChannelProfile; lang: Lang }) {
  if (profile.error) {
    return (
      <div className="rounded-md bg-[var(--bg-tertiary)] p-3">
        <span className="text-sm font-medium text-[var(--text-primary)]">{profile.channel}</span>
        <span className="ml-2 text-xs text-red-400">{profile.error}</span>
      </div>
    );
  }

  const maxHour = Math.max(...Object.values(profile.hour_distribution), 1);

  return (
    <div className="rounded-md bg-[var(--bg-tertiary)] p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--text-primary)]">{profile.channel}</span>
        <span className="text-[10px] text-[var(--text-secondary)]">
          {profile.message_count} {t("intel.msgs", lang)} | {profile.posts_per_hour} {t("intel.posts_hr", lang)} | {t("intel.avg_views", lang).replace("{n}", String(profile.avg_views))}
        </span>
      </div>

      {/* Hour distribution bar chart */}
      <div className="mb-2">
        <span className="text-[10px] text-[var(--text-secondary)] mb-1 block">
          {t("intel.hour_dist", lang)}
        </span>
        <div className="flex h-8 items-end gap-px">
          {Array.from({ length: 24 }, (_, h) => {
            const count = profile.hour_distribution[h] || 0;
            const height = (count / maxHour) * 100;
            const isPeak = profile.peak_hours.includes(h);
            return (
              <div
                key={h}
                className={`flex-1 rounded-t-sm transition-colors ${
                  isPeak ? "bg-[var(--accent-blue)]" : "bg-[var(--border-color)]"
                }`}
                style={{ height: `${Math.max(height, 4)}%` }}
                title={`${h}:00 — ${count} posts`}
              />
            );
          })}
        </div>
        <div className="mt-0.5 flex justify-between text-[8px] text-gray-600">
          <span>0h</span>
          <span>6h</span>
          <span>12h</span>
          <span>18h</span>
          <span>23h</span>
        </div>
      </div>

      {/* Media distribution */}
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(profile.media_distribution).map(([type, count]) => (
          <span key={type} className="rounded bg-[var(--bg-primary)] px-1.5 py-0.5 text-[10px] text-[var(--text-secondary)]">
            {type}: {count}
          </span>
        ))}
      </div>

      {/* Top forward sources */}
      {Object.keys(profile.top_forward_sources).length > 0 && (
        <div className="mt-2">
          <span className="text-[10px] text-[var(--text-secondary)]">
            {t("intel.forward_sources", lang)}:
          </span>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {Object.entries(profile.top_forward_sources).slice(0, 5).map(([src, count]) => (
              <span key={src} className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">
                {src} ({count})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
