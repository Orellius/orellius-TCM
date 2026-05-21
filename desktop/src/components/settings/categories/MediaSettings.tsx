import { useState, useEffect, useRef } from "react";
import { useSettingsStore } from "../../../stores/settingsStore";
import { toast } from "../../../stores/toastStore";
import { t } from "../../../lib/i18n";
import { Toggle } from "../shared/Toggle";
import { SettingRow } from "../shared/SettingRow";

const API = "http://127.0.0.1:8000/api";

interface WatermarkRef {
  channel: string;
  filename: string;
  path: string;
}

export function MediaSettings() {
  const {
    language,
    stampEnabled,
    stampImagePath,
    stampOpacity,
    stampSizePct,
    stampPosition,
    watermarkRemovalEnabled,
    watermarkConfidenceThreshold,
    setStampEnabled,
    setStampImagePath,
    setStampOpacity,
    setStampSizePct,
    setStampPosition,
    setWatermarkRemovalEnabled,
    setWatermarkConfidenceThreshold,
  } = useSettingsStore();

  const [wmRefs, setWmRefs] = useState<WatermarkRef[]>([]);
  const wmFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API}/watermark/references`)
      .then((r) => r.json())
      .then((data) => setWmRefs(data.references || []))
      .catch(() => {});
  }, []);

  const handleWmRefUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    const reader = new FileReader();
    reader.onload = async () => {
      const b64 = (reader.result as string).split(",")[1];
      try {
        await fetch(`${API}/watermark/add-reference`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ channel: "global", image: b64, filename: file.name }),
        });
        const res = await fetch(`${API}/watermark/references`);
        const data = await res.json();
        setWmRefs(data.references || []);
      } catch {
        toast.error(t("error.generic", language));
      }
    };
    reader.readAsDataURL(file);
  };

  const handleWmRefDelete = async (ref: WatermarkRef) => {
    try {
      await fetch(`${API}/watermark/reference`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel: ref.channel, filename: ref.filename }),
      });
      setWmRefs((prev) => prev.filter((r) => r.path !== ref.path));
    } catch {
      toast.error(t("error.generic", language));
    }
  };

  return (
    <div className="space-y-8">
      {/* ── Stamp ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.media", language)}
        </h3>

        <div className="space-y-5">
          <SettingRow label={t("settings.stamp_enabled", language)} description={t("settings.stamp_desc", language)}>
            <Toggle checked={stampEnabled} onChange={setStampEnabled} />
          </SettingRow>

          {stampEnabled && (
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm text-[var(--text-primary)]">
                  {t("settings.stamp_path", language)}
                </label>
                <input
                  type="text"
                  value={stampImagePath}
                  onChange={(e) => setStampImagePath(e.target.value)}
                  placeholder="assets/stamps/watermark.png"
                  className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
                />
              </div>

              {/* Stamp Opacity */}
              <div>
                <label className="mb-1 block text-sm text-[var(--text-primary)]">
                  {t("settings.stamp_opacity", language)}
                </label>
                <p className="mb-2 text-xs text-[var(--text-secondary)]">
                  {t("settings.stamp_opacity_desc", language)}
                </p>
                <div className="flex items-center gap-4">
                  <span className="w-8 text-xs text-[var(--text-secondary)]">10%</span>
                  <input
                    type="range"
                    min={10}
                    max={100}
                    step={5}
                    value={stampOpacity}
                    onChange={(e) => setStampOpacity(Number(e.target.value))}
                    className="flex-1 accent-[var(--accent-blue)]"
                  />
                  <span className="w-8 text-xs text-[var(--text-secondary)]">100%</span>
                  <span className="min-w-[3rem] rounded-md bg-[var(--bg-tertiary)] px-2 py-1 text-center text-sm font-medium text-[var(--text-primary)]">
                    {stampOpacity}%
                  </span>
                </div>
              </div>

              {/* Stamp Size */}
              <div>
                <label className="mb-1 block text-sm text-[var(--text-primary)]">
                  {t("settings.stamp_size", language)}
                </label>
                <p className="mb-2 text-xs text-[var(--text-secondary)]">
                  {t("settings.stamp_size_desc", language)}
                </p>
                <div className="flex items-center gap-4">
                  <span className="w-8 text-xs text-[var(--text-secondary)]">10%</span>
                  <input
                    type="range"
                    min={10}
                    max={50}
                    step={2}
                    value={stampSizePct}
                    onChange={(e) => setStampSizePct(Number(e.target.value))}
                    className="flex-1 accent-[var(--accent-blue)]"
                  />
                  <span className="w-8 text-xs text-[var(--text-secondary)]">50%</span>
                  <span className="min-w-[3rem] rounded-md bg-[var(--bg-tertiary)] px-2 py-1 text-center text-sm font-medium text-[var(--text-primary)]">
                    {stampSizePct}%
                  </span>
                </div>
              </div>

              {/* Stamp Position */}
              <div>
                <label className="mb-1 block text-sm text-[var(--text-primary)]">
                  {t("settings.stamp_position", language)}
                </label>
                <select
                  value={stampPosition}
                  onChange={(e) => setStampPosition(e.target.value)}
                  className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
                >
                  <option value="center">{t("settings.pos_center", language)}</option>
                  <option value="bottom-right">{t("settings.pos_bottom_right", language)}</option>
                  <option value="bottom-left">{t("settings.pos_bottom_left", language)}</option>
                  <option value="top-right">{t("settings.pos_top_right", language)}</option>
                  <option value="top-left">{t("settings.pos_top_left", language)}</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Watermark Removal ── */}
      <div>
        <h3 className="mb-4 text-base font-semibold text-[var(--text-primary)]">
          {t("settings.wm_removal", language)}
        </h3>

        <div className="space-y-4">
          <SettingRow
            label={t("settings.wm_removal_enabled", language)}
            description={t("settings.wm_removal_desc", language)}
          >
            <Toggle checked={watermarkRemovalEnabled} onChange={setWatermarkRemovalEnabled} />
          </SettingRow>

          {watermarkRemovalEnabled && (
            <>
              <div>
                <label className="mb-1 block text-sm text-[var(--text-primary)]">
                  {t("settings.wm_confidence", language)}
                </label>
                <p className="mb-2 text-xs text-[var(--text-secondary)]">
                  {t("settings.wm_confidence_desc", language)}
                </p>
                <div className="flex items-center gap-4">
                  <span className="w-8 text-xs text-[var(--text-secondary)]">0.3</span>
                  <input
                    type="range"
                    min={0.3}
                    max={0.95}
                    step={0.05}
                    value={watermarkConfidenceThreshold}
                    onChange={(e) => setWatermarkConfidenceThreshold(Number(e.target.value))}
                    className="flex-1 accent-[var(--accent-blue)]"
                  />
                  <span className="w-8 text-xs text-[var(--text-secondary)]">0.95</span>
                  <span className="min-w-[3rem] rounded-md bg-[var(--bg-tertiary)] px-2 py-1 text-center text-sm font-medium text-[var(--text-primary)]">
                    {watermarkConfidenceThreshold.toFixed(2)}
                  </span>
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm text-[var(--text-primary)]">
                  {t("settings.wm_references", language)}
                </label>
                {wmRefs.length > 0 ? (
                  <div className="mb-3 flex flex-wrap gap-2">
                    {wmRefs.map((ref) => (
                      <div
                        key={ref.path}
                        className="group relative flex items-center gap-2 rounded-md bg-[var(--bg-tertiary)] px-3 py-1.5"
                      >
                        <span className="text-xs text-[var(--accent-blue)]">{ref.channel}/</span>
                        <span className="text-xs text-[var(--text-primary)]">{ref.filename}</span>
                        <button
                          onClick={() => handleWmRefDelete(ref)}
                          className="ml-1 text-[var(--text-secondary)] transition-colors hover:text-red-400"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="h-3 w-3">
                            <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mb-3 text-xs text-[var(--text-secondary)]">
                    {t("settings.wm_no_refs", language)}
                  </p>
                )}
                <button
                  onClick={() => wmFileRef.current?.click()}
                  className="rounded-md bg-[var(--bg-tertiary)] px-4 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--border-color)] hover:text-[var(--text-primary)]"
                >
                  {t("settings.wm_upload_ref", language)}
                </button>
                <input
                  ref={wmFileRef}
                  type="file"
                  accept="image/png,image/jpeg"
                  onChange={handleWmRefUpload}
                  className="hidden"
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
