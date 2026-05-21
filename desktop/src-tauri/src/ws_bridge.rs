use futures_util::StreamExt;
use tauri::{AppHandle, Emitter};
use tokio_tungstenite::connect_async;

const WS_BASE: &str = "ws://127.0.0.1:8000/ws";
const RECONNECT_DELAY_SECS: u64 = 3;

/// Build the WS URL, appending ?token=<token> if API_SECRET_TOKEN env is set.
fn ws_url() -> String {
    match std::env::var("API_SECRET_TOKEN") {
        Ok(token) if !token.is_empty() => format!("{}?token={}", WS_BASE, token),
        _ => WS_BASE.to_string(),
    }
}

/// Maintains a persistent WebSocket connection to the Python backend.
/// Forwards all incoming messages as Tauri events to the React frontend.
/// Auto-reconnects on disconnect. Only forwards valid JSON text frames.
pub async fn run_bridge(app: AppHandle) {
    let url = ws_url();
    loop {
        log::info!("Connecting to Python backend at {}", WS_BASE);

        match connect_async(&url).await {
            Ok((ws_stream, _)) => {
                log::info!("WebSocket connected to Python backend");
                let _ = app.emit("backend-status", "connected");

                let (_write, mut read) = ws_stream.split();

                while let Some(msg_result) = read.next().await {
                    match msg_result {
                        Ok(msg) => {
                            if let Ok(text) = msg.to_text() {
                                // Only forward frames that look like JSON objects
                                let trimmed = text.trim();
                                if !trimmed.starts_with('{') {
                                    log::warn!("Skipping non-JSON WS frame ({} bytes): {:?}",
                                        text.len(),
                                        &text[..text.len().min(50)]);
                                    continue;
                                }
                                if let Err(e) = app.emit("pipeline-event", text) {
                                    log::error!("Failed to emit event: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            log::error!("WebSocket read error: {}", e);
                            break;
                        }
                    }
                }

                log::warn!("WebSocket disconnected from Python backend");
                let _ = app.emit("backend-status", "disconnected");
            }
            Err(e) => {
                log::warn!("Failed to connect to Python backend: {}", e);
                let _ = app.emit("backend-status", "disconnected");
            }
        }

        // Wait before reconnecting
        tokio::time::sleep(std::time::Duration::from_secs(RECONNECT_DELAY_SECS)).await;
    }
}
