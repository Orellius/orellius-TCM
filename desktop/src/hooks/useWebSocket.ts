import { useEffect } from "react";
import { listen } from "@tauri-apps/api/event";
import { usePipelineStore } from "../stores/pipelineStore";
import { useLogStore, type LogEntry } from "../stores/logStore";

/**
 * Subscribes to pipeline events forwarded from the Rust WebSocket bridge.
 * Events flow: Python backend → WebSocket → Rust ws_bridge → Tauri event → React
 */
export function usePipelineEvents() {
  const updateFromEvent = usePipelineStore((s) => s.updateFromEvent);
  const addLogEntry = useLogStore((s) => s.addEntry);

  useEffect(() => {
    // Listen for pipeline events from Rust WS bridge
    const unlistenPipeline = listen<string>("pipeline-event", (event) => {
      try {
        const payload = typeof event.payload === "string"
          ? JSON.parse(event.payload)
          : event.payload;

        // Ensure parsed result is an object with a type field
        if (!payload || typeof payload !== "object" || !payload.type) {
          return;
        }

        // Route log entries to the log store
        if (payload.type === "log_entry" && payload.entry) {
          addLogEntry(payload.entry as LogEntry);
          return;
        }

        // Everything else goes to the pipeline store
        updateFromEvent(payload);
      } catch {
        // Non-JSON frames are silently skipped (already filtered in Rust bridge)
      }
    });

    const unlistenStatus = listen<string>("backend-status", () => {});

    // Log that the listener is registered
    unlistenPipeline.then(() => {
      console.log("[WS] Pipeline event listener registered");
    }).catch((err) => {
      console.error("[WS] Failed to register pipeline event listener:", err);
    });

    return () => {
      unlistenPipeline.then((fn) => fn());
      unlistenStatus.then((fn) => fn());
    };
  }, [updateFromEvent, addLogEntry]);
}

/**
 * Polls the REST API as a fallback for when WebSocket events aren't flowing.
 * This ensures the UI stays in sync even if the WS bridge has issues.
 */
export function useRestPolling() {
  const setRunning = usePipelineStore((s) => s.setRunning);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/pipeline/status");
        if (res.ok) {
          const data = await res.json();
          setRunning(data.running);
        }
      } catch {
        // Backend not reachable
      }
    };

    poll(); // Initial fetch
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [setRunning]);
}
