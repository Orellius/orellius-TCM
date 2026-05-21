import { usePipelineStore } from "../stores/pipelineStore";
import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";

export function PublishQueue() {
  const messages = usePipelineStore((s) => s.messages);
  const lang = useSettingsStore((s) => s.language);
  const recent = messages.slice(0, 20);

  return (
    <div className="flex-1 overflow-auto border-b border-[var(--border-color)]">
      <div className="border-b border-[var(--border-color)] px-4 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          {t("publish.recent", lang)} ({messages.length})
        </h2>
      </div>
      <div className="space-y-1 p-2">
        {recent.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-[var(--text-secondary)]">{t("publish.empty", lang)}</p>
        ) : (
          recent.map((msg) => (
            <div
              key={msg.id}
              className="flex items-center justify-between rounded-md px-3 py-2 hover:bg-[var(--bg-tertiary)]"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-[var(--text-primary)]">
                  {(msg.originalText ?? msg.translatedText ?? "").slice(0, 60)}...
                </p>
                <p className="text-xs text-[var(--text-secondary)]">{msg.sourceChannel}</p>
              </div>
              <MessageStatusBadge status={msg.status} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function MessageStatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    ingested: "text-blue-400",
    translating: "text-amber-400",
    reviewing: "text-yellow-400",
    processing_media: "text-purple-400",
    publishing: "text-cyan-400",
    published: "text-green-400",
    publish_failed: "text-red-400",
    failed: "text-red-400",
  };

  return (
    <span className={`ml-2 whitespace-nowrap text-xs font-medium ${colorMap[status] ?? "text-gray-400"}`}>
      {status}
    </span>
  );
}
