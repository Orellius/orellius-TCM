import { useState, useEffect, useMemo } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api } from "../lib/api";
import { useSettingsStore } from "../stores/settingsStore";
import { usePipelineStore } from "../stores/pipelineStore";
import { toast } from "../stores/toastStore";
import { t } from "../lib/i18n";

interface Template {
  id: string;
  name_en: string;
  name_he: string;
  matching_event_types: string[];
  matching_threat_levels: string[];
  template_body: string;
  priority: number;
}

interface TemplateListEditorProps {
  eventTypes: Array<{ key: string; name_en: string; name_he: string }>;
  threatLevels: Array<{ key: string; name_en: string; name_he: string }>;
}

const PLACEHOLDERS = [
  { key: "{title}", i18nKey: "placeholder.title" },
  { key: "{translated_text}", i18nKey: "placeholder.translated_text" },
  { key: "{intel_status}", i18nKey: "placeholder.intel_status" },
  { key: "{intel_status_line}", i18nKey: "placeholder.intel_status_line" },
  { key: "{event_type_he}", i18nKey: "placeholder.event_type_he" },
  { key: "{threat_level_he}", i18nKey: "placeholder.threat_level_he" },
  { key: "{region}", i18nKey: "placeholder.region" },
  { key: "{timestamp}", i18nKey: "placeholder.timestamp" },
  { key: "{facts_list}", i18nKey: "placeholder.facts_list" },
  { key: "{entities}", i18nKey: "placeholder.entities" },
];

/* ── Sortable Item ── */
function SortableTemplateItem({
  tpl,
  isSelected,
  matchCount,
  lang,
  onSelect,
  onDelete,
}: {
  tpl: Template;
  isSelected: boolean;
  matchCount: number;
  lang: "he" | "en";
  onSelect: () => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: tpl.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`group flex items-center rounded-lg transition-colors ${
        isSelected
          ? "bg-[var(--accent-blue)]/15 ring-1 ring-[var(--accent-blue)]/30"
          : "hover:bg-[var(--bg-tertiary)]"
      }`}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        className="flex-shrink-0 cursor-grab px-1.5 text-[var(--text-secondary)] opacity-0 group-hover:opacity-60 active:cursor-grabbing"
        tabIndex={-1}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
          <circle cx="5.5" cy="3.5" r="1" />
          <circle cx="10.5" cy="3.5" r="1" />
          <circle cx="5.5" cy="8" r="1" />
          <circle cx="10.5" cy="8" r="1" />
          <circle cx="5.5" cy="12.5" r="1" />
          <circle cx="10.5" cy="12.5" r="1" />
        </svg>
      </button>

      <button
        onClick={onSelect}
        className={`flex-1 rounded-md px-2 py-2.5 text-start text-sm ${
          isSelected ? "text-[var(--accent-blue)]" : "text-[var(--text-secondary)]"
        }`}
      >
        <div className="flex items-center gap-1.5">
          <span className={`font-medium ${isSelected ? "text-[var(--accent-blue)]" : "text-[var(--text-primary)]"}`}>
            {lang === "he" ? tpl.name_he : tpl.name_en}
          </span>
          {matchCount > 0 && (
            <span className="shrink-0 rounded-full bg-[var(--accent-blue)]/20 px-1.5 py-px text-[9px] font-bold text-[var(--accent-blue)]">
              {matchCount}
            </span>
          )}
        </div>
        <div className="mt-0.5 font-mono text-[10px] text-[var(--text-secondary)]">{tpl.id}</div>
      </button>

      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="mx-1 rounded p-1 text-[var(--text-secondary)] opacity-0 transition-opacity hover:bg-red-900/30 hover:text-red-400 group-hover:opacity-100"
        title={t("btn.delete", lang)}
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
          <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
        </svg>
      </button>
    </div>
  );
}

/* ── Section Card wrapper ── */
function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <div className="border-b border-[var(--border-color)] px-5 py-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{title}</h4>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

/* ── Main Component ── */
export function TemplateListEditor({ eventTypes, threatLevels }: TemplateListEditorProps) {
  const lang = useSettingsStore((s) => s.language);
  const messages = usePipelineStore((s) => s.messages);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Template | null>(null);
  const [saving, setSaving] = useState(false);
  const [isNew, setIsNew] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const templateMatchCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const msg of messages) {
      const tplId = msg.suggestedTemplateId;
      if (tplId) counts[tplId] = (counts[tplId] || 0) + 1;
    }
    return counts;
  }, [messages]);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const res = await api.getTemplates();
      const tpls = res.templates as Template[];
      setTemplates(tpls);
      if (tpls.length > 0 && !selectedId) selectTemplate(tpls[0]);
    } catch {
      toast.error(t("error.load_templates", lang));
    }
  };

  const selectTemplate = (tpl: Template) => {
    setSelectedId(tpl.id);
    setEditForm({ ...tpl });
    setIsNew(false);
  };

  const handleNew = () => {
    const id = `custom_${Date.now()}`;
    const newTpl: Template = {
      id,
      name_en: "New Template",
      name_he: "\u05ea\u05d1\u05e0\u05d9\u05ea \u05d7\u05d3\u05e9\u05d4",
      matching_event_types: [],
      matching_threat_levels: [],
      template_body: "{translated_text}",
      priority: 0,
    };
    setEditForm(newTpl);
    setSelectedId(null);
    setIsNew(true);
  };

  const handleSave = async () => {
    if (!editForm) return;
    setSaving(true);
    try {
      if (isNew) {
        await api.createTemplate(editForm as unknown as Record<string, unknown>);
      } else {
        await api.updateTemplate(editForm.id, editForm as unknown as Record<string, unknown>);
      }
      await loadTemplates();
      setSelectedId(editForm.id);
      setIsNew(false);
      toast.success(t("success.template_saved", lang));
    } catch {
      toast.error(t("error.template_save", lang));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id?: string) => {
    const targetId = id ?? editForm?.id;
    if (!targetId) return;
    try {
      await api.deleteTemplate(targetId);
      if (selectedId === targetId) {
        setSelectedId(null);
        setEditForm(null);
      }
      await loadTemplates();
      toast.success(t("success.template_deleted", lang));
    } catch {
      toast.error(t("error.template_delete", lang));
    }
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = templates.findIndex((t) => t.id === active.id);
    const newIndex = templates.findIndex((t) => t.id === over.id);
    const reordered = arrayMove(templates, oldIndex, newIndex);
    setTemplates(reordered);

    try {
      await api.reorderTemplates(reordered.map((t) => t.id));
    } catch {
      await loadTemplates();
    }
  };

  const toggleArrayItem = (arr: string[], item: string) =>
    arr.includes(item) ? arr.filter((x) => x !== item) : [...arr, item];

  const inputClass =
    "w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)]/30 transition-colors";

  return (
    <div className="flex h-full">
      {/* ── Left: Sortable Template List ── */}
      <div className="w-72 flex-shrink-0 border-e border-[var(--border-color)] bg-[var(--bg-secondary)] flex flex-col">
        <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--border-color)]">
          <h2 className="text-sm font-bold text-[var(--text-primary)]">
            {t("templates.title", lang)}
          </h2>
          <button
            onClick={handleNew}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent-blue)] text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            +
          </button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-0.5">
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={templates.map((t) => t.id)} strategy={verticalListSortingStrategy}>
              {templates.map((tpl) => (
                <SortableTemplateItem
                  key={tpl.id}
                  tpl={tpl}
                  isSelected={selectedId === tpl.id}
                  matchCount={templateMatchCounts[tpl.id] ?? 0}
                  lang={lang}
                  onSelect={() => selectTemplate(tpl)}
                  onDelete={() => handleDelete(tpl.id)}
                />
              ))}
            </SortableContext>
          </DndContext>
        </div>
      </div>

      {/* ── Right: Edit Form ── */}
      <div className="flex-1 overflow-auto">
        {editForm ? (
          <div className="mx-auto max-w-4xl space-y-5 p-6">
            {/* ── Action bar ── */}
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                {isNew
                  ? lang === "he" ? "תבנית חדשה" : "New Template"
                  : lang === "he" ? editForm.name_he : editForm.name_en}
              </h3>
              <div className="flex items-center gap-2">
                {!isNew && (
                  <button
                    onClick={() => handleDelete()}
                    className="rounded-lg border border-red-500/30 px-4 py-2 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/10"
                  >
                    {t("btn.delete", lang)}
                  </button>
                )}
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-lg bg-[var(--accent-green)] px-5 py-2 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {saving ? "..." : t("btn.save", lang)}
                </button>
              </div>
            </div>

            {/* ── Identity section ── */}
            <SectionCard title={lang === "he" ? "פרטי תבנית" : "Template Identity"}>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                    {t("templates.name_he", lang)}
                  </label>
                  <input
                    value={editForm.name_he}
                    onChange={(e) => setEditForm({ ...editForm, name_he: e.target.value })}
                    dir="rtl"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                    {t("templates.name_en", lang)}
                  </label>
                  <input
                    value={editForm.name_en}
                    onChange={(e) => setEditForm({ ...editForm, name_en: e.target.value })}
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                    {t("templates.id", lang)}
                  </label>
                  <input
                    value={editForm.id}
                    onChange={(e) => isNew && setEditForm({ ...editForm, id: e.target.value })}
                    readOnly={!isNew}
                    className={`${inputClass} font-mono text-xs ${!isNew ? "opacity-50 cursor-not-allowed" : ""}`}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-[var(--text-secondary)]">
                    {t("templates.priority", lang)}
                  </label>
                  <input
                    type="number"
                    value={editForm.priority}
                    onChange={(e) => setEditForm({ ...editForm, priority: Number(e.target.value) })}
                    className={`${inputClass} font-mono text-xs`}
                  />
                </div>
              </div>
            </SectionCard>

            {/* ── Template Body + Placeholders ── */}
            <SectionCard title={t("templates.body", lang)}>
              <textarea
                value={editForm.template_body}
                onChange={(e) => setEditForm({ ...editForm, template_body: e.target.value })}
                dir="rtl"
                rows={10}
                className={`${inputClass} resize-y rounded-b-none border-b-0 font-mono`}
              />
              <div className="rounded-b-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
                <h4 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                  {t("templates.placeholders", lang)}
                </h4>
                <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
                  {PLACEHOLDERS.map((p) => (
                    <div key={p.key} className="flex items-center gap-2 text-[11px]">
                      <code className="shrink-0 rounded-md bg-[var(--bg-tertiary)] px-1.5 py-0.5 font-mono text-[var(--accent-blue)]">
                        {p.key}
                      </code>
                      <span className="text-[var(--text-secondary)]">{t(p.i18nKey, lang)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </SectionCard>

            {/* ── Matching Rules ── */}
            <div className="grid grid-cols-2 gap-5">
              {/* Event Types */}
              <SectionCard title={t("templates.event_types", lang)}>
                <div className="flex flex-wrap gap-2">
                  {eventTypes.map((et) => {
                    const checked = editForm.matching_event_types.includes(et.key);
                    return (
                      <button
                        key={et.key}
                        onClick={() =>
                          setEditForm({
                            ...editForm,
                            matching_event_types: toggleArrayItem(editForm.matching_event_types, et.key),
                          })
                        }
                        className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                          checked
                            ? "border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]"
                            : "border-[var(--border-color)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]/30"
                        }`}
                      >
                        {checked && (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="mr-1 -ml-0.5 inline h-3 w-3">
                            <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
                          </svg>
                        )}
                        {lang === "he" ? et.name_he : et.name_en}
                      </button>
                    );
                  })}
                </div>
              </SectionCard>

              {/* Threat Levels */}
              <SectionCard title={t("templates.threat_levels", lang)}>
                <div className="flex flex-wrap gap-2">
                  {threatLevels.map((tl) => {
                    const checked = editForm.matching_threat_levels.includes(tl.key);
                    return (
                      <button
                        key={tl.key}
                        onClick={() =>
                          setEditForm({
                            ...editForm,
                            matching_threat_levels: toggleArrayItem(editForm.matching_threat_levels, tl.key),
                          })
                        }
                        className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                          checked
                            ? "border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]"
                            : "border-[var(--border-color)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]/30"
                        }`}
                      >
                        {checked && (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="mr-1 -ml-0.5 inline h-3 w-3">
                            <path fillRule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clipRule="evenodd" />
                          </svg>
                        )}
                        {lang === "he" ? tl.name_he : tl.name_en}
                      </button>
                    );
                  })}
                </div>
              </SectionCard>
            </div>

            {/* ── Match Count ── */}
            {!isNew && templateMatchCounts[editForm.id] != null && templateMatchCounts[editForm.id] > 0 && (
              <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)] px-5 py-3">
                <span className="text-xs text-[var(--text-secondary)]">
                  {t("templates.match_count", lang)}:{" "}
                  <span className="font-bold text-[var(--accent-blue)]">{templateMatchCounts[editForm.id]}</span>
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-[var(--text-secondary)]">
              {t("templates.select", lang)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
