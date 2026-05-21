import { useEffect, useState } from "react";
import { useToastStore, type Toast as ToastItem } from "../stores/toastStore";

const TYPE_STYLES: Record<string, string> = {
  error: "border-red-500/40 bg-red-950/90 text-red-200",
  success: "border-green-500/40 bg-green-950/90 text-green-200",
  info: "border-blue-500/40 bg-blue-950/90 text-blue-200",
};

const ICON: Record<string, string> = {
  error: "\u2716",    // ✖
  success: "\u2714",  // ✔
  info: "\u24D8",     // ⓘ
};

function ToastItem({ toast, onDismiss }: { toast: ToastItem; onDismiss: () => void }) {
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  // Animate in on mount
  useEffect(() => {
    const frame = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  // Animate out before removal
  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(onDismiss, 200); // wait for exit animation
    }, toast.duration - 200);
    return () => clearTimeout(timer);
  }, [toast.duration, onDismiss]);

  const style = TYPE_STYLES[toast.type] || TYPE_STYLES.info;

  return (
    <div
      role="alert"
      className={`pointer-events-auto flex items-start gap-2.5 rounded-lg border px-4 py-3 shadow-lg backdrop-blur-sm transition-all duration-200 ${style} ${
        visible && !exiting
          ? "translate-y-0 opacity-100"
          : "translate-y-2 opacity-0"
      }`}
      style={{ maxWidth: 420, minWidth: 260 }}
    >
      <span className="mt-px shrink-0 text-sm">{ICON[toast.type]}</span>
      <p className="flex-1 text-sm leading-snug" dir="auto">
        {toast.message}
      </p>
      <button
        onClick={() => {
          setExiting(true);
          setTimeout(onDismiss, 200);
        }}
        className="shrink-0 rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5">
          <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
        </svg>
      </button>
    </div>
  );
}

/** Render at app root — fixed overlay for toast popups. */
export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-[9999] flex flex-col items-center gap-2">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => removeToast(t.id)} />
      ))}
    </div>
  );
}
