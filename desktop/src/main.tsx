import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/globals.css";

// ── Global crash handlers ─────────────────────────────────────
// Catches errors that happen outside React's tree (module-level,
// async code, event listeners, Vite HMR failures).

function showCrashOverlay(title: string, detail: string) {
  // Don't overwrite existing overlay
  if (document.getElementById("orellius-crash-overlay")) return;

  const overlay = document.createElement("div");
  overlay.id = "orellius-crash-overlay";
  Object.assign(overlay.style, {
    position: "fixed", inset: "0", zIndex: "99999",
    background: "#1a1a2e", color: "#e0e0e0", fontFamily: "monospace",
    padding: "32px", overflow: "auto",
  });
  overlay.innerHTML = `
    <div style="max-width:800px;margin:0 auto">
      <h1 style="color:#ff4444;font-size:20px;margin:0 0 8px">Orellius — Uncaught Error</h1>
      <p style="color:#888;font-size:13px;margin:0 0 16px">${title}</p>
      <pre style="background:#0d0d1a;border:1px solid #333;border-radius:8px;padding:16px;
        font-size:11px;color:#aaa;white-space:pre-wrap;word-break:break-word;max-height:400px;overflow:auto">${detail}</pre>
      <div style="margin-top:16px;display:flex;gap:8px">
        <button onclick="document.getElementById('orellius-crash-overlay')?.remove()"
          style="background:#333;color:#ccc;border:1px solid #555;border-radius:6px;padding:8px 20px;cursor:pointer;font-size:13px">
          Dismiss
        </button>
        <button onclick="window.location.reload()"
          style="background:#2563eb;color:white;border:none;border-radius:6px;padding:8px 20px;cursor:pointer;font-size:13px;font-weight:600">
          Reload
        </button>
        <button onclick="navigator.clipboard.writeText(document.querySelector('#orellius-crash-overlay pre')?.textContent||'')"
          style="background:#333;color:#ccc;border:1px solid #555;border-radius:6px;padding:8px 20px;cursor:pointer;font-size:13px">
          Copy
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
}

window.addEventListener("error", (event) => {
  console.error("[Global Error]", event.error ?? event.message);
  const detail = event.error?.stack ?? `${event.message}\nat ${event.filename}:${event.lineno}:${event.colno}`;
  showCrashOverlay("An uncaught error occurred", detail);
});

window.addEventListener("unhandledrejection", (event) => {
  const err = event.reason;
  console.error("[Unhandled Promise Rejection]", err);
  const detail = err instanceof Error ? (err.stack ?? err.message) : String(err);
  showCrashOverlay("Unhandled promise rejection", detail);
});

// ── Render ────────────────────────────────────────────────────

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
