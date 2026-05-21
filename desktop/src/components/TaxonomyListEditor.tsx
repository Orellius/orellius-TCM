import { useState } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";

interface TaxonomyItem {
  key: string;
  name_en: string;
  name_he: string;
}

interface TaxonomyListEditorProps {
  title: string;
  description: string;
  items: TaxonomyItem[];
  onAdd: (item: TaxonomyItem) => Promise<void>;
  onUpdate: (key: string, data: Partial<TaxonomyItem>) => Promise<void>;
  onDelete: (key: string) => Promise<void>;
  addLabel: string;
}

export function TaxonomyListEditor({ title, description, items, onAdd, onUpdate, onDelete, addLabel }: TaxonomyListEditorProps) {
  const lang = useSettingsStore((s) => s.language);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editData, setEditData] = useState<TaxonomyItem>({ key: "", name_en: "", name_he: "" });
  const [adding, setAdding] = useState(false);
  const [newItem, setNewItem] = useState<TaxonomyItem>({ key: "", name_en: "", name_he: "" });
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const startEdit = (item: TaxonomyItem) => {
    setEditingKey(item.key);
    setEditData({ ...item });
    setAdding(false);
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditData({ key: "", name_en: "", name_he: "" });
  };

  const saveEdit = async () => {
    if (!editData.name_en.trim() || !editData.name_he.trim()) return;
    setBusy(true);
    try {
      await onUpdate(editingKey!, { name_en: editData.name_en.trim(), name_he: editData.name_he.trim() });
      cancelEdit();
    } catch {
      /* parent handles error */
    } finally {
      setBusy(false);
    }
  };

  const handleAdd = async () => {
    if (!newItem.key.trim() || !newItem.name_en.trim() || !newItem.name_he.trim()) return;
    setBusy(true);
    try {
      await onAdd({ key: newItem.key.trim(), name_en: newItem.name_en.trim(), name_he: newItem.name_he.trim() });
      setNewItem({ key: "", name_en: "", name_he: "" });
      setAdding(false);
    } catch {
      /* parent handles error */
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (key: string) => {
    setBusy(true);
    try {
      await onDelete(key);
      setConfirmDelete(null);
    } catch {
      /* parent handles error */
    } finally {
      setBusy(false);
    }
  };

  const inputClass =
    "rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-2.5 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-[var(--text-primary)]">{title}</h3>
          <p className="text-xs text-[var(--text-secondary)]">{description}</p>
        </div>
        <button
          onClick={() => { setAdding(true); cancelEdit(); }}
          className="rounded-md bg-[var(--accent-blue)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
        >
          + {addLabel}
        </button>
      </div>

      <div className="space-y-1.5">
        {items.map((item) => (
          <div
            key={item.key}
            className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-2.5"
          >
            {editingKey === item.key ? (
              <div className="space-y-2">
                <code className="text-xs text-[var(--text-secondary)]">{item.key}</code>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-[var(--text-secondary)] w-8">EN</label>
                  <input
                    value={editData.name_en}
                    onChange={(e) => setEditData({ ...editData, name_en: e.target.value })}
                    className={`flex-1 ${inputClass}`}
                    placeholder="English name"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-[var(--text-secondary)] w-8">HE</label>
                  <input
                    value={editData.name_he}
                    onChange={(e) => setEditData({ ...editData, name_he: e.target.value })}
                    className={`flex-1 ${inputClass}`}
                    dir="rtl"
                    placeholder="Hebrew name"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    onClick={cancelEdit}
                    className="rounded-md border border-[var(--border-color)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                  >
                    {t("btn.cancel", lang)}
                  </button>
                  <button
                    onClick={saveEdit}
                    disabled={busy}
                    className="rounded-md bg-[var(--accent-green)] px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                  >
                    {t("btn.save", lang)}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <code className="rounded bg-[var(--bg-primary)] px-2 py-0.5 text-xs text-[var(--accent-blue)] font-mono">
                  {item.key}
                </code>
                <span className="text-sm text-[var(--text-primary)]">{item.name_en}</span>
                <span className="text-sm text-[var(--text-secondary)]" dir="rtl">{item.name_he}</span>
                <div className="flex-1" />
                <button
                  onClick={() => startEdit(item)}
                  className="rounded p-1.5 text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--accent-blue)]"
                  title="Edit"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                    <path d="M13.488 2.513a1.75 1.75 0 0 0-2.475 0L3.05 10.476a.75.75 0 0 0-.198.34l-.823 3.046a.75.75 0 0 0 .92.92l3.046-.823a.75.75 0 0 0 .34-.198l7.963-7.963a1.75 1.75 0 0 0 0-2.475l-.81-.81ZM11.72 3.22a.25.25 0 0 1 .354 0l.81.81a.25.25 0 0 1 0 .354L12 5.268 10.732 4l.988-.78Z" />
                  </svg>
                </button>
                {confirmDelete === item.key ? (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-red-400">{t("taxonomies.delete_confirm", lang)}</span>
                    <button
                      onClick={() => handleDelete(item.key)}
                      disabled={busy}
                      className="rounded px-2 py-0.5 text-xs bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {t("btn.delete", lang)}
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="rounded px-2 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                    >
                      {t("btn.cancel", lang)}
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(item.key)}
                    className="rounded p-1.5 text-[var(--text-secondary)] hover:bg-red-900/30 hover:text-red-400"
                    title="Delete"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
                      <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
                    </svg>
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

        {items.length === 0 && !adding && (
          <p className="py-4 text-center text-sm text-[var(--text-secondary)] italic">
            No items configured
          </p>
        )}

        {/* Add new item form */}
        {adding && (
          <div className="rounded-lg border border-dashed border-[var(--accent-blue)] bg-[var(--bg-secondary)] px-4 py-3 space-y-2">
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--text-secondary)] w-8">{t("taxonomies.key", lang)}</label>
              <input
                value={newItem.key}
                onChange={(e) => setNewItem({ ...newItem, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })}
                className={`flex-1 ${inputClass} font-mono`}
                placeholder="snake_case_key"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--text-secondary)] w-8">EN</label>
              <input
                value={newItem.name_en}
                onChange={(e) => setNewItem({ ...newItem, name_en: e.target.value })}
                className={`flex-1 ${inputClass}`}
                placeholder="English name"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--text-secondary)] w-8">HE</label>
              <input
                value={newItem.name_he}
                onChange={(e) => setNewItem({ ...newItem, name_he: e.target.value })}
                className={`flex-1 ${inputClass}`}
                dir="rtl"
                placeholder="Hebrew name"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setAdding(false); setNewItem({ key: "", name_en: "", name_he: "" }); }}
                className="rounded-md border border-[var(--border-color)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
              >
                {t("btn.cancel", lang)}
              </button>
              <button
                onClick={handleAdd}
                disabled={busy || !newItem.key.trim() || !newItem.name_en.trim() || !newItem.name_he.trim()}
                className="rounded-md bg-[var(--accent-green)] px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                {t("btn.save", lang)}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
