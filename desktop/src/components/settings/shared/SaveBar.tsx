import { t } from "../../../lib/i18n";

interface SaveBarProps {
  saving: boolean;
  onSave: () => void;
  lang: "he" | "en";
}

export function SaveBar({ saving, onSave, lang }: SaveBarProps) {
  return (
    <div className="border-t border-[var(--border-color)] bg-[var(--bg-secondary)] px-6 py-3">
      <button
        onClick={onSave}
        disabled={saving}
        className="rounded-md bg-[var(--accent-blue)] px-6 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {saving ? t("channels.saving", lang) : t("btn.save", lang)}
      </button>
    </div>
  );
}
