use serde_json::{json, Value};

use std::{
    env, fs,
    path::{Path, PathBuf},
    process,
    time::{SystemTime, UNIX_EPOCH},
};

use tauri::{AppHandle, Manager};

use tauri_plugin_shell::ShellExt;

fn data_root(app: &AppHandle) -> Result<PathBuf, String> {
    let root = app
        .path()
        .app_local_data_dir()
        .map_err(|error| format!("Falha resolvendo AppLocalData: {error}"))?;

    fs::create_dir_all(&root).map_err(|error| format!("Falha criando AppLocalData: {error}"))?;

    Ok(root)
}

fn state_root(app: &AppHandle) -> Result<PathBuf, String> {
    let state = data_root(app)?.join("STATE");

    fs::create_dir_all(&state).map_err(|error| format!("Falha criando STATE: {error}"))?;

    Ok(state)
}

fn request_path(app: &AppHandle) -> Result<PathBuf, String> {
    let ipc = data_root(app)?.join("IPC");

    fs::create_dir_all(&ipc).map_err(|error| format!("Falha criando IPC: {error}"))?;

    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| format!("Falha obtendo timestamp: {error}"))?
        .as_nanos();

    Ok(ipc.join(format!("request-{}-{nanos}.json", process::id(),)))
}

fn cleanup_request(path: &Path) {
    let _ = fs::remove_file(path);
}

async fn backend_bridge(app: &AppHandle, request: Value) -> Result<Value, String> {
    let data = data_root(app)?;

    let state = state_root(app)?;

    let request_file = request_path(app)?;

    let body = serde_json::to_vec(&request)
        .map_err(|error| format!("Falha serializando request: {error}"))?;

    fs::write(&request_file, body)
        .map_err(|error| format!("Falha gravando request IPC: {error}"))?;

    let mut command = app
        .shell()
        .sidecar("rachel-backend")
        .map_err(|error| {
            cleanup_request(&request_file);

            format!("Sidecar RACHEL indisponivel: {error}")
        })?
        .arg("--request-file")
        .arg(&request_file)
        .env("RACHEL_STATE_ROOT", &state)
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .current_dir(&data);

    if let Ok(provider) = env::var("RACHEL_MODEL_PROVIDER") {
        command = command.env("RACHEL_MODEL_PROVIDER", provider);
    }

    let output = command.output().await.map_err(|error| {
        cleanup_request(&request_file);

        format!("Falha executando sidecar RACHEL: {error}")
    })?;

    cleanup_request(&request_file);

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() {
        return Err(format!(
            "Backend RACHEL encerrou com codigo {:?}: {}",
            output.status.code(),
            if stderr.is_empty() {
                stdout.trim()
            } else {
                &stderr
            }
        ));
    }

    let line = stdout
        .lines()
        .rev()
        .find(|line| !line.trim().is_empty())
        .ok_or_else(|| format!("Backend sem JSON. stderr={stderr}"))?;

    let response: Value = serde_json::from_str(line.trim()).map_err(|error| {
        format!("JSON invalido do backend: {error}; stdout={stdout}; stderr={stderr}")
    })?;

    if response.get("ok").and_then(Value::as_bool) != Some(true) {
        let message = response
            .get("error")
            .and_then(|error| error.get("message"))
            .and_then(Value::as_str)
            .unwrap_or("Falha desconhecida");

        return Err(message.to_string());
    }

    response
        .get("payload")
        .cloned()
        .ok_or_else(|| "payload ausente".to_string())
}

#[tauri::command]
async fn rachel_dashboard(app: AppHandle) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "dashboard"
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_status(app: AppHandle) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "status"
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_chat(
    app: AppHandle,
    content: String,
    conversation_id: Option<String>,
) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "chat",
            "content": content,
            "conversation_id": conversation_id,
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_assist(
    app: AppHandle,
    content: String,
    conversation_id: Option<String>,
    approval_id: Option<String>,
) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "assist",
            "content": content,
            "conversation_id": conversation_id,
            "approval_id": approval_id,
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_security_snapshot(app: AppHandle, limit: Option<i64>) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "security_snapshot",
            "limit": limit.unwrap_or(50),
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_security_decide(
    app: AppHandle,
    approval_id: String,
    allow: bool,
    confirmation: String,
) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "security_decide",
            "approval_id": approval_id,
            "allow": allow,
            "confirmation": confirmation,
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_memory_search(
    app: AppHandle,
    query: String,
    limit: Option<i64>,
) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "memory_search",
            "query": query,
            "limit": limit.unwrap_or(10),
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_voice_status(
    app: AppHandle,
    include_hardware: Option<bool>,
) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "voice_status",
            "include_hardware": include_hardware.unwrap_or(true),
        }),
    )
    .await
}

#[tauri::command]
async fn rachel_health(app: AppHandle) -> Result<Value, String> {
    backend_bridge(
        &app,
        json!({
            "action": "health"
        }),
    )
    .await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            rachel_dashboard,
            rachel_status,
            rachel_chat,
            rachel_assist,
            rachel_security_snapshot,
            rachel_security_decide,
            rachel_memory_search,
            rachel_voice_status,
            rachel_health
        ])
        .run(tauri::generate_context!())
        .expect("error while running RACHEL IA");
}
