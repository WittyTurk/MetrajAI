use std::sync::Mutex;

use serde::Serialize;
use tauri::{Manager, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Clone, Serialize)]
struct EngineConnection {
    url: Option<String>,
    token: String,
    status: String,
}

struct EngineState {
    connection: Mutex<EngineConnection>,
    child: Mutex<Option<CommandChild>>,
}

fn stop_engine(app: &tauri::AppHandle) {
    if let Ok(mut child) = app.state::<EngineState>().child.lock() {
        if let Some(process) = child.take() {
            let _ = process.kill();
        }
    }
}

#[tauri::command]
fn engine_connection(state: State<'_, EngineState>) -> Result<EngineConnection, String> {
    state
        .connection
        .lock()
        .map(|connection| connection.clone())
        .map_err(|_| "Engine state is unavailable".to_string())
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let token = uuid::Uuid::new_v4().to_string();
            app.manage(EngineState {
                connection: Mutex::new(EngineConnection {
                    url: None,
                    token: token.clone(),
                    status: "starting".to_string(),
                }),
                child: Mutex::new(None),
            });

            let parent_pid = std::process::id().to_string();
            let mut sidecar = app
                .shell()
                .sidecar("metrajai-engine")?
                .args([
                    "serve",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "0",
                    "--token",
                    &token,
                    "--parent-pid",
                    &parent_pid,
                ]);
            let report_runtime = app.path().resource_dir()?.join("resources/report-runtime");
            let node_name = if cfg!(windows) { "node.exe" } else { "node" };
            let node_binary = report_runtime.join(node_name);
            let node_modules = report_runtime.join("node_modules");
            if node_binary.is_file() && node_modules.is_dir() {
                sidecar = sidecar
                    .env("METRAJAI_NODE_BINARY", node_binary)
                    .env("METRAJAI_ARTIFACT_NODE_MODULES", node_modules);
            }
            let ocr_binary = app.path().resource_dir()?.join("resources/metrajai-ocr");
            if ocr_binary.is_file() {
                sidecar = sidecar.env("METRAJAI_OCR_BINARY", ocr_binary);
            }
            let (mut receiver, child) = sidecar.spawn()?;
            if let Ok(mut slot) = app.state::<EngineState>().child.lock() {
                *slot = Some(child);
            }

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = receiver.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            let line = String::from_utf8_lossy(&bytes);
                            if let Ok(payload) = serde_json::from_str::<serde_json::Value>(&line) {
                                if payload.get("event").and_then(|value| value.as_str()) == Some("ready") {
                                    if let Some(port) = payload.get("port").and_then(|value| value.as_u64()) {
                                        if let Ok(mut connection) = handle.state::<EngineState>().connection.lock() {
                                            connection.url = Some(format!("http://127.0.0.1:{port}"));
                                            connection.status = "ready".to_string();
                                        }
                                    }
                                }
                            }
                        }
                        CommandEvent::Error(message) => {
                            if let Ok(mut connection) = handle.state::<EngineState>().connection.lock() {
                                connection.status = format!("error: {message}");
                            }
                        }
                        CommandEvent::Terminated(payload) => {
                            if let Ok(mut connection) = handle.state::<EngineState>().connection.lock() {
                                connection.status = format!("stopped: {:?}", payload.code);
                                connection.url = None;
                            }
                        }
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine_connection])
        .on_window_event(|window, event| {
            if matches!(event, tauri::WindowEvent::CloseRequested { .. }) {
                stop_engine(window.app_handle());
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building MetrajAI desktop application");
    app.run(|app_handle, event| {
        if matches!(
            event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            stop_engine(app_handle);
        }
    });
}
