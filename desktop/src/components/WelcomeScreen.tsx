import { useState, useEffect } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { OnboardingWizard } from "./OnboardingWizard";
import { t } from "../lib/i18n";

const API = "http://127.0.0.1:8000/api";

interface WelcomeScreenProps {
  onComplete: () => void;
}

export function WelcomeScreen({ onComplete }: WelcomeScreenProps) {
  const language = useSettingsStore((s) => s.language);
  const setLanguage = useSettingsStore((s) => s.setLanguage);

  const [checking, setChecking] = useState(true);
  const [showWizard, setShowWizard] = useState(false);
  const [alreadyConnected, setAlreadyConnected] = useState(false);
  const [existingChannels, setExistingChannels] = useState<string[]>([]);

  // On mount, check if there is an existing Telegram session
  useEffect(() => {
    let cancelled = false;

    async function checkSession() {
      try {
        const statusRes = await fetch(`${API}/telegram/status`);
        if (!statusRes.ok) {
          if (!cancelled) setChecking(false);
          return;
        }

        const statusData = await statusRes.json();
        const connected =
          statusData.connected === true || statusData.auth_state === "connected";

        if (!connected) {
          if (!cancelled) setChecking(false);
          return;
        }

        // Connected — check if channels are already configured
        const channelsRes = await fetch(`${API}/channels`);
        if (!channelsRes.ok) {
          if (!cancelled) {
            setAlreadyConnected(true);
            setShowWizard(true);
            setChecking(false);
          }
          return;
        }

        const channelsData = await channelsRes.json();
        const channels: string[] = channelsData.channels || [];

        if (channels.length > 0) {
          // Returning user with everything configured — go straight to app
          if (!cancelled) onComplete();
          return;
        }

        // Connected but no channels — show wizard starting from channel selection
        if (!cancelled) {
          setAlreadyConnected(true);
          setExistingChannels(channels);
          setShowWizard(true);
          setChecking(false);
        }
      } catch {
        // Network error or backend down — show welcome screen
        if (!cancelled) setChecking(false);
      }
    }

    checkSession();
    return () => {
      cancelled = true;
    };
  }, [onComplete]);

  // If wizard is active, render it full-screen
  if (showWizard) {
    return (
      <OnboardingWizard
        onComplete={onComplete}
        lang={language}
        alreadyConnected={alreadyConnected}
        existingChannels={existingChannels.length > 0 ? existingChannels : undefined}
      />
    );
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-[var(--bg-primary)]" dir={language === "he" ? "rtl" : "ltr"}>
      <div className="relative w-full max-w-md rounded-2xl border border-[var(--border-color)] bg-[var(--bg-secondary)] p-10 shadow-2xl">
        {/* Subtle glow behind the card */}
        <div className="pointer-events-none absolute -inset-px rounded-2xl bg-gradient-to-b from-[var(--accent-blue)]/5 to-transparent" />

        {/* Logo + Title */}
        <div className="relative mb-8 text-center">
          <div className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-[var(--accent-blue)]/10 ring-1 ring-[var(--accent-blue)]/30">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-7 w-7 text-[var(--accent-blue)]"
            >
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="4" />
              <line x1="12" y1="2" x2="12" y2="6" />
              <line x1="12" y1="18" x2="12" y2="22" />
              <line x1="2" y1="12" x2="6" y2="12" />
              <line x1="18" y1="12" x2="22" y2="12" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            Orellius
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {t("welcome.subtitle", language)}
          </p>
        </div>

        {/* Language Picker */}
        <div className="relative mb-8 flex justify-center gap-3">
          <button
            onClick={() => setLanguage("en")}
            className={`rounded-lg px-5 py-2.5 text-sm font-medium transition-all ${
              language === "en"
                ? "border border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]"
                : "border border-[var(--border-color)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]"
            }`}
          >
            English
          </button>
          <button
            onClick={() => setLanguage("he")}
            className={`rounded-lg px-5 py-2.5 text-sm font-medium transition-all ${
              language === "he"
                ? "border border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]"
                : "border border-[var(--border-color)] bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]"
            }`}
          >
            עברית
          </button>
        </div>

        {/* Tagline */}
        <p className="relative mb-8 text-center text-sm font-medium tracking-wide text-[var(--text-secondary)]">
          {t("welcome.tagline", language)}
        </p>

        {/* Connect Button or Loading Spinner */}
        <div className="relative">
          {checking ? (
            <div className="flex flex-col items-center gap-3 py-2">
              <Spinner />
              <span className="text-xs text-[var(--text-secondary)]">
                {t("welcome.reconnecting", language)}
              </span>
            </div>
          ) : (
            <button
              onClick={() => setShowWizard(true)}
              className="w-full rounded-lg bg-[var(--accent-blue)] py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90 active:opacity-80"
            >
              {t("welcome.connect_btn", language)}
              <span className="ms-2">{"\u2192"}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Spinner ────────────────────────────────────────────── */

function Spinner() {
  return (
    <svg
      className="h-5 w-5 animate-spin text-[var(--accent-blue)]"
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
