import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";

/**
 * Read-only channel summary in the Pipeline sidebar.
 * Channel configuration is done in the Connection tab.
 */
export function ChannelManager() {
  const { sourceChannels, targetChannel, language: lang } = useSettingsStore();

  return (
    <div className="flex-1 overflow-auto p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
        {t("channels.configured", lang)}
      </h2>

      {/* Source channels */}
      {sourceChannels.length > 0 ? (
        <div className="mb-3 space-y-1">
          <span className="text-xs text-[var(--text-secondary)]">{t("channels.source", lang)}</span>
          {sourceChannels.map((channel) => (
            <div
              key={channel}
              className="flex items-center gap-2 rounded-md bg-[var(--bg-tertiary)] px-3 py-1.5"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-blue)]" />
              <span className="text-sm text-[var(--text-primary)]">{channel}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-3 text-xs text-[var(--text-secondary)] opacity-70">
          {t("channels.no_source", lang)}
        </p>
      )}

      {/* Target channel */}
      {targetChannel ? (
        <div className="mb-3">
          <span className="text-xs text-[var(--text-secondary)]">{t("channels.target", lang)}</span>
          <div className="mt-1 flex items-center gap-2 rounded-md bg-[var(--bg-tertiary)] px-3 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent-green)]" />
            <span className="text-sm text-[var(--text-primary)]">{targetChannel}</span>
          </div>
        </div>
      ) : (
        <p className="mb-3 text-xs text-[var(--text-secondary)] opacity-70">
          {t("channels.no_target", lang)}
        </p>
      )}

      {/* Hint to go to Connection tab */}
      {(sourceChannels.length === 0 || !targetChannel) && (
        <p className="mt-2 text-xs text-[var(--accent-blue)] opacity-80">
          {t("channels.go_connection", lang)}
        </p>
      )}
    </div>
  );
}
