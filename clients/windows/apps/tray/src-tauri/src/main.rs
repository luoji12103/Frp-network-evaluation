use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;

#[tauri::command]
fn service_status_label() -> String {
    "Uninitialized".to_string()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![service_status_label])
        .setup(|app| {
            let initialize = MenuItem::with_id(
                app,
                "initialize",
                "Initialize / Reconfigure",
                true,
                None::<&str>,
            )?;
            let restart = MenuItem::with_id(app, "restart", "Restart Service", true, None::<&str>)?;
            let open_config = MenuItem::with_id(
                app,
                "open_config",
                "Open Config File",
                true,
                None::<&str>,
            )?;
            let open_logs =
                MenuItem::with_id(app, "open_logs", "Open Logs Folder", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Tray", true, None::<&str>)?;
            let menu =
                Menu::with_items(app, &[&initialize, &restart, &open_config, &open_logs, &quit])?;
            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("mc-netprobe Client")
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run mc-netprobe tray");
}
