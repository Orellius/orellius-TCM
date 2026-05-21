import { usePipelineStore } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

export function ArchivePanel() {
  const messages = usePipelineStore((s) => s.messages);
  const selectMessage = usePipelineStore((s) => s.selectMessage);
  const lang = useSettingsStore((s) => s.language);

  const archived = messages.filter((m) => m.status === "archived");

  const handleRestore = async (id: string) => {
    try {
      await api.restoreMessage(id);
    } catch (err) {
      console.error("Restore failed:", err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteMessage(id);
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  return (
    <div className="flex h-full flex-col p-6">
      <h2 className="mb-4 text-lg font-semibold text-[var(--text-primary)]">
        {t("archive.title", lang)}
      </h2>

      {archived.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">{t("archive.empty", lang)}</p>
      ) : (
        <div className="space-y-2 overflow-auto">
          {archived.map((msg) => {
            const time = new Date(msg.timestamp * 1000).toLocaleString(
              lang === "he" ? "he-IL" : "en-US",
              { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short" },
            );

            return (
              <div
                key={msg.id}
                className="flex items-center justify-between rounded-lg border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-4 py-3"
              >
                <button
                  onClick={() => selectMessage(msg.id)}
                  className="min-w-0 flex-1 text-start"
                >
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="font-medium text-[var(--text-primary)]">{msg.sourceChannel}</span>
                    <span>&middot;</span>
                    <span>{time}</span>
                  </div>
                  <p className="mt-1 line-clamp-1 text-sm text-[var(--text-primary)]" dir="auto">
                    {msg.translatedText || msg.originalText}
                  </p>
                </button>

                <div className="ms-3 flex shrink-0 gap-2">
                  <button
                    onClick={() => handleRestore(msg.id)}
                    className="rounded-md bg-[var(--bg-secondary)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)]"
                  >
                    {t("archive.restore", lang)}
                  </button>
                  <button
                    onClick={() => handleDelete(msg.id)}
                    className="rounded-md bg-red-900/30 px-3 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-900/50"
                  >
                    {t("btn.delete", lang)}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
