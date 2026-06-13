// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{Manager, State, Emitter};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, TrayIconBuilder, TrayIconEvent};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_autostart::ManagerExt;

struct AppState {
    minimize_to_tray: Mutex<bool>,
    backend_port: u16,
}

#[tauri::command]
fn sync_minimize_to_tray(state: State<'_, AppState>, value: bool) {
    if let Ok(mut minimize) = state.minimize_to_tray.lock() {
        *minimize = value;
    }
}

#[tauri::command]
fn get_minimize_to_tray(state: State<'_, AppState>) -> bool {
    state.minimize_to_tray.lock().map(|v| *v).unwrap_or(true)
}

#[tauri::command]
fn get_backend_port(state: State<'_, AppState>) -> u16 {
    state.backend_port
}

/// Explicitly hide the window to tray (called from frontend instead of relying solely on close event)
#[tauri::command]
fn hide_to_tray(window: tauri::Window) {
    let _ = window.hide();
}

#[tauri::command]
fn enable_autostart(app: tauri::AppHandle) -> Result<(), String> {
    app.autolaunch().enable().map_err(|e| e.to_string())
}

#[tauri::command]
fn disable_autostart(app: tauri::AppHandle) -> Result<(), String> {
    app.autolaunch().disable().map_err(|e| e.to_string())
}

#[tauri::command]
fn is_autostart_enabled(app: tauri::AppHandle) -> Result<bool, String> {
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

fn get_available_port() -> u16 {
    std::net::TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .unwrap_or(8000) // Fallback to 8000 if finding a dynamic port fails
}

fn main() {
    let port = get_available_port();

    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, Some(vec!["--hidden"])))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let show_i = MenuItem::with_id(app, "show", "Show ACE", true, None::<&str>)?;
            let activate_i = MenuItem::with_id(app, "activate", "🎤 Activate Listening", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let separator = PredefinedMenuItem::separator(app)?;
            let menu = Menu::with_items(app, &[&show_i, &activate_i, &separator, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("ACE Voice Controller")
                .icon(app.default_window_icon().unwrap().clone())
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                            let _ = window.unminimize();
                        }
                    }
                    "activate" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                            let _ = window.emit("tray-activate", ());
                        }
                    }
                    "quit" => {
                        std::process::exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                            let _ = window.unminimize();
                        }
                    }
                })
                .build(app)?;

            let args: Vec<String> = std::env::args().collect();
            if args.contains(&"--hidden".to_string()) {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }

            let backend_exe = if cfg!(debug_assertions) {
                // During tauri dev, use the built executable from dist directly
                std::path::PathBuf::from("../../backend/dist/ace-backend/ace-backend.exe")
            } else {
                // In release, the binary is bundled in the resources folder
                app.path().resolve("../../backend/dist/ace-backend/ace-backend.exe", tauri::path::BaseDirectory::Resource).expect("failed to resolve resource")
            };

            let mut cmd = std::process::Command::new(backend_exe);
            cmd.env("BACKEND_PORT", port.to_string());
            
            if cfg!(debug_assertions) {
                // Ensure backend runs from project root during dev to find .env file
                cmd.current_dir("../../");
            }
            
            cmd.spawn().expect("Failed to spawn backend sidecar");
            
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
            get_backend_port,
            enable_autostart,
            disable_autostart,
            is_autostart_enabled
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
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
