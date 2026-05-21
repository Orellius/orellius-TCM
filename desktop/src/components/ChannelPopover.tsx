import { useEffect, useRef } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { t } from "../lib/i18n";

interface ChannelPopoverProps {
  open: boolean;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLElement | null>;
}

export function ChannelPopover({ open, onClose, anchorRef }: ChannelPopoverProps) {
  const { sourceChannels, targetChannel, language: lang } = useSettingsStore();
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close on click outside or Escape
  useEffect(() => {
    if (!open) return;

    function handleClick(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        anchorRef.current &&
        !anchorRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    }

    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open, onClose, anchorRef]);

  if (!open) return null;

  return (
    <div
      ref={popoverRef}
      className="absolute top-full mt-1 w-64 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] shadow-lg z-50"
    >
      <div className="p-3">
        {/* Source channels */}
        <div className="mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t("channels.source", lang)}
          </span>
          {sourceChannels.length > 0 ? (
            <div className="mt-1 space-y-1">
              {sourceChannels.map((ch) => (
                <div key={ch} className="flex items-center gap-2 rounded bg-[var(--bg-tertiary)] px-2 py-1">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-blue)]" />
                  <span className="truncate text-xs text-[var(--text-primary)]">{ch}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-xs text-[var(--text-secondary)] opacity-70">
              {t("channels.no_source", lang)}
            </p>
          )}
        </div>

        {/* Target channel */}
        <div className="mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t("channels.target", lang)}
          </span>
          {targetChannel ? (
            <div className="mt-1 flex items-center gap-2 rounded bg-[var(--bg-tertiary)] px-2 py-1">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-green)]" />
              <span className="truncate text-xs text-[var(--text-primary)]">{targetChannel}</span>
            </div>
          ) : (
            <p className="mt-1 text-xs text-[var(--text-secondary)] opacity-70">
              {t("channels.no_target", lang)}
            </p>
          )}
        </div>

        {/* Link to connection tab */}
        <p className="text-[10px] text-[var(--accent-blue)] opacity-80">
          {t("rail.configure", lang)}
        </p>
      </div>
    </div>
  );
}
