use tauri::Manager;

mod commands;
mod ws_bridge;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // A second instance tried to launch — focus the existing window instead
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
            log::info!("Blocked duplicate instance — focused existing window");
        }))
        .setup(|app| {
            let handle = app.handle().clone();

            // Spawn the WebSocket bridge to the Python backend
            tauri::async_runtime::spawn(async move {
                ws_bridge::run_bridge(handle).await;
            });

            log::info!("Orellius Telegram Manager initialized");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::pipeline::start_pipeline,
            commands::pipeline::stop_pipeline,
            commands::pipeline::get_status,
            commands::channels::list_channels,
            commands::channels::add_channel,
            commands::channels::remove_channel,
            commands::settings::get_settings,
            commands::settings::update_settings,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
