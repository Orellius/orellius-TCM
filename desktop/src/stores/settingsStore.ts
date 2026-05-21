import { create } from "zustand";
import { persist } from "zustand/middleware";

type Lang = "he" | "en";

interface SettingsStore {
  // Auth / connection state
  telegramConnected: boolean;
  // UI language (Hebrew default)
  language: Lang;
  // Source channels to scrape
  sourceChannels: string[];
  // Target channel to publish to
  targetChannel: string;
  // Publishing delay between messages (seconds)
  publishDelay: number;
  // Auto-publish without review
  autoPublish: boolean;
  // Onboarding
  onboardingComplete: boolean;
  // Stamp/watermark config
  stampEnabled: boolean;
  stampImagePath: string;
  stampOpacity: number;
  stampSizePct: number;
  stampPosition: string;
  // Watermark removal config
  watermarkRemovalEnabled: boolean;
  watermarkConfidenceThreshold: number;
  // UI scale (0.75 – 1.5, default 1)
  uiScale: number;
  // Ghost Mode
  ghostModeEnabled: boolean;
  suppressReadReceipts: boolean;
  suppressOnlineStatus: boolean;
  // Pre-Processing
  keywordFilterEnabled: boolean;
  dedupEnabled: boolean;
  priorityKeywords: string;
  // Channel branding
  channelSignature: string;
  // Fact checking
  factCheckEnabled: boolean;
  setFactCheckEnabled: (enabled: boolean) => void;

  // Actions
  setTelegramConnected: (connected: boolean) => void;
  setLanguage: (lang: Lang) => void;
  setSourceChannels: (channels: string[]) => void;
  setTargetChannel: (channel: string) => void;
  setPublishDelay: (delay: number) => void;
  setAutoPublish: (auto: boolean) => void;
  setStampEnabled: (enabled: boolean) => void;
  setStampImagePath: (path: string) => void;
  setStampOpacity: (opacity: number) => void;
  setStampSizePct: (pct: number) => void;
  setStampPosition: (pos: string) => void;
  setWatermarkRemovalEnabled: (enabled: boolean) => void;
  setWatermarkConfidenceThreshold: (threshold: number) => void;
  setUiScale: (scale: number) => void;
  setGhostModeEnabled: (enabled: boolean) => void;
  setSuppressReadReceipts: (enabled: boolean) => void;
  setSuppressOnlineStatus: (enabled: boolean) => void;
  setKeywordFilterEnabled: (enabled: boolean) => void;
  setDedupEnabled: (enabled: boolean) => void;
  setPriorityKeywords: (keywords: string) => void;
  setOnboardingComplete: (complete: boolean) => void;
  setChannelSignature: (sig: string) => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      telegramConnected: false,
      language: "he",
      sourceChannels: [],
      targetChannel: "",
      publishDelay: 2,
      autoPublish: false,
      onboardingComplete: false,
      stampEnabled: true,
      stampImagePath: "",
      stampOpacity: 55,
      stampSizePct: 20,
      stampPosition: "center",
      watermarkRemovalEnabled: false,
      watermarkConfidenceThreshold: 0.65,
      uiScale: 1.05,
      ghostModeEnabled: true,
      suppressReadReceipts: true,
      suppressOnlineStatus: true,
      keywordFilterEnabled: true,
      dedupEnabled: true,
      priorityKeywords: "",
      channelSignature: "",
      factCheckEnabled: true,
      setFactCheckEnabled: (enabled) => set({ factCheckEnabled: enabled }),

      setTelegramConnected: (connected) => set({ telegramConnected: connected }),
      setLanguage: (lang) => set({ language: lang }),
      setSourceChannels: (channels) => set({ sourceChannels: channels }),
      setTargetChannel: (channel) => set({ targetChannel: channel }),
      setPublishDelay: (delay) => set({ publishDelay: delay }),
      setAutoPublish: (auto) => set({ autoPublish: auto }),
      setOnboardingComplete: (complete) => set({ onboardingComplete: complete }),
      setStampEnabled: (enabled) => set({ stampEnabled: enabled }),
      setStampImagePath: (path) => set({ stampImagePath: path }),
      setStampOpacity: (opacity) => set({ stampOpacity: opacity }),
      setStampSizePct: (pct) => set({ stampSizePct: pct }),
      setStampPosition: (pos) => set({ stampPosition: pos }),
      setWatermarkRemovalEnabled: (enabled) => set({ watermarkRemovalEnabled: enabled }),
      setWatermarkConfidenceThreshold: (threshold) => set({ watermarkConfidenceThreshold: threshold }),
      setUiScale: (scale) => set({ uiScale: scale }),
      setGhostModeEnabled: (enabled) => set({ ghostModeEnabled: enabled }),
      setSuppressReadReceipts: (enabled) => set({ suppressReadReceipts: enabled }),
      setSuppressOnlineStatus: (enabled) => set({ suppressOnlineStatus: enabled }),
      setKeywordFilterEnabled: (enabled) => set({ keywordFilterEnabled: enabled }),
      setDedupEnabled: (enabled) => set({ dedupEnabled: enabled }),
      setPriorityKeywords: (keywords) => set({ priorityKeywords: keywords }),
      setChannelSignature: (sig) => set({ channelSignature: sig }),
    }),
    {
      name: "orellius-settings",
      partialize: (state) => ({
        language: state.language,
        onboardingComplete: state.onboardingComplete,
        publishDelay: state.publishDelay,
        autoPublish: state.autoPublish,
        stampEnabled: state.stampEnabled,
        stampImagePath: state.stampImagePath,
        stampOpacity: state.stampOpacity,
        stampSizePct: state.stampSizePct,
        stampPosition: state.stampPosition,
        watermarkRemovalEnabled: state.watermarkRemovalEnabled,
        watermarkConfidenceThreshold: state.watermarkConfidenceThreshold,
        uiScale: state.uiScale,
        ghostModeEnabled: state.ghostModeEnabled,
        suppressReadReceipts: state.suppressReadReceipts,
        suppressOnlineStatus: state.suppressOnlineStatus,
        keywordFilterEnabled: state.keywordFilterEnabled,
        dedupEnabled: state.dedupEnabled,
        priorityKeywords: state.priorityKeywords,
        channelSignature: state.channelSignature,
        factCheckEnabled: state.factCheckEnabled,
      }),
    }
  )
);
