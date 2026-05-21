import { Component, useState, useEffect, type ReactNode } from "react";
import { Dashboard } from "./components/Dashboard";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { ToastContainer } from "./components/Toast";
import { usePipelineEvents, useRestPolling } from "./hooks/useWebSocket";
import { useSettingsStore } from "./stores/settingsStore";
import { t } from "./lib/i18n";

type AppState = "loading" | "onboarding" | "dashboard";

interface ErrorBoundaryState {
  error: Error | null;
  errorInfo: string;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, errorInfo: "" };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    const errorInfo = [
      `[${new Date().toISOString()}] React ErrorBoundary caught:`,
      `Message: ${error.message}`,
      `Stack: ${error.stack ?? "N/A"}`,
      `Component stack: ${info.componentStack ?? "N/A"}`,
    ].join("\n");
    console.error(errorInfo);
    this.setState({ errorInfo });
    // Persist to sessionStorage so it survives hot reload
    try {
      const log = JSON.parse(sessionStorage.getItem("orellius_crash_log") ?? "[]");
      log.push({ ts: Date.now(), message: error.message, stack: error.stack, component: info.componentStack });
      sessionStorage.setItem("orellius_crash_log", JSON.stringify(log.slice(-20)));
    } catch { /* ignore */ }
  }

  render() {
    if (this.state.error) {
      const fullReport = this.state.errorInfo;
      return (
        <div style={{
          background: "#1a1a2e", color: "#e0e0e0", padding: 32, fontFamily: "monospace",
          height: "100vh", width: "100vw", overflow: "auto", boxSizing: "border-box",
        }}>
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
              <span style={{ fontSize: 32 }}>X</span>
              <div>
                <h1 style={{ color: "#ff4444", margin: 0, fontSize: 20 }}>Orellius Crashed</h1>
                <p style={{ color: "#888", margin: "4px 0 0", fontSize: 13 }}>
                  The app hit an unrecoverable error. Details below.
                </p>
              </div>
            </div>

            <div style={{
              background: "#0d0d1a", border: "1px solid #333", borderRadius: 8,
              padding: 16, marginBottom: 16, fontSize: 13,
            }}>
              <div style={{ color: "#ff6b6b", fontWeight: 600, marginBottom: 8 }}>
                {this.state.error.message}
              </div>
              <pre style={{
                color: "#aaa", fontSize: 11, whiteSpace: "pre-wrap", wordBreak: "break-word",
                maxHeight: 300, overflow: "auto", margin: 0,
              }}>
                {this.state.error.stack}
              </pre>
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => {
                  this.setState({ error: null, errorInfo: "" });
                }}
                style={{
                  background: "#2563eb", color: "white", border: "none", borderRadius: 6,
                  padding: "8px 20px", cursor: "pointer", fontSize: 13, fontWeight: 600,
                }}
              >
                Retry
              </button>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(fullReport);
                }}
                style={{
                  background: "#333", color: "#ccc", border: "1px solid #555", borderRadius: 6,
                  padding: "8px 20px", cursor: "pointer", fontSize: 13,
                }}
              >
                Copy Error
              </button>
              <button
                onClick={() => window.location.reload()}
                style={{
                  background: "#333", color: "#ccc", border: "1px solid #555", borderRadius: 6,
                  padding: "8px 20px", cursor: "pointer", fontSize: 13,
                }}
              >
                Full Reload
              </button>
            </div>

            <p style={{ color: "#555", fontSize: 11, marginTop: 16 }}>
              Crash log saved to session storage. Check console for full details.
            </p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function LoadingScreen({ lang }: { lang: "he" | "en" }) {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-[var(--bg-primary)]">
      <div className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-full bg-[var(--accent-blue)]/10 ring-1 ring-[var(--accent-blue)]/30 animate-pulse">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="h-8 w-8 text-[var(--accent-blue)]">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="4" />
          <line x1="12" y1="2" x2="12" y2="6" />
          <line x1="12" y1="18" x2="12" y2="22" />
          <line x1="2" y1="12" x2="6" y2="12" />
          <line x1="18" y1="12" x2="22" y2="12" />
        </svg>
      </div>
      <p className="text-sm text-[var(--text-secondary)]">{t("loading.initializing", lang)}</p>
    </div>
  );
}

function App() {
  usePipelineEvents();
  useRestPolling();

  const uiScale = useSettingsStore((s) => s.uiScale);
  const lang = useSettingsStore((s) => s.language);
  const setTelegramConnected = useSettingsStore((s) => s.setTelegramConnected);
  const setOnboardingComplete = useSettingsStore((s) => s.setOnboardingComplete);

  const [appState, setAppState] = useState<AppState>("loading");

  useEffect(() => {
    const start = Date.now();
    const onboardingComplete = useSettingsStore.getState().onboardingComplete;

    if (!onboardingComplete) {
      // Ensure minimum loading time
      const elapsed = Date.now() - start;
      const remaining = Math.max(0, 800 - elapsed);
      setTimeout(() => setAppState("onboarding"), remaining);
      return;
    }

    // Onboarding done — check Telegram status
    fetch("http://127.0.0.1:8000/api/telegram/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.connected) {
          setTelegramConnected(true);
        }
      })
      .catch(() => {})
      .finally(() => {
        const elapsed = Date.now() - start;
        const remaining = Math.max(0, 800 - elapsed);
        setTimeout(() => setAppState("dashboard"), remaining);
      });
  }, [setTelegramConnected]);

  const handleOnboardingComplete = () => {
    setOnboardingComplete(true);
    setTelegramConnected(true);
    setAppState("dashboard");
  };

  return (
    <ErrorBoundary>
      <div
        className="flex h-screen w-screen bg-[var(--bg-primary)]"
        style={{ zoom: uiScale }}
      >
        {appState === "loading" ? (
          <LoadingScreen lang={lang} />
        ) : appState === "onboarding" ? (
          <WelcomeScreen onComplete={handleOnboardingComplete} />
        ) : (
          <Dashboard />
        )}
        <ToastContainer />
      </div>
    </ErrorBoundary>
  );
}

export default App;
