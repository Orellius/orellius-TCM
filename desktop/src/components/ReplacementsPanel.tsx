import { useState, useEffect } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";
import { api } from "../lib/api";

interface ReplacementRule {
  find: string;
  replace: string;
  enabled: boolean;
}

export function ReplacementsPanel() {
  const lang = useSettingsStore((s) => s.language);
  const [replacements, setReplacements] = useState<ReplacementRule[]>([]);
  const [newFind, setNewFind] = useState("");
  const [newReplace, setNewReplace] = useState("");

  useEffect(() => {
    api.getReplacements().then((res) => setReplacements(res.replacements)).catch(() => {});
  }, []);

  const handleAdd = async () => {
    if (!newFind.trim()) return;
    await api.addReplacement(newFind.trim(), newReplace.trim());
    const res = await api.getReplacements();
    setReplacements(res.replacements);
    setNewFind("");
    setNewReplace("");
  };

  const handleToggle = async (index: number, enabled: boolean) => {
    await api.updateReplacement(index, { enabled });
    const res = await api.getReplacements();
    setReplacements(res.replacements);
  };

  const handleDelete = async (index: number) => {
    await api.deleteReplacement(index);
    const res = await api.getReplacements();
    setReplacements(res.replacements);
  };

  return (
    <div className="flex h-full flex-col overflow-auto p-6">
      <h2 className="mb-2 text-lg font-bold text-[var(--text-primary)]">
        {t("replacements.title", lang)}
      </h2>
      <p className="mb-6 text-sm text-[var(--text-secondary)]">
        {t("replacements.desc", lang)}
      </p>

      {/* Add new rule */}
      <div className="mb-6 flex items-center gap-2">
        <input
          value={newFind}
          onChange={(e) => setNewFind(e.target.value)}
          placeholder={t("replacements.find", lang)}
          dir="rtl"
          className="w-48 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
        />
        <span className="text-sm text-[var(--text-secondary)]">&rarr;</span>
        <input
          value={newReplace}
          onChange={(e) => setNewReplace(e.target.value)}
          placeholder={t("replacements.replace", lang)}
          dir="rtl"
          className="w-48 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
        />
        <button
          onClick={handleAdd}
          disabled={!newFind.trim()}
          className="rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          +
        </button>
      </div>

      {/* Rules list */}
      <div className="space-y-2">
        {replacements.length === 0 && (
          <p className="py-4 text-center text-sm text-[var(--text-secondary)] italic">
            {t("replacements.empty", lang)}
          </p>
        )}
        {replacements.map((rule, i) => (
          <div
            key={`${rule.find}::${rule.replace}`}
            className={`flex items-center gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-4 py-3 ${
              !rule.enabled ? "opacity-40" : ""
            }`}
          >
            <button
              onClick={() => handleToggle(i, !rule.enabled)}
              className={`h-5 w-5 shrink-0 rounded border transition-colors ${
                rule.enabled
                  ? "border-[var(--accent-blue)] bg-[var(--accent-blue)]"
                  : "border-[var(--border-color)] bg-transparent"
              }`}
              title={rule.enabled ? t("btn.disable", lang) : t("btn.enable", lang)}
            >
              {rule.enabled && (
                <svg viewBox="0 0 12 12" fill="none" className="h-full w-full">
                  <path d="M2.5 6L5 8.5L9.5 3.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
            <code className="rounded bg-[var(--bg-primary)] px-2.5 py-1 text-sm text-red-400" dir="rtl">
              {rule.find}
            </code>
            <span className="text-sm text-[var(--text-secondary)]">&rarr;</span>
            <code className="rounded bg-[var(--bg-primary)] px-2.5 py-1 text-sm text-green-400" dir="rtl">
              {rule.replace}
            </code>
            <div className="flex-1" />
            <button
              onClick={() => handleDelete(i)}
              className="rounded p-1.5 text-[var(--text-secondary)] hover:bg-red-900/30 hover:text-red-400"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
                <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
