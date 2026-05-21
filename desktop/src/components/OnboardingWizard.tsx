import { useState, useEffect, useCallback, useRef, type ReactNode } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { toast } from "../stores/toastStore";

const API = "http://127.0.0.1:8000/api";

/* ── Types ──────────────────────────────────────────────── */

interface OnboardingWizardProps {
  onComplete: () => void;
  lang: "he" | "en";
  /** If user is already connected (session exists), skip auth steps */
  alreadyConnected?: boolean;
  /** Pre-fetched channel list if already connected */
  existingChannels?: string[];
}

interface TelegramChannel {
  id: number;
  title: string;
  username: string;
  participants: number;
  is_megagroup: boolean;
  is_creator: boolean;
  is_admin: boolean;
}

type AuthState = "disconnected" | "awaiting_code" | "awaiting_2fa" | "connected" | "error";

/* ── i18n (self-contained fallback) ─────────────────────── */

const OB_TEXT: Record<string, Record<"he" | "en", string>> = {
  connect_title:       { en: "Connect to Telegram",      he: "\u05D4\u05EA\u05D7\u05D1\u05E8 \u05DC\u05D8\u05DC\u05D2\u05E8\u05DD" },
  connect_education:   { en: "Orellius connects to your Telegram account to monitor source channels for intelligence. Your session is encrypted and stored locally.", he: "Orellius \u05DE\u05EA\u05D7\u05D1\u05E8 \u05DC\u05D7\u05E9\u05D1\u05D5\u05DF \u05D4\u05D8\u05DC\u05D2\u05E8\u05DD \u05E9\u05DC\u05DA \u05DB\u05D3\u05D9 \u05DC\u05E0\u05D8\u05E8 \u05E2\u05E8\u05D5\u05E6\u05D9 \u05DE\u05E7\u05D5\u05E8. \u05D4\u05E1\u05E9\u05DF \u05DE\u05D5\u05E6\u05E4\u05DF \u05D5\u05DE\u05D0\u05D5\u05D7\u05E1\u05DF \u05DE\u05E7\u05D5\u05DE\u05D9\u05EA." },
  phone_label:         { en: "Phone Number",              he: "\u05DE\u05E1\u05E4\u05E8 \u05D8\u05DC\u05E4\u05D5\u05DF" },
  phone_placeholder:   { en: "+1234567890",               he: "+972501234567" },
  phone_required:      { en: "Phone number is required",  he: "\u05E0\u05D3\u05E8\u05E9 \u05DE\u05E1\u05E4\u05E8 \u05D8\u05DC\u05E4\u05D5\u05DF" },
  connect_btn:         { en: "Connect",                   he: "\u05D4\u05EA\u05D7\u05D1\u05E8" },
  connecting:          { en: "Connecting...",              he: "\u05DE\u05EA\u05D7\u05D1\u05E8..." },
  connect_error:       { en: "Failed to connect to backend", he: "\u05D4\u05D7\u05D9\u05D1\u05D5\u05E8 \u05DC\u05E9\u05E8\u05EA \u05E0\u05DB\u05E9\u05DC" },

  verify_title:        { en: "Verify Your Identity",      he: "\u05D0\u05DE\u05EA \u05D0\u05EA \u05D6\u05D4\u05D5\u05EA\u05DA" },
  verify_education:    { en: "Telegram sent a verification code to your account. This confirms you own this number.", he: "\u05D8\u05DC\u05D2\u05E8\u05DD \u05E9\u05DC\u05D7 \u05E7\u05D5\u05D3 \u05D0\u05D9\u05DE\u05D5\u05EA \u05DC\u05D7\u05E9\u05D1\u05D5\u05E0\u05DA. \u05D6\u05D4 \u05DE\u05D0\u05E9\u05E8 \u05E9\u05D0\u05EA\u05D4 \u05D1\u05E2\u05DC \u05D4\u05DE\u05E1\u05E4\u05E8." },
  code_placeholder:    { en: "Enter code from Telegram",  he: "\u05D4\u05D6\u05DF \u05E7\u05D5\u05D3 \u05DE\u05D8\u05DC\u05D2\u05E8\u05DD" },
  twofa_placeholder:   { en: "Enter 2FA password",        he: "\u05D4\u05D6\u05DF \u05E1\u05D9\u05E1\u05DE\u05EA 2FA" },
  twofa_education:     { en: "Your account has two-factor authentication enabled. Enter your cloud password to continue.", he: "\u05DC\u05D7\u05E9\u05D1\u05D5\u05E0\u05DA \u05DE\u05D5\u05E4\u05E2\u05DC \u05D0\u05D9\u05DE\u05D5\u05EA \u05D3\u05D5-\u05E9\u05DC\u05D1\u05D9. \u05D4\u05D6\u05DF \u05D0\u05EA \u05E1\u05D9\u05E1\u05DE\u05EA \u05D4\u05E2\u05E0\u05DF \u05DB\u05D3\u05D9 \u05DC\u05D4\u05DE\u05E9\u05D9\u05DA." },
  submit:              { en: "Submit",                    he: "\u05E9\u05DC\u05D7" },
  code_error:          { en: "Failed to submit code",     he: "\u05E9\u05DC\u05D9\u05D7\u05EA \u05D4\u05E7\u05D5\u05D3 \u05E0\u05DB\u05E9\u05DC\u05D4" },
  twofa_error:         { en: "Failed to submit 2FA",      he: "\u05E9\u05DC\u05D9\u05D7\u05EA \u05E1\u05D9\u05E1\u05DE\u05EA 2FA \u05E0\u05DB\u05E9\u05DC\u05D4" },

  sources_title:       { en: "Select Source Channels",    he: "\u05D1\u05D7\u05E8 \u05E2\u05E8\u05D5\u05E6\u05D9 \u05DE\u05E7\u05D5\u05E8" },
  sources_education:   { en: "Choose channels to monitor. Orellius will scrape messages, translate them, and analyze them for intelligence value.", he: "\u05D1\u05D7\u05E8 \u05E2\u05E8\u05D5\u05E6\u05D9\u05DD \u05DC\u05E0\u05D9\u05D8\u05D5\u05E8. Orellius \u05D9\u05E9\u05D0\u05D1 \u05D4\u05D5\u05D3\u05E2\u05D5\u05EA, \u05D9\u05EA\u05E8\u05D2\u05DD \u05D0\u05D5\u05EA\u05DF \u05D5\u05D9\u05E0\u05EA\u05D7 \u05D0\u05EA \u05E2\u05E8\u05DB\u05DF \u05D4\u05DE\u05D5\u05D3\u05D9\u05E2\u05D9\u05E0\u05D9." },
  select_all:          { en: "Select All",                he: "\u05D1\u05D7\u05E8 \u05D4\u05DB\u05DC" },
  deselect_all:        { en: "Deselect All",              he: "\u05D1\u05D8\u05DC \u05D1\u05D7\u05D9\u05E8\u05D4" },
  no_channels:         { en: "No channels found",         he: "\u05DC\u05D0 \u05E0\u05DE\u05E6\u05D0\u05D5 \u05E2\u05E8\u05D5\u05E6\u05D9\u05DD" },
  loading_channels:    { en: "Loading channels...",       he: "\u05D8\u05D5\u05E2\u05DF \u05E2\u05E8\u05D5\u05E6\u05D9\u05DD..." },
  selected_count:      { en: "selected",                  he: "\u05E0\u05D1\u05D7\u05E8\u05D5" },
  members:             { en: "members",                   he: "\u05D7\u05D1\u05E8\u05D9\u05DD" },
  min_one_source:      { en: "Select at least 1 channel", he: "\u05D1\u05D7\u05E8 \u05DC\u05E4\u05D7\u05D5\u05EA \u05E2\u05E8\u05D5\u05E5 \u05D0\u05D7\u05D3" },

  target_title:        { en: "Select Target Channel",     he: "\u05D1\u05D7\u05E8 \u05E2\u05E8\u05D5\u05E5 \u05D9\u05E2\u05D3" },
  target_education:    { en: "Approved intelligence reports will be published to this channel. You must be an admin or creator of the target channel.", he: "\u05D3\u05D5\u05D7\u05D5\u05EA \u05DE\u05D5\u05D3\u05D9\u05E2\u05D9\u05DF \u05DE\u05D0\u05D5\u05E9\u05E8\u05D9\u05DD \u05D9\u05E4\u05D5\u05E8\u05E1\u05DE\u05D5 \u05DC\u05E2\u05E8\u05D5\u05E5 \u05D6\u05D4. \u05E2\u05DC\u05D9\u05DA \u05DC\u05D4\u05D9\u05D5\u05EA \u05DE\u05E0\u05D4\u05DC \u05D0\u05D5 \u05D9\u05D5\u05E6\u05E8 \u05D4\u05E2\u05E8\u05D5\u05E5." },
  select_target:       { en: "Select target channel...",  he: "\u05D1\u05D7\u05E8 \u05E2\u05E8\u05D5\u05E5 \u05D9\u05E2\u05D3..." },
  no_owned:            { en: "No owned/admin channels found", he: "\u05DC\u05D0 \u05E0\u05DE\u05E6\u05D0\u05D5 \u05E2\u05E8\u05D5\u05E6\u05D9\u05DD \u05D1\u05D1\u05E2\u05DC\u05D5\u05EA\u05DA" },

  config_title:        { en: "Configure Your Setup",      he: "\u05D4\u05D2\u05D3\u05E8 \u05D0\u05EA \u05D4\u05DE\u05E2\u05E8\u05DB\u05EA" },
  config_education:    { en: "Fine-tune how Orellius operates. You can always change these later in Settings.", he: "\u05DB\u05D5\u05D5\u05DF \u05D0\u05EA \u05D0\u05D5\u05E4\u05DF \u05D4\u05E4\u05E2\u05D5\u05DC\u05D4 \u05E9\u05DC Orellius. \u05EA\u05D5\u05DB\u05DC \u05DC\u05E9\u05E0\u05D5\u05EA \u05D6\u05D0\u05EA \u05DE\u05D0\u05D5\u05D7\u05E8 \u05D9\u05D5\u05EA\u05E8 \u05D1\u05D4\u05D2\u05D3\u05E8\u05D5\u05EA." },
  ghost_mode:          { en: "Ghost Mode",                he: "\u05DE\u05E6\u05D1 \u05E8\u05D5\u05D7" },
  ghost_desc:          { en: "Enable stealth monitoring \u2014 suppress read receipts and online status", he: "\u05D4\u05E4\u05E2\u05DC \u05DE\u05E2\u05E7\u05D1 \u05D7\u05DE\u05E7\u05E0\u05D9 \u2014 \u05D3\u05D9\u05DB\u05D5\u05D9 \u05E7\u05E8\u05D9\u05D0\u05D5\u05EA \u05D5\u05DE\u05E6\u05D1 \u05DE\u05E7\u05D5\u05D5\u05DF" },
  auto_publish:        { en: "Auto-Publish",              he: "\u05E4\u05E8\u05E1\u05D5\u05DD \u05D0\u05D5\u05D8\u05D5\u05DE\u05D8\u05D9" },
  auto_publish_desc:   { en: "Automatically publish approved messages without manual review", he: "\u05E4\u05E8\u05E1\u05DD \u05D4\u05D5\u05D3\u05E2\u05D5\u05EA \u05DE\u05D0\u05D5\u05E9\u05E8\u05D5\u05EA \u05DC\u05DC\u05D0 \u05D1\u05D9\u05E7\u05D5\u05E8\u05EA \u05D9\u05D3\u05E0\u05D9\u05EA" },
  publish_delay:       { en: "Publishing Delay",          he: "\u05D4\u05E9\u05D4\u05D9\u05D9\u05EA \u05E4\u05E8\u05E1\u05D5\u05DD" },
  publish_delay_desc:  { en: "Wait X seconds between publications to avoid rate limits", he: "\u05D4\u05DE\u05EA\u05DF X \u05E9\u05E0\u05D9\u05D5\u05EA \u05D1\u05D9\u05DF \u05E4\u05E8\u05E1\u05D5\u05DE\u05D9\u05DD \u05DC\u05DE\u05E0\u05D9\u05E2\u05EA \u05D7\u05E1\u05D9\u05DE\u05D4" },
  seconds:             { en: "sec",                       he: "\u05E9\u05E0\u05D9\u05D5\u05EA" },

  ready_title:         { en: "You're All Set!",           he: "\u05D4\u05DB\u05DC \u05DE\u05D5\u05DB\u05DF!" },
  ready_education:     { en: "Orellius is ready to start monitoring. Click below to begin your first intelligence pipeline.", he: "Orellius \u05DE\u05D5\u05DB\u05DF \u05DC\u05D4\u05EA\u05D7\u05D9\u05DC \u05DC\u05E0\u05D8\u05E8. \u05DC\u05D7\u05E5 \u05DC\u05DE\u05D8\u05D4 \u05DB\u05D3\u05D9 \u05DC\u05D4\u05E4\u05E2\u05D9\u05DC \u05D0\u05EA \u05E6\u05D9\u05E0\u05D5\u05E8 \u05D4\u05DE\u05D5\u05D3\u05D9\u05E2\u05D9\u05DF." },
  start_monitoring:    { en: "Start Monitoring",          he: "\u05D4\u05EA\u05D7\u05DC \u05E0\u05D9\u05D8\u05D5\u05E8" },
  saving:              { en: "Saving...",                 he: "\u05E9\u05D5\u05DE\u05E8..." },
  summary_sources:     { en: "Source channels",           he: "\u05E2\u05E8\u05D5\u05E6\u05D9 \u05DE\u05E7\u05D5\u05E8" },
  summary_target:      { en: "Target",                   he: "\u05D9\u05E2\u05D3" },
  summary_ghost:       { en: "Ghost Mode",               he: "\u05DE\u05E6\u05D1 \u05E8\u05D5\u05D7" },
  summary_auto_pub:    { en: "Auto-Publish",             he: "\u05E4\u05E8\u05E1\u05D5\u05DD \u05D0\u05D5\u05D8\u05D5\u05DE\u05D8\u05D9" },
  on:                  { en: "On",                       he: "\u05DE\u05D5\u05E4\u05E2\u05DC" },
  off:                 { en: "Off",                      he: "\u05DB\u05D1\u05D5\u05D9" },
  none:                { en: "None",                     he: "\u05DC\u05DC\u05D0" },
  save_error:          { en: "Failed to save configuration", he: "\u05E9\u05DE\u05D9\u05E8\u05EA \u05D4\u05EA\u05E6\u05D5\u05E8\u05D4 \u05E0\u05DB\u05E9\u05DC\u05D4" },

  // Navigation
  back:                { en: "Back",                     he: "\u05D7\u05D6\u05D5\u05E8" },
  next:                { en: "Next",                     he: "\u05D4\u05D1\u05D0" },
  skip:                { en: "Skip",                     he: "\u05D3\u05DC\u05D2" },
};

/* ── Component ──────────────────────────────────────────── */

const TOTAL_STEPS = 6; // 0..5

export function OnboardingWizard({
  onComplete,
  lang,
  alreadyConnected = false,
  existingChannels,
}: OnboardingWizardProps) {
  const {
    setSourceChannels,
    setTargetChannel,
    setGhostModeEnabled,
    setAutoPublish,
    setPublishDelay,
  } = useSettingsStore();

  // Determine starting step: skip auth steps if already connected
  const startStep = alreadyConnected ? 2 : 0;

  const [step, setStep] = useState(startStep);
  const [direction, setDirection] = useState<"forward" | "back">("forward");
  const [animating, setAnimating] = useState(false);

  // Auth state
  const [authState, setAuthState] = useState<AuthState>(
    alreadyConnected ? "connected" : "disconnected"
  );
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState("");

  // Channel state
  const [telegramChannels, setTelegramChannels] = useState<TelegramChannel[]>([]);
  const [loadingChannels, setLoadingChannels] = useState(false);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(
    new Set(existingChannels ?? [])
  );
  const [targetChannel, setTargetCh] = useState("");

  // Config state
  const [ghostMode, setGhostMode] = useState(true);
  const [autoPublish, setAutoPub] = useState(false);
  const [publishDelay, setPubDelay] = useState(30);

  // Saving state for final step
  const [saving, setSaving] = useState(false);

  // Ref to auto-focus inputs
  const phoneRef = useRef<HTMLInputElement>(null);
  const codeRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const ob = useCallback(
    (key: string) => OB_TEXT[key]?.[lang] ?? key,
    [lang]
  );

  // Fetch Telegram channel list when connected
  const fetchChannels = useCallback(async () => {
    setLoadingChannels(true);
    try {
      const res = await fetch(`${API}/telegram/channels`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTelegramChannels(data.channels || []);
    } catch {
      setTelegramChannels([]);
    }
    setLoadingChannels(false);
  }, []);

  // When auth state transitions to connected, fetch channels
  useEffect(() => {
    if (authState === "connected") {
      fetchChannels();
    }
  }, [authState, fetchChannels]);

  // Auto-focus inputs
  useEffect(() => {
    if (step === 0) {
      setTimeout(() => phoneRef.current?.focus(), 100);
    }
    if (step === 1 && authState === "awaiting_code") {
      setTimeout(() => codeRef.current?.focus(), 100);
    }
    if (step === 1 && authState === "awaiting_2fa") {
      setTimeout(() => passwordRef.current?.focus(), 100);
    }
  }, [step, authState]);

  /* ── Step navigation ──────────────────────────────────── */

  const goTo = useCallback(
    (target: number, dir: "forward" | "back") => {
      if (animating) return;
      setDirection(dir);
      setAnimating(true);
      // Short delay to trigger exit animation, then switch step
      setTimeout(() => {
        setStep(target);
        setAnimating(false);
      }, 150);
    },
    [animating]
  );

  const goNext = useCallback(() => {
    if (step < TOTAL_STEPS - 1) goTo(step + 1, "forward");
  }, [step, goTo]);

  const goBack = useCallback(() => {
    // Don't go back past start step (skip auth if alreadyConnected)
    const minimum = alreadyConnected ? 2 : 0;
    if (step > minimum) goTo(step - 1, "back");
  }, [step, alreadyConnected, goTo]);

  /* ── Auth handlers ────────────────────────────────────── */

  const handleConnect = async () => {
    setAuthError("");

    // Validate phone before connecting
    const trimmedPhone = phone.trim();
    if (!trimmedPhone) {
      setAuthError(ob("phone_required"));
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: trimmedPhone }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.status === "error") {
        setAuthError(data.message || ob("connect_error"));
        setLoading(false);
        return;
      }

      setAuthState(data.status as AuthState);
      if (data.message) toast.info(data.message);
      // If directly connected (cached session), auto-advance
      if (data.status === "connected") {
        goNext();
      } else if (data.status === "awaiting_code" || data.status === "awaiting_2fa") {
        goTo(1, "forward");
      }
    } catch {
      toast.error(ob("connect_error"));
    }
    setLoading(false);
  };

  const handleSubmitCode = async () => {
    if (!code.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAuthState(data.status as AuthState);
      if (data.message) toast.info(data.message);
      if (data.status === "connected") {
        goTo(2, "forward");
      }
      // If awaiting_2fa, stay on step 1 — UI will switch to password input
    } catch {
      toast.error(ob("code_error"));
    }
    setLoading(false);
  };

  const handleSubmit2FA = async () => {
    if (!password) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/telegram/2fa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAuthState(data.status as AuthState);
      if (data.message) toast.info(data.message);
      if (data.status === "connected") {
        goTo(2, "forward");
      }
    } catch {
      toast.error(ob("twofa_error"));
    }
    setLoading(false);
    setPassword("");
  };

  /* ── Channel helpers ──────────────────────────────────── */

  const ownedChannels = telegramChannels.filter(
    (ch) => ch.is_creator || ch.is_admin
  );

  const toggleSource = (identifier: string) => {
    setSelectedSources((prev) => {
      const next = new Set(prev);
      if (next.has(identifier)) next.delete(identifier);
      else next.add(identifier);
      return next;
    });
  };

  const selectAll = () => {
    const all = telegramChannels.map((ch) => ch.username || String(ch.id));
    setSelectedSources(new Set(all));
  };

  const deselectAll = () => {
    setSelectedSources(new Set());
  };

  /* ── Final save ───────────────────────────────────────── */

  const handleFinish = async () => {
    setSaving(true);
    try {
      // Save source channels
      const sources = Array.from(selectedSources);
      for (const ch of sources) {
        await fetch(`${API}/channels`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ channel: ch }),
        });
      }

      // Save target + settings
      await fetch(`${API}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_channel: targetChannel,
          ghost_mode_enabled: ghostMode,
          auto_publish: autoPublish,
          publish_delay_seconds: publishDelay,
        }),
      });

      // Update Zustand stores
      setSourceChannels(sources);
      setTargetChannel(targetChannel);
      setGhostModeEnabled(ghostMode);
      setAutoPublish(autoPublish);
      setPublishDelay(publishDelay);

      // Start pipeline
      await fetch(`${API}/pipeline/start`, { method: "POST" });

      toast.success(
        lang === "en" ? "Pipeline started!" : "\u05D4\u05E6\u05D9\u05E0\u05D5\u05E8 \u05D4\u05D5\u05E4\u05E2\u05DC!"
      );
      useSettingsStore.getState().setOnboardingComplete(true);
      onComplete();
    } catch {
      toast.error(ob("save_error"));
    }
    setSaving(false);
  };

  /* ── Step indicator dots ──────────────────────────────── */

  const effectiveSteps = alreadyConnected
    ? [2, 3, 4, 5]
    : [0, 1, 2, 3, 4, 5];

  function StepDots() {
    return (
      <div className="mb-6 flex items-center justify-center gap-2">
        {effectiveSteps.map((s) => (
          <div
            key={s}
            className={`h-2 w-2 rounded-full transition-all duration-300 ${
              s < step
                ? "bg-[var(--accent-blue)]"
                : s === step
                ? "ring-2 ring-[var(--accent-blue)] bg-transparent"
                : "bg-[var(--bg-tertiary)]"
            }`}
          />
        ))}
      </div>
    );
  }

  /* ── Education block ──────────────────────────────────── */

  function EducationBlock({ text }: { text: string }) {
    return (
      <div className="mb-6 flex gap-3 rounded-lg border-l-2 border-[var(--accent-blue)]/40 bg-[var(--accent-blue)]/5 px-4 py-3">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="mt-0.5 h-4 w-4 flex-shrink-0 text-[var(--accent-blue)]"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-sm italic text-[var(--text-secondary)]">{text}</p>
      </div>
    );
  }

  /* ── Step content renderers ───────────────────────────── */

  function renderStep0() {
    return (
      <>
        <EducationBlock text={ob("connect_education")} />

        {/* Phone number input */}
        <div className="mb-4">
          <label className="mb-1.5 block text-sm font-medium text-[var(--text-primary)]">
            {ob("phone_label")}
          </label>
          <input
            ref={phoneRef}
            type="tel"
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value);
              setAuthError("");
            }}
            onKeyDown={(e) => e.key === "Enter" && handleConnect()}
            placeholder={ob("phone_placeholder")}
            dir="ltr"
            className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
          {authError && (
            <p className="mt-1.5 text-xs text-[var(--accent-red)]">{authError}</p>
          )}
        </div>

        <button
          onClick={handleConnect}
          disabled={loading || !phone.trim()}
          className="w-full rounded-lg bg-[var(--accent-blue)] py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? ob("connecting") : ob("connect_btn")}
        </button>
      </>
    );
  }

  function renderStep1() {
    if (authState === "awaiting_2fa") {
      return (
        <>
          <EducationBlock text={ob("twofa_education")} />
          <div className="flex gap-2">
            <input
              ref={passwordRef}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit2FA()}
              placeholder={ob("twofa_placeholder")}
              className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
            />
            <button
              onClick={handleSubmit2FA}
              disabled={loading || !password}
              className="rounded-md bg-[var(--accent-green)] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {loading ? "..." : ob("submit")}
            </button>
          </div>
        </>
      );
    }

    // Default: awaiting code
    return (
      <>
        <EducationBlock text={ob("verify_education")} />
        <div className="flex gap-2">
          <input
            ref={codeRef}
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmitCode()}
            placeholder={ob("code_placeholder")}
            className="flex-1 rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)] focus:border-[var(--accent-blue)] focus:outline-none"
          />
          <button
            onClick={handleSubmitCode}
            disabled={loading || !code.trim()}
            className="rounded-md bg-[var(--accent-green)] px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? "..." : ob("submit")}
          </button>
        </div>
      </>
    );
  }

  function renderStep2() {
    return (
      <>
        <EducationBlock text={ob("sources_education")} />

        {/* Select / Deselect All */}
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs text-[var(--text-secondary)]">
            {selectedSources.size} {ob("selected_count")}
          </span>
          <div className="flex gap-2">
            <button
              onClick={selectAll}
              className="rounded-md bg-[var(--bg-tertiary)] px-3 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {ob("select_all")}
            </button>
            <button
              onClick={deselectAll}
              className="rounded-md bg-[var(--bg-tertiary)] px-3 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {ob("deselect_all")}
            </button>
          </div>
        </div>

        {/* Channel list */}
        <div className="max-h-56 space-y-1 overflow-auto rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-2">
          {loadingChannels ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner />
              <span className="ml-2 text-xs text-[var(--text-secondary)]">
                {ob("loading_channels")}
              </span>
            </div>
          ) : telegramChannels.length === 0 ? (
            <p className="py-8 text-center text-xs text-[var(--text-secondary)]">
              {ob("no_channels")}
            </p>
          ) : (
            telegramChannels.map((ch) => {
              const identifier = ch.username || String(ch.id);
              const checked = selectedSources.has(identifier);
              return (
                <label
                  key={ch.id}
                  className={`flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 transition-colors ${
                    checked
                      ? "bg-[var(--accent-blue)]/10"
                      : "hover:bg-[var(--bg-tertiary)]"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleSource(identifier)}
                    className="h-4 w-4 rounded border-[var(--border-color)] accent-[var(--accent-blue)]"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-[var(--text-primary)]">
                      {ch.title}
                    </span>
                    {ch.username && (
                      <span className="ml-2 text-xs text-[var(--text-secondary)]">
                        @{ch.username}
                      </span>
                    )}
                  </div>
                  {ch.participants > 0 && (
                    <span className="flex-shrink-0 text-xs text-[var(--text-secondary)]">
                      {ch.participants.toLocaleString()} {ob("members")}
                    </span>
                  )}
                </label>
              );
            })
          )}
        </div>

        {/* Validation hint */}
        {selectedSources.size === 0 && (
          <p className="mt-2 text-xs text-[var(--accent-amber)]">
            {ob("min_one_source")}
          </p>
        )}
      </>
    );
  }

  function renderStep3() {
    return (
      <>
        <EducationBlock text={ob("target_education")} />

        <select
          value={targetChannel}
          onChange={(e) => setTargetCh(e.target.value)}
          className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-tertiary)] px-3 py-2.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent-blue)] focus:outline-none"
        >
          <option value="">{ob("select_target")}</option>
          {ownedChannels.length === 0 && (
            <option value="" disabled>
              {ob("no_owned")}
            </option>
          )}
          {ownedChannels.map((ch) => {
            const identifier = ch.username
              ? `@${ch.username}`
              : String(ch.id);
            return (
              <option key={ch.id} value={ch.username || String(ch.id)}>
                {ch.title} ({identifier})
              </option>
            );
          })}
        </select>
      </>
    );
  }

  function renderStep4() {
    return (
      <>
        <EducationBlock text={ob("config_education")} />

        <div className="space-y-5">
          {/* Ghost Mode */}
          <div className="flex items-start gap-3">
            <Toggle checked={ghostMode} onChange={setGhostMode} />
            <div>
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {ob("ghost_mode")}
              </span>
              <p className="text-xs text-[var(--text-secondary)]">
                {ob("ghost_desc")}
              </p>
            </div>
          </div>

          {/* Auto-Publish */}
          <div className="flex items-start gap-3">
            <Toggle checked={autoPublish} onChange={setAutoPub} />
            <div>
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {ob("auto_publish")}
              </span>
              <p className="text-xs text-[var(--text-secondary)]">
                {ob("auto_publish_desc")}
              </p>
            </div>
          </div>

          {/* Publish Delay */}
          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--text-primary)]">
              {ob("publish_delay")}
            </label>
            <p className="mb-2 text-xs text-[var(--text-secondary)]">
              {ob("publish_delay_desc")}
            </p>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={120}
                step={5}
                value={publishDelay}
                onChange={(e) => setPubDelay(Number(e.target.value))}
                className="flex-1 accent-[var(--accent-blue)]"
              />
              <span className="min-w-[4rem] rounded-md bg-[var(--bg-tertiary)] px-2 py-1 text-center text-sm font-medium text-[var(--text-primary)]">
                {publishDelay} {ob("seconds")}
              </span>
            </div>
          </div>
        </div>
      </>
    );
  }

  function renderStep5() {
    const sources = Array.from(selectedSources);
    return (
      <>
        <EducationBlock text={ob("ready_education")} />

        {/* Summary */}
        <div className="mb-6 space-y-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] p-4">
          <SummaryRow
            label={ob("summary_sources")}
            value={`${sources.length} ${sources.length === 1 ? "channel" : "channels"}`}
          />
          <SummaryRow
            label={ob("summary_target")}
            value={targetChannel ? `@${targetChannel}` : ob("none")}
          />
          <SummaryRow
            label={ob("summary_ghost")}
            value={ghostMode ? ob("on") : ob("off")}
            accent={ghostMode}
          />
          <SummaryRow
            label={ob("summary_auto_pub")}
            value={autoPublish ? ob("on") : ob("off")}
            accent={autoPublish}
          />
        </div>

        <button
          onClick={handleFinish}
          disabled={saving}
          className="w-full rounded-lg bg-[var(--accent-green)] py-3 text-sm font-bold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? ob("saving") : ob("start_monitoring")}
        </button>
      </>
    );
  }

  /* ── Step title map ───────────────────────────────────── */

  const stepTitles: Record<number, string> = {
    0: ob("connect_title"),
    1: ob("verify_title"),
    2: ob("sources_title"),
    3: ob("target_title"),
    4: ob("config_title"),
    5: ob("ready_title"),
  };

  /* ── Can proceed? ─────────────────────────────────────── */

  const canProceed = (): boolean => {
    switch (step) {
      case 0:
        return false; // Step 0 advances via handleConnect
      case 1:
        return false; // Step 1 advances via code/2fa submit
      case 2:
        return selectedSources.size > 0;
      case 3:
        return true; // Optional
      case 4:
        return true; // Optional
      case 5:
        return false; // Step 5 uses its own finish button
      default:
        return false;
    }
  };

  const isOptionalStep = step === 3 || step === 4;
  const showNextButton = step >= 2 && step <= 4;
  const showBackButton = step > (alreadyConnected ? 2 : 0) && step < 5;

  /* ── Render ───────────────────────────────────────────── */

  const stepRenderers: Record<number, () => ReactNode> = {
    0: renderStep0,
    1: renderStep1,
    2: renderStep2,
    3: renderStep3,
    4: renderStep4,
    5: renderStep5,
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[var(--bg-primary)]" dir={lang === "he" ? "rtl" : "ltr"}>
      <div className="relative w-full max-w-lg rounded-2xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-8 shadow-2xl">
        {/* Glow */}
        <div className="pointer-events-none absolute -inset-px rounded-2xl bg-gradient-to-b from-[var(--accent-blue)]/5 to-transparent" />

        {/* Step Dots */}
        <div className="relative">
          <StepDots />
        </div>

        {/* Step Title */}
        <h2 className="relative mb-4 text-lg font-bold text-[var(--text-primary)]">
          {stepTitles[step]}
        </h2>

        {/* Animated Step Content */}
        <div className="relative min-h-[220px]">
          <div
            className={`transition-all duration-300 ease-out ${
              animating
                ? direction === "forward"
                  ? "translate-x-8 opacity-0"
                  : "-translate-x-8 opacity-0"
                : "translate-x-0 opacity-100"
            }`}
          >
            {stepRenderers[step]?.()}
          </div>
        </div>

        {/* Navigation Buttons */}
        {(showBackButton || showNextButton) && (
          <div className="relative mt-6 flex items-center justify-between">
            {showBackButton ? (
              <button
                onClick={goBack}
                className="text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
              >
                {ob("back")}
              </button>
            ) : (
              <div />
            )}

            <div className="flex items-center gap-3">
              {isOptionalStep && (
                <button
                  onClick={goNext}
                  className="text-sm text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                >
                  {ob("skip")}
                </button>
              )}
              {showNextButton && (
                <button
                  onClick={goNext}
                  disabled={!canProceed() && !isOptionalStep}
                  className="rounded-lg bg-[var(--accent-blue)] px-6 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                >
                  {ob("next")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Small helper components ────────────────────────────── */

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative mt-0.5 h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
        checked ? "bg-[var(--accent-blue)]" : "bg-[var(--bg-tertiary)]"
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-[22px]" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function SummaryRow({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span
        className={`text-sm font-medium ${
          accent ? "text-[var(--accent-blue)]" : "text-[var(--text-primary)]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin text-[var(--accent-blue)]"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
