import { t } from "../lib/i18n";

// ── Types ──────────────────────────────────────────────────────────────────────

type TabId =
  | "home"
  | "pipeline"
  | "channels"
  | "templates"
  | "replacements"
  | "archive"
  | "intel"
  | "settings";

interface TabNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  lang: "he" | "en";
  badges?: Partial<Record<TabId, number>>;
}

// ── Inline SVG Icons (20x20 viewBox) ───────────────────────────────────────────

function IconHome() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <path d="M3 10L10 3L17 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 8.5V16C5 16.5523 5.44772 17 6 17H9V13C9 12.4477 9.44772 12 10 12C10.5523 12 11 12.4477 11 13V17H14C14.5523 17 15 16.5523 15 16V8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconPipeline() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <rect x="2" y="12" width="3" height="6" rx="0.5" fill="currentColor" />
      <rect x="6.5" y="8" width="3" height="10" rx="0.5" fill="currentColor" />
      <rect x="11" y="5" width="3" height="13" rx="0.5" fill="currentColor" />
      <rect x="15.5" y="2" width="3" height="16" rx="0.5" fill="currentColor" />
    </svg>
  );
}

function IconChannels() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <path d="M13.024 9.25c.47 0 .827-.433.637-.863a4 4 0 0 0-4.094-2.364c-.468.05-.665.576-.43.984l1.08 1.868a.75.75 0 0 0 .649.375h2.158ZM7.84 7.758c-.236-.408-.79-.5-1.068-.12A3.982 3.982 0 0 0 6 10c0 .884.287 1.7.772 2.363.278.38.832.287 1.068-.12l1.08-1.868a.75.75 0 0 0 0-.75L7.84 7.758ZM9.138 12.993c-.235.408-.039.934.43.984a4 4 0 0 0 4.094-2.364c.19-.43-.168-.863-.638-.863h-2.158a.75.75 0 0 0-.65.375l-1.078 1.868Z" fill="currentColor" />
      <path fillRule="evenodd" d="M14.13 4.347l.644-1.117a.75.75 0 0 0-1.299-.75l-.644 1.116a20.944 20.944 0 0 0-5.662 0L6.525 2.48a.75.75 0 1 0-1.3.75l.645 1.117a20.882 20.882 0 0 0-4.852 4.12.75.75 0 1 0 1.152.96 19.422 19.422 0 0 1 3.578-3.267l-.645 1.118a.75.75 0 0 0 1.3.75l.644-1.116a20.884 20.884 0 0 1 5.906 0l.644 1.116a.75.75 0 0 0 1.3-.75l-.645-1.117a19.42 19.42 0 0 1 3.578 3.267.75.75 0 1 0 1.152-.96 20.878 20.878 0 0 0-4.852-4.12Z" clipRule="evenodd" fill="currentColor" />
    </svg>
  );
}

function IconTemplates() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <rect x="3" y="2" width="14" height="16" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
      <line x1="6" y1="6" x2="14" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="6" y1="9.5" x2="14" y2="9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="6" y1="13" x2="11" y2="13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconReplacements() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <path d="M14 4L17 7L14 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3 7H17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6 16L3 13L6 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M17 13H3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconArchive() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <rect x="2" y="3" width="16" height="4" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4 7V16C4 16.5523 4.44772 17 5 17H15C15.5523 17 16 16.5523 16 16V7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 11H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconIntel() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <circle cx="10" cy="10" r="7.25" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="4" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="1" fill="currentColor" />
      <line x1="10" y1="1" x2="10" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="10" y1="16" x2="10" y2="19" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="1" y1="10" x2="4" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="16" y1="10" x2="19" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" className="shrink-0">
      <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M10 1.5V4M10 16V18.5M1.5 10H4M16 10H18.5M3.4 3.4L5.2 5.2M14.8 14.8L16.6 16.6M16.6 3.4L14.8 5.2M5.2 14.8L3.4 16.6"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
      />
    </svg>
  );
}

// ── Tab Configuration ──────────────────────────────────────────────────────────

interface TabDefinition {
  id: TabId;
  i18nKey: string;
  icon: () => React.JSX.Element;
}

const TAB_DEFINITIONS: readonly TabDefinition[] = [
  { id: "home",         i18nKey: "tab.home",          icon: IconHome },
  { id: "pipeline",     i18nKey: "tab.pipeline",      icon: IconPipeline },
  { id: "channels",     i18nKey: "tab.channels",      icon: IconChannels },
  { id: "templates",    i18nKey: "tab.templates",      icon: IconTemplates },
  { id: "replacements", i18nKey: "tab.replacements",   icon: IconReplacements },
  { id: "archive",      i18nKey: "tab.archive",        icon: IconArchive },
  { id: "intel",        i18nKey: "tab.intel",          icon: IconIntel },
  { id: "settings",     i18nKey: "tab.settings",       icon: IconSettings },
];

// ── Component ──────────────────────────────────────────────────────────────────

function TabNav({ activeTab, onTabChange, lang, badges }: TabNavProps) {
  return (
    <nav
      className="flex items-center gap-0.5"
      dir={lang === "he" ? "rtl" : "ltr"}
      role="tablist"
      aria-label="Main navigation"
    >
      {TAB_DEFINITIONS.map((tab) => {
        const isActive = activeTab === tab.id;
        const label = t(tab.i18nKey, lang);
        const badgeCount = badges?.[tab.id];
        const Icon = tab.icon;

        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-label={label}
            onClick={() => onTabChange(tab.id)}
            className={`relative flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors duration-150 ${
              isActive
                ? "bg-[var(--accent-blue)] text-white"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon />
            <span className="whitespace-nowrap">{label}</span>

            {/* Badge */}
            {badgeCount != null && badgeCount > 0 && (
              <span className="absolute -top-1 -end-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--accent-red)] px-1 text-[9px] font-bold text-white">
                {badgeCount > 99 ? "99+" : badgeCount}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}

// ── Exports ────────────────────────────────────────────────────────────────────

export type { TabId, TabNavProps, TabDefinition };
export { TAB_DEFINITIONS, TabNav };
