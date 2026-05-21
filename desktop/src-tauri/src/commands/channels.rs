use serde::{Deserialize, Serialize};

const API_BASE: &str = "http://127.0.0.1:8000/api";

#[derive(Serialize, Deserialize)]
pub struct ChannelList {
    pub channels: Vec<String>,
}

#[tauri::command]
pub async fn list_channels() -> Result<ChannelList, String> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/channels", API_BASE))
        .send()
        .await
        .map_err(|e| format!("Failed to list channels: {}", e))?;

    resp.json::<ChannelList>()
        .await
        .map_err(|e| format!("Failed to parse channels: {}", e))
}

#[tauri::command]
pub async fn add_channel(channel: String) -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/channels", API_BASE))
        .json(&serde_json::json!({ "channel": channel }))
        .send()
        .await
        .map_err(|e| format!("Failed to add channel: {}", e))?;

    resp.text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))
}

#[tauri::command]
pub async fn remove_channel(channel: String) -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .delete(format!("{}/channels/{}", API_BASE, channel))
        .send()
        .await
        .map_err(|e| format!("Failed to remove channel: {}", e))?;

    resp.text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))
}
