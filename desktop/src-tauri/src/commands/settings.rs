use serde::{Deserialize, Serialize};

const API_BASE: &str = "http://127.0.0.1:8000/api";

#[derive(Serialize, Deserialize, Clone)]
pub struct AppSettings {
    pub publish_delay: u32,
    pub auto_publish: bool,
    pub stamp_enabled: bool,
    pub stamp_image_path: String,
    pub target_channel: String,
}

#[tauri::command]
pub async fn get_settings() -> Result<AppSettings, String> {
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("{}/settings", API_BASE))
        .send()
        .await
        .map_err(|e| format!("Failed to get settings: {}", e))?;

    resp.json::<AppSettings>()
        .await
        .map_err(|e| format!("Failed to parse settings: {}", e))
}

#[tauri::command]
pub async fn update_settings(settings: AppSettings) -> Result<String, String> {
    let client = reqwest::Client::new();
    let resp = client
        .put(format!("{}/settings", API_BASE))
        .json(&settings)
        .send()
        .await
        .map_err(|e| format!("Failed to update settings: {}", e))?;

    resp.text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))
}
