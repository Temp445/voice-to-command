// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{
    CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem, State,
};

use tauri::api::process::Command;

struct AppState {
    minimize_to_tray: Mutex<bool>,
    backend_port: u16,
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

#[tauri::command]
fn get_backend_port(state: State<AppState>) -> u16 {
    state.backend_port
}

/// Explicitly hide the window to tray (called from frontend instead of relying solely on close event)
#[tauri::command]
fn hide_to_tray(window: tauri::Window) {
    let _ = window.hide();
}

fn get_available_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .unwrap_or(8000) // Fallback to 8000 if finding a dynamic port fails
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

    let port = get_available_port();

    tauri::Builder::default()
        .setup(move |_app| {
            let mut env = std::collections::HashMap::new();
            env.insert("BACKEND_PORT".to_string(), port.to_string());
            
            let (_rx, _child) = Command::new_sidecar("ace-backend")
                .expect("failed to create `ace-backend` binary command")
                .envs(env)
                .spawn()
                .expect("Failed to spawn sidecar");
            
            Ok(())
        })
        .manage(AppState { 
            minimize_to_tray: Mutex::new(true),
            backend_port: port,
        })
        .invoke_handler(tauri::generate_handler![
            sync_minimize_to_tray,
            get_minimize_to_tray,
            hide_to_tray,
            get_backend_port
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
