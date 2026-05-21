import { useSettingsStore } from "../../../stores/settingsStore";
import { t } from "../../../lib/i18n";

function LangButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-[var(--accent-blue)] text-white"
          : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--bg-primary)]"
      }`}
    >
      {label}
    </button>
  );
}

export function AppearanceSettings() {
  const { language, uiScale, setLanguage, setUiScale } = useSettingsStore();

  return (
    <div className="space-y-8">
      {/* ── Language Picker ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.language", language)}
        </h3>
        <p className="mb-3 text-xs text-[var(--text-secondary)]">
          {t("settings.language_desc", language)}
        </p>
        <div className="flex gap-2">
          <LangButton label="עברית" active={language === "he"} onClick={() => setLanguage("he")} />
          <LangButton label="English" active={language === "en"} onClick={() => setLanguage("en")} />
        </div>
      </div>

      {/* ── UI Scale ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.ui_scale", language)}
        </h3>
        <p className="mb-3 text-xs text-[var(--text-secondary)]">
          {t("settings.ui_scale_desc", language)}
        </p>
        <div className="flex items-center gap-4">
          <span className="w-8 text-xs text-[var(--text-secondary)]">75%</span>
          <input
            type="range"
            min={0.75}
            max={1.5}
            step={0.05}
            value={uiScale}
            onChange={(e) => setUiScale(Number(e.target.value))}
            className="flex-1 accent-[var(--accent-blue)]"
          />
          <span className="w-8 text-xs text-[var(--text-secondary)]">150%</span>
          <span className="min-w-[3.5rem] rounded-md bg-[var(--bg-tertiary)] px-2 py-1 text-center text-sm font-medium text-[var(--text-primary)]">
            {Math.round(uiScale * 100)}%
          </span>
          {uiScale !== 1 && (
            <button
              onClick={() => setUiScale(1)}
              className="rounded-md bg-[var(--bg-tertiary)] px-2 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)]"
            >
              {t("settings.ui_scale_reset", language)}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
