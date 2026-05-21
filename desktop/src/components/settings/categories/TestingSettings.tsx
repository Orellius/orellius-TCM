import { useState } from "react";
import { useSettingsStore } from "../../../stores/settingsStore";
import { toast } from "../../../stores/toastStore";
import { t } from "../../../lib/i18n";
import { api } from "../../../lib/api";
import { SirenIcon } from "../shared/settingsIcons";

const API = "http://127.0.0.1:8000/api";

export function TestingSettings() {
  const lang = useSettingsStore((s) => s.language);
  const { targetChannel } = useSettingsStore();

  const [hfcMocking, setHfcMocking] = useState(false);
  const [hfcDeleting, setHfcDeleting] = useState(false);
  const [testSending, setTestSending] = useState(false);

  const handleHfcMock = async () => {
    setHfcMocking(true);
    try {
      const res = await api.hfcTestMock();
      if (res.published) {
        toast.success(t("settings.hfc_mock_ok", lang));
      } else {
        toast.success(t("settings.hfc_mock_feed_only", lang));
      }
    } catch {
      toast.error(t("error.generic", lang));
    }
    setHfcMocking(false);
  };

  const handleHfcDeleteMock = async () => {
    setHfcDeleting(true);
    try {
      const res = await api.hfcDeleteMock();
      if (res.deleted_count > 0) {
        toast.success(t("testing.delete_ok", lang));
      } else {
        toast.info(t("testing.delete_none", lang));
      }
    } catch {
      toast.error(t("error.generic", lang));
    }
    setHfcDeleting(false);
  };

  const handleTestSend = async () => {
    if (!targetChannel) return;
    setTestSending(true);
    toast.info(t("connection.sending", lang));
    try {
      const res = await fetch(`${API}/telegram/test-send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: targetChannel, text: "Orellius Manager - Test message" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.ok) {
        toast.success(t("success.send_success", lang));
      } else {
        toast.error(data.error || t("error.send_failed", lang));
      }
    } catch {
      toast.error(t("error.send_failed", lang));
    }
    setTestSending(false);
  };

  return (
    <div className="space-y-8">
      {/* ── HFC Alerts Testing ── */}
      <div>
        <div className="mb-4 flex items-center gap-2 text-base font-semibold text-[var(--text-primary)]">
          <SirenIcon />
          {t("testing.hfc_section", lang)}
        </div>

        <div className="space-y-4">
          <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 space-y-3">
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">{t("testing.fire_mock", lang)}</p>
              <p className="text-xs text-[var(--text-secondary)]">{t("testing.fire_mock_desc", lang)}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleHfcMock}
                disabled={hfcMocking}
                className="rounded-md bg-red-600/20 px-4 py-2 text-xs font-medium text-red-400 transition-colors hover:bg-red-600/30 disabled:opacity-50"
              >
                {hfcMocking ? "..." : t("testing.fire_mock", lang)}
              </button>
              <button
                onClick={handleHfcDeleteMock}
                disabled={hfcDeleting}
                className="rounded-md bg-[var(--bg-tertiary)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)] hover:text-[var(--text-primary)] disabled:opacity-50"
              >
                {hfcDeleting ? "..." : t("testing.delete_mock", lang)}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Telegram Testing ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("testing.telegram_section", lang)}
        </h3>

        <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 space-y-3">
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">{t("testing.send_test", lang)}</p>
            <p className="text-xs text-[var(--text-secondary)]">{t("testing.send_test_desc", lang)}</p>
          </div>
          {targetChannel ? (
            <button
              onClick={handleTestSend}
              disabled={testSending}
              className="rounded-md bg-[var(--accent-amber)] px-4 py-2 text-xs font-medium text-white disabled:opacity-50"
            >
              {testSending ? "..." : t("testing.send_test", lang)}
            </button>
          ) : (
            <p className="text-xs text-amber-400">{t("testing.no_target", lang)}</p>
          )}
        </div>
      </div>
    </div>
  );
}
