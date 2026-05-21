import { useState, useEffect } from "react";
import { api } from "../lib/api";
import { useSettingsStore } from "../stores/settingsStore";
import { toast } from "../stores/toastStore";
import { t } from "../lib/i18n";
import { TemplateListEditor } from "./TemplateListEditor";
import { TaxonomyListEditor } from "./TaxonomyListEditor";

type SubTab = "templates" | "event_types" | "threat_levels" | "alert_templates";

interface TaxonomyItem {
  key: string;
  name_en: string;
  name_he: string;
}

export function TemplateEditor() {
  const lang = useSettingsStore((s) => s.language);
  const [subTab, setSubTab] = useState<SubTab>("templates");
  const [eventTypes, setEventTypes] = useState<TaxonomyItem[]>([]);
  const [threatLevels, setThreatLevels] = useState<TaxonomyItem[]>([]);
  const [resetKey, setResetKey] = useState(0);

  const refreshEventTypes = async () => {
    try {
      const r = await api.getEventTypes();
      setEventTypes(r.event_types);
    } catch {
      toast.error(t("error.generic", lang));
    }
  };

  const refreshThreatLevels = async () => {
    try {
      const r = await api.getThreatLevels();
      setThreatLevels(r.threat_levels);
    } catch {
      toast.error(t("error.generic", lang));
    }
  };

  useEffect(() => {
    refreshEventTypes();
    refreshThreatLevels();
  }, []);

  const handleResetTemplates = async () => {
    if (!confirm(lang === "he" ? "לאפס תבניות לברירת מחדל?" : "Reset templates to defaults?")) return;
    try {
      await api.resetTemplates();
      setResetKey((k) => k + 1);
      toast.success(lang === "he" ? "תבניות אופסו" : "Templates reset");
    } catch {
      toast.error(t("error.generic", lang));
    }
  };

  const handleResetTaxonomies = async () => {
    if (!confirm(lang === "he" ? "לאפס סוגי אירועים ורמות איום לברירת מחדל?" : "Reset event types & threat levels to defaults?")) return;
    try {
      await api.resetTaxonomies();
      await refreshEventTypes();
      await refreshThreatLevels();
      toast.success(lang === "he" ? "טקסונומיות אופסו" : "Taxonomies reset");
    } catch {
      toast.error(t("error.generic", lang));
    }
  };

  const tabs: { key: SubTab; label: string }[] = [
    { key: "templates", label: t("templates.subtab.templates", lang) },
    { key: "event_types", label: t("templates.subtab.event_types", lang) },
    { key: "threat_levels", label: t("templates.subtab.threat_levels", lang) },
    { key: "alert_templates", label: t("templates.subtab.alert_templates", lang) },
  ];

  return (
    <div className="flex h-full flex-col">
      {/* Sub-tab bar */}
      <div className="flex items-center gap-1 border-b border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSubTab(tab.key)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              subTab === tab.key
                ? "bg-[var(--accent-blue)]/20 text-[var(--accent-blue)]"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <div className="ml-auto">
          {(subTab === "templates") && (
            <button
              onClick={handleResetTemplates}
              className="rounded-md px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
            >
              {lang === "he" ? "איפוס לברירת מחדל" : "Reset to Defaults"}
            </button>
          )}
          {(subTab === "event_types" || subTab === "threat_levels") && (
            <button
              onClick={handleResetTaxonomies}
              className="rounded-md px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
            >
              {lang === "he" ? "איפוס לברירת מחדל" : "Reset to Defaults"}
            </button>
          )}
        </div>
      </div>

      {/* Active sub-tab content */}
      <div className="flex-1 overflow-hidden">
        {subTab === "templates" && (
          <TemplateListEditor key={resetKey} eventTypes={eventTypes} threatLevels={threatLevels} />
        )}
        {subTab === "event_types" && (
          <div className="h-full overflow-auto p-6">
            <TaxonomyListEditor
              title={t("templates.subtab.event_types", lang)}
              description={t("taxonomies.event_types_desc", lang)}
              items={eventTypes}
              onAdd={async (item) => {
                await api.createEventType(item);
                await refreshEventTypes();
              }}
              onUpdate={async (key, data) => {
                await api.updateEventType(key, data);
                await refreshEventTypes();
              }}
              onDelete={async (key) => {
                await api.deleteEventType(key);
                await refreshEventTypes();
              }}
              addLabel={t("taxonomies.add_event_type", lang)}
            />
          </div>
        )}
        {subTab === "threat_levels" && (
          <div className="h-full overflow-auto p-6">
            <TaxonomyListEditor
              title={t("templates.subtab.threat_levels", lang)}
              description={t("taxonomies.threat_levels_desc", lang)}
              items={threatLevels}
              onAdd={async (item) => {
                await api.createThreatLevel(item);
                await refreshThreatLevels();
              }}
              onUpdate={async (key, data) => {
                await api.updateThreatLevel(key, data);
                await refreshThreatLevels();
              }}
              onDelete={async (key) => {
                await api.deleteThreatLevel(key);
                await refreshThreatLevels();
              }}
              addLabel={t("taxonomies.add_threat_level", lang)}
            />
          </div>
        )}
        {subTab === "alert_templates" && (
          <HfcTemplateList />
        )}
      </div>
    </div>
  );
}

/* ── HFC Alert Template List ──────────────────────────────── */

function HfcTemplateList() {
  const lang = useSettingsStore((s) => s.language);
  const [templates, setTemplates] = useState<Record<string, { category: string; name_he: string; emoji: string; template_body: string }>>({});
  const [editingBodies, setEditingBodies] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    api.getHfcTemplates()
      .then((r) => {
        setTemplates(r.templates);
        const bodies: Record<string, string> = {};
        for (const [k, v] of Object.entries(r.templates)) {
          bodies[k] = v.template_body;
        }
        setEditingBodies(bodies);
      })
      .catch(() => toast.error(t("error.generic", lang)));
  }, []);

  const handleSave = async (category: string) => {
    setSaving(category);
    try {
      await api.updateHfcTemplate(category, { template_body: editingBodies[category] });
      toast.success(t("templates.saved", lang));
    } catch {
      toast.error(t("error.template_save", lang));
    }
    setSaving(null);
  };

  return (
    <div className="h-full overflow-auto p-6 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
          {t("hfc.templates_title", lang)}
        </h3>
        <p className="text-xs text-[var(--text-secondary)] mb-4">
          {t("hfc.templates_desc", lang)}
        </p>
      </div>
      {Object.entries(templates).map(([key, tpl]) => (
        <div key={key} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">{tpl.emoji}</span>
            <span className="text-sm font-medium text-[var(--text-primary)]">{tpl.name_he}</span>
            <span className="text-xs text-[var(--text-secondary)]">({key})</span>
          </div>
          <textarea
            value={editingBodies[key] ?? ""}
            onChange={(e) => setEditingBodies((prev) => ({ ...prev, [key]: e.target.value }))}
            dir="rtl"
            rows={5}
            className="w-full resize-y rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] font-mono focus:border-[var(--accent-blue)] focus:outline-none"
          />
          <div className="mt-2 flex justify-end">
            <button
              onClick={() => handleSave(key)}
              disabled={saving === key}
              className="rounded-md bg-[var(--accent-blue)] px-4 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {saving === key ? "..." : t("btn.save", lang)}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
