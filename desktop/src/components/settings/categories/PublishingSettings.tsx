import { useSettingsStore } from "../../../stores/settingsStore";
import { t } from "../../../lib/i18n";
import { Toggle } from "../shared/Toggle";
import { SettingRow } from "../shared/SettingRow";

export function PublishingSettings() {
  const {
    language,
    publishDelay,
    autoPublish,
    channelSignature,
    setPublishDelay,
    setAutoPublish,
    setChannelSignature,
  } = useSettingsStore();

  return (
    <div className="space-y-8">
      {/* ── Publishing ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.publishing", language)}
        </h3>

        <div className="space-y-5">
          <div>
            <label className="mb-1 block text-sm text-[var(--text-primary)]">
              {t("settings.publish_delay", language)}
            </label>
            <p className="mb-2 text-xs text-[var(--text-secondary)]">
              {t("settings.publish_delay_desc", language)}
            </p>
            <input
              type="number"
              min={0}
              max={3600}
              value={publishDelay}
              onChange={(e) => setPublishDelay(Number(e.target.value))}
              className="w-32 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
            />
          </div>

          <SettingRow
            label={t("settings.auto_publish", language)}
            description={t("settings.auto_publish_desc", language)}
          >
            <Toggle checked={autoPublish} onChange={setAutoPublish} />
          </SettingRow>
        </div>
      </div>

      {/* ── Channel Branding ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.channel_branding", language)}
        </h3>

        <div>
          <label className="mb-1 block text-sm text-[var(--text-primary)]">
            {t("settings.signature_label", language)}
          </label>
          <p className="mb-2 text-xs text-[var(--text-secondary)]">
            {t("settings.signature_desc", language)}
          </p>
          <textarea
            value={channelSignature}
            onChange={(e) => setChannelSignature(e.target.value)}
            placeholder={t("settings.signature_placeholder", language)}
            dir="rtl"
            rows={4}
            className="w-full resize-y rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}
