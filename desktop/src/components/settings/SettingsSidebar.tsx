import { useSettingsStore } from "../../stores/settingsStore";
import { t } from "../../lib/i18n";
import { LinkIcon, MegaphoneIcon, PhotoIcon, FunnelIcon, GlobeIcon, CpuIcon, BeakerIcon } from "./shared/settingsIcons";
import type { SettingsCategoryId } from "./types";

const categories: Array<{ id: SettingsCategoryId; icon: React.ReactNode; labelKey: string }> = [
  { id: "connection", icon: <LinkIcon />, labelKey: "settings_cat.connection" },
  { id: "publishing", icon: <MegaphoneIcon />, labelKey: "settings_cat.publishing" },
  { id: "media", icon: <PhotoIcon />, labelKey: "settings_cat.media" },
  { id: "processing", icon: <FunnelIcon />, labelKey: "settings_cat.processing" },
  { id: "appearance", icon: <GlobeIcon />, labelKey: "settings_cat.appearance" },
  { id: "system", icon: <CpuIcon />, labelKey: "settings_cat.system" },
  { id: "testing", icon: <BeakerIcon />, labelKey: "settings_cat.testing" },
];

interface SettingsSidebarProps {
  activeCategory: SettingsCategoryId;
  onCategoryChange: (category: SettingsCategoryId) => void;
}

export function SettingsSidebar({ activeCategory, onCategoryChange }: SettingsSidebarProps) {
  const lang = useSettingsStore((s) => s.language);

  return (
    <nav className="flex w-48 flex-col border-e border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <div className="p-3 space-y-1">
        <h2 className="mb-3 px-3 text-lg font-bold text-[var(--text-primary)]">
          {t("settings.title", lang)}
        </h2>
        {categories.map(({ id, icon, labelKey }) => (
          <button
            key={id}
            onClick={() => onCategoryChange(id)}
            className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              activeCategory === id
                ? "bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {icon}
            {t(labelKey, lang)}
          </button>
        ))}
      </div>
    </nav>
  );
}
