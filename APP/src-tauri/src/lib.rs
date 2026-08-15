use serde_json::{json, Value};
use std::{
    env,
    io::Write,
    path::PathBuf,
    process::{Command, Stdio},
};


fn repository_root() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("RACHEL_REPO_ROOT") {
        let configured = PathBuf::from(value);

        if configured.exists() {
            return configured
                .canonicalize()
                .map_err(|error| error.to_string());
        }
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .canonicalize()
        .map_err(|error| {
            format!("Falha resolvendo raiz da Rachel: {error}")
        })
}


fn python_bridge(
    request: Value,
) -> Result<Value, String> {
    let root = repository_root()?;

    let python = root
        .join("AMBIENTES")
        .join("runtime")
        .join("Scripts")
        .join("python.exe");

    let bridge = root
        .join("APP")
        .join("bridge")
        .join("rachel_bridge.py");

    if !python.is_file() {
        return Err(format!(
            "Runtime Python ausente: {}",
            python.display()
        ));
    }

    if !bridge.is_file() {
        return Err(format!(
            "Bridge Python ausente: {}",
            bridge.display()
        ));
    }

    let mut child = Command::new(&python)
        .arg(&bridge)
        .current_dir(&root)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| {
            format!("Falha iniciando backend: {error}")
        })?;

    let body = serde_json::to_vec(&request)
        .map_err(|error| error.to_string())?;

    child
        .stdin
        .as_mut()
        .ok_or_else(|| "stdin indisponivel".to_string())?
        .write_all(&body)
        .map_err(|error| {
            format!("Falha enviando request: {error}")
        })?;

    let output = child
        .wait_with_output()
        .map_err(|error| {
            format!("Falha aguardando backend: {error}")
        })?;

    let stdout = String::from_utf8_lossy(
        &output.stdout
    )
    .to_string();

    let stderr = String::from_utf8_lossy(
        &output.stderr
    )
    .trim()
    .to_string();

    let line = stdout
        .lines()
        .rev()
        .find(|line| !line.trim().is_empty())
        .ok_or_else(|| {
            format!(
                "Backend sem JSON. stderr={stderr}"
            )
        })?;

    let response: Value =
        serde_json::from_str(line.trim())
            .map_err(|error| {
                format!(
                    "JSON invalido: {error}; stdout={stdout}; stderr={stderr}"
                )
            })?;

    if response
        .get("ok")
        .and_then(Value::as_bool)
        != Some(true)
    {
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
fn rachel_status() -> Result<Value, String> {
    python_bridge(
        json!({
            "action": "status"
        })
    )
}


#[tauri::command]
fn rachel_chat(
    content: String,
    conversation_id: Option<String>,
) -> Result<Value, String> {
    python_bridge(
        json!({
            "action": "chat",
            "content": content,
            "conversation_id": conversation_id,
        })
    )
}


#[tauri::command]
fn rachel_assist(
    content: String,
    conversation_id: Option<String>,
    approval_id: Option<String>,
) -> Result<Value, String> {
    python_bridge(
        json!({
            "action": "assist",
            "content": content,
            "conversation_id": conversation_id,
            "approval_id": approval_id,
        })
    )
}


#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(
            tauri::generate_handler![
                rachel_status,
                rachel_chat,
                rachel_assist
            ]
        )
        .run(tauri::generate_context!())
        .expect("error while running RACHEL IA");
}
