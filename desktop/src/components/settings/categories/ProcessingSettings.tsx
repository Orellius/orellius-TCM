import { useSettingsStore } from "../../../stores/settingsStore";
import { t } from "../../../lib/i18n";
import { Toggle } from "../shared/Toggle";
import { SettingRow } from "../shared/SettingRow";

export function ProcessingSettings() {
  const {
    language,
    keywordFilterEnabled,
    dedupEnabled,
    priorityKeywords,
    factCheckEnabled,
    ghostModeEnabled,
    suppressReadReceipts,
    suppressOnlineStatus,
    setKeywordFilterEnabled,
    setDedupEnabled,
    setPriorityKeywords,
    setFactCheckEnabled,
    setGhostModeEnabled,
    setSuppressReadReceipts,
    setSuppressOnlineStatus,
  } = useSettingsStore();

  return (
    <div className="space-y-8">
      {/* ── Pre-Processing ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.preprocess", language)}
        </h3>

        <div className="space-y-4">
          <SettingRow
            label={t("settings.keyword_filter", language)}
            description={t("settings.keyword_filter_desc", language)}
          >
            <Toggle checked={keywordFilterEnabled} onChange={setKeywordFilterEnabled} />
          </SettingRow>

          {keywordFilterEnabled && (
            <div>
              <label className="mb-1 block text-sm text-[var(--text-primary)]">
                {t("settings.keywords_label", language)}
              </label>
              <input
                type="text"
                value={priorityKeywords}
                onChange={(e) => setPriorityKeywords(e.target.value)}
                placeholder={t("settings.keywords_placeholder", language)}
                className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
              />
            </div>
          )}

          <SettingRow label={t("settings.dedup", language)} description={t("settings.dedup_desc", language)}>
            <Toggle checked={dedupEnabled} onChange={setDedupEnabled} />
          </SettingRow>
        </div>
      </div>

      {/* ── Fact Checking ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.fact_check", language)}
        </h3>

        <SettingRow
          label={t("settings.fact_check_enabled", language)}
          description={t("settings.fact_check_desc", language)}
        >
          <Toggle checked={factCheckEnabled} onChange={setFactCheckEnabled} />
        </SettingRow>
      </div>

      {/* ── Ghost Mode ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.ghost_mode", language)}
        </h3>

        <div className="space-y-4">
          <SettingRow label={t("settings.ghost_enabled", language)} description={t("settings.ghost_desc", language)}>
            <Toggle checked={ghostModeEnabled} onChange={setGhostModeEnabled} />
          </SettingRow>

          {ghostModeEnabled && (
            <div className="space-y-3 ps-2">
              <div className="flex items-center gap-3">
                <Toggle checked={suppressReadReceipts} onChange={setSuppressReadReceipts} />
                <span className="text-sm text-[var(--text-primary)]">
                  {t("settings.ghost_read_receipts", language)}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <Toggle checked={suppressOnlineStatus} onChange={setSuppressOnlineStatus} />
                <span className="text-sm text-[var(--text-primary)]">
                  {t("settings.ghost_online_status", language)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
