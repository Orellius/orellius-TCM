import { useState, useEffect } from "react";
import { useSettingsStore } from "../../stores/settingsStore";
import { toast } from "../../stores/toastStore";
import { t } from "../../lib/i18n";
import { api } from "../../lib/api";
import { SettingsSidebar } from "./SettingsSidebar";
import { SaveBar } from "./shared/SaveBar";
import { ConnectionSettings } from "./categories/ConnectionSettings";
import { PublishingSettings } from "./categories/PublishingSettings";
import { MediaSettings } from "./categories/MediaSettings";
import { ProcessingSettings } from "./categories/ProcessingSettings";
import { AppearanceSettings } from "./categories/AppearanceSettings";
import { SystemSettings } from "./categories/SystemSettings";
import { TestingSettings } from "./categories/TestingSettings";
import type { SettingsCategoryId } from "./types";

export type { SettingsCategoryId };

interface SettingsPanelProps {
  initialCategory?: SettingsCategoryId;
}

export function SettingsPanel({ initialCategory }: SettingsPanelProps) {
  const [activeCategory, setActiveCategory] = useState<SettingsCategoryId>(initialCategory ?? "connection");
  const lang = useSettingsStore((s) => s.language);
  const [saving, setSaving] = useState(false);

  // When external navigation changes the target category
  useEffect(() => {
    if (initialCategory) setActiveCategory(initialCategory);
  }, [initialCategory]);

  // Sync all settings from backend on mount (source of truth after restart)
  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        const store = useSettingsStore.getState();
        if (s.publish_delay != null) store.setPublishDelay(s.publish_delay);
        if (s.auto_publish != null) store.setAutoPublish(s.auto_publish);
        if (s.stamp_enabled != null) store.setStampEnabled(s.stamp_enabled);
        if (s.stamp_image_path != null) store.setStampImagePath(s.stamp_image_path);
        if (s.stamp_opacity != null) store.setStampOpacity(s.stamp_opacity);
        if (s.stamp_size_pct != null) store.setStampSizePct(s.stamp_size_pct);
        if (s.stamp_position != null) store.setStampPosition(s.stamp_position);
        if (s.watermark_removal_enabled != null) store.setWatermarkRemovalEnabled(s.watermark_removal_enabled);
        if (s.watermark_confidence_threshold != null) store.setWatermarkConfidenceThreshold(s.watermark_confidence_threshold);
        store.setGhostModeEnabled(s.ghost_mode_enabled);
        store.setSuppressReadReceipts(s.suppress_read_receipts);
        store.setSuppressOnlineStatus(s.suppress_online_status);
        store.setKeywordFilterEnabled(s.keyword_filter_enabled);
        store.setDedupEnabled(s.dedup_enabled);
        store.setPriorityKeywords(s.priority_keywords);
        store.setChannelSignature(s.channel_signature ?? "");
        store.setFactCheckEnabled(s.fact_check_enabled ?? true);
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const s = useSettingsStore.getState();
      await api.updateSettings({
        publish_delay: s.publishDelay,
        auto_publish: s.autoPublish,
        stamp_enabled: s.stampEnabled,
        stamp_image_path: s.stampImagePath,
        stamp_opacity: s.stampOpacity,
        stamp_size_pct: s.stampSizePct,
        stamp_position: s.stampPosition,
        watermark_removal_enabled: s.watermarkRemovalEnabled,
        watermark_confidence_threshold: s.watermarkConfidenceThreshold,
        ghost_mode_enabled: s.ghostModeEnabled,
        suppress_read_receipts: s.suppressReadReceipts,
        suppress_online_status: s.suppressOnlineStatus,
        keyword_filter_enabled: s.keywordFilterEnabled,
        dedup_enabled: s.dedupEnabled,
        priority_keywords: s.priorityKeywords,
        channel_signature: s.channelSignature,
        fact_check_enabled: s.factCheckEnabled,
      });
      toast.success(t("settings.saved", lang));
    } catch {
      toast.error(t("error.settings_save", lang));
    }
    setSaving(false);
  };

  return (
    <div className="flex h-full">
      <SettingsSidebar activeCategory={activeCategory} onCategoryChange={setActiveCategory} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-auto p-6">
          {activeCategory === "connection" && <ConnectionSettings />}
          {activeCategory === "publishing" && <PublishingSettings />}
          {activeCategory === "media" && <MediaSettings />}
          {activeCategory === "processing" && <ProcessingSettings />}
          {activeCategory === "appearance" && <AppearanceSettings />}
          {activeCategory === "system" && <SystemSettings />}
          {activeCategory === "testing" && <TestingSettings />}
        </div>
        <SaveBar saving={saving} onSave={handleSave} lang={lang} />
      </div>
    </div>
  );
}
