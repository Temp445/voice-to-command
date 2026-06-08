// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{
    CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem, State,
};

struct AppState {
    minimize_to_tray: Mutex<bool>,
}

#[tauri::command]
fn sync_minimize_to_tray(state: State<AppState>, value: bool) {
    if let Ok(mut minimize) = state.minimize_to_tray.lock() {
        *minimize = value;
    }
}

#[tauri::command]
fn get_minimize_to_tray(state: State<AppState>) -> bool {
    state.minimize_to_tray.lock().map(|v| *v).unwrap_or(true)
}

/// Explicitly hide the window to tray (called from frontend instead of relying solely on close event)
#[tauri::command]
fn hide_to_tray(window: tauri::Window) {
    let _ = window.hide();
}

fn main() {
    // System tray menu
    let show = CustomMenuItem::new("show".to_string(), "Show ACE");
    let activate = CustomMenuItem::new("activate".to_string(), "🎤 Activate Listening");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");

    let tray_menu = SystemTrayMenu::new()
        .add_item(show)
        .add_item(activate)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit);

    let system_tray = SystemTray::new().with_menu(tray_menu).with_tooltip("ACE Voice Controller");

    tauri::Builder::default()
        .manage(AppState { minimize_to_tray: Mutex::new(true) })
        .invoke_handler(tauri::generate_handler![
            sync_minimize_to_tray,
            get_minimize_to_tray,
            hide_to_tray
        ])
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "show" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                        let _ = window.unminimize();
                    }
                }
                "activate" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                        let _ = window.emit("tray-activate", ());
                    }
                }
                "quit" => std::process::exit(0),
                _ => {}
            },
            SystemTrayEvent::DoubleClick { .. } => {
                if let Some(window) = app.get_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                    let _ = window.unminimize();
                }
            }
            _ => {}
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event.event() {
                let window = event.window();
                let state = window.state::<AppState>();
                let minimize = state.minimize_to_tray.lock().ok().map(|v| *v).unwrap_or(false);
                if minimize {
                    api.prevent_close();
                    let _ = window.hide();
                }
                // If minimize is false, allow normal close (fall through)
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
