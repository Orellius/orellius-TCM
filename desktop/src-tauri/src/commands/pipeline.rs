use serde::{Deserialize, Serialize};

const API_BASE: &str = "http://127.0.0.1:8000/api";

#[derive(Serialize, Deserialize)]
pub struct PipelineStatus {
    pub running: bool,
    pub agents: std::collections::HashMap<String, String>,
    pub queue_size: u32,
}

#[tauri::command]
pub async fn start_pipeline() -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/pipeline/start", API_BASE))
        .send()
        .await
        .map_err(|e| format!("Failed to start pipeline: {}", e))?;

    resp.text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))
}

#[tauri::command]
pub async fn stop_pipeline() -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/pipeline/stop", API_BASE))
        .send()
        .await
        .map_err(|e| format!("Failed to stop pipeline: {}", e))?;

    resp.text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))
}

#[tauri::command]
pub async fn get_status() -> Result<PipelineStatus, String> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/pipeline/status", API_BASE))
        .send()
        .await
        .map_err(|e| format!("Failed to get status: {}", e))?;

    resp.json::<PipelineStatus>()
        .await
        .map_err(|e| format!("Failed to parse status: {}", e))
}
