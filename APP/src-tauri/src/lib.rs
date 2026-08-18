use serde_json::{json, Value};

use std::{
    collections::HashMap,
    env, fs,
    path::PathBuf,
    process,
    sync::{
        atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering},
        Arc, Mutex,
    },
};

use tauri::{async_runtime, AppHandle, Emitter, Manager, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Default)]
struct ResumeStore {
    plans: Mutex<HashMap<String, Value>>,
}

impl ResumeStore {
    fn remember(&self, approval_id: String, plan: Value) {
        if let Ok(mut plans) = self.plans.lock() {
            plans.insert(approval_id, plan);
        }
    }

    fn take(&self, approval_id: &str) -> Option<Value> {
        self.plans
            .lock()
            .ok()
            .and_then(|mut plans| plans.remove(approval_id))
    }

    fn forget(&self, approval_id: &str) {
        if let Ok(mut plans) = self.plans.lock() {
            plans.remove(approval_id);
        }
    }
}

struct BackendInner {
    child: Mutex<Option<CommandChild>>,
    pending: Mutex<HashMap<String, async_runtime::Sender<Result<Value, String>>>>,
    stdout_buffer: Mutex<String>,
    start_lock: async_runtime::Mutex<()>,
    started: AtomicBool,
    pid: AtomicU32,
    sequence: AtomicU64,
}

impl Default for BackendInner {
    fn default() -> Self {
        Self {
            child: Mutex::new(None),
            pending: Mutex::new(HashMap::new()),
            stdout_buffer: Mutex::new(String::new()),
            start_lock: async_runtime::Mutex::new(()),
            started: AtomicBool::new(false),
            pid: AtomicU32::new(0),
            sequence: AtomicU64::new(0),
        }
    }
}

#[derive(Clone, Default)]
struct BackendHost {
    inner: Arc<BackendInner>,
}

impl BackendHost {
    fn snapshot(&self) -> Value {
        let pending = self
            .inner
            .pending
            .lock()
            .map(|items| items.len())
            .unwrap_or(0);

        json!({
            "resident": self.inner.started.load(Ordering::Acquire),
            "pid": match self.inner.pid.load(Ordering::Acquire) {
                0 => Value::Null,
                value => json!(value),
            },
            "pending_requests": pending,
            "transport": "stdio-ndjson",
            "persistent_ipc": true,
            "streaming_events": true,
            "cancellable_generation": true,
        })
    }

    async fn ensure_started(&self, app: &AppHandle) -> Result<(), String> {
        if self.inner.started.load(Ordering::Acquire) {
            return Ok(());
        }

        let _start_guard = self.inner.start_lock.lock().await;
        if self.inner.started.load(Ordering::Acquire) {
            return Ok(());
        }

        let data = data_root(app)?;
        let state = state_root(app)?;

        let mut command = app
            .shell()
            .sidecar("rachel-backend")
            .map_err(|error| format!("Sidecar RACHEL indisponivel: {error}"))?
            .arg("--server")
            .env("RACHEL_STATE_ROOT", &state)
            .env("PYTHONUTF8", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .current_dir(&data);

        for key in [
            "RACHEL_MODEL_PROVIDER",
            "RACHEL_MODEL_NAME",
            "RACHEL_MODEL_BASE_URL",
            "RACHEL_MODEL_API_KEY",
            "RACHEL_MODEL_TIMEOUT_SECONDS",
            "RACHEL_RUNTIME_ROOT",
        ] {
            if let Ok(value) = env::var(key) {
                command = command.env(key, value);
            }
        }

        let (mut receiver, child) = command
            .spawn()
            .map_err(|error| format!("Falha iniciando backend residente RACHEL: {error}"))?;

        let pid = child.pid();
        {
            let mut slot = self
                .inner
                .child
                .lock()
                .map_err(|_| "Backend child lock poisoned".to_string())?;
            *slot = Some(child);
        }
        if let Ok(mut buffer) = self.inner.stdout_buffer.lock() {
            buffer.clear();
        }

        self.inner.pid.store(pid, Ordering::Release);
        self.inner.started.store(true, Ordering::Release);

        let app_handle = app.clone();
        let inner = Arc::clone(&self.inner);

        async_runtime::spawn(async move {
            while let Some(event) = receiver.recv().await {
                match event {
                    CommandEvent::Stdout(bytes) => {
                        route_stdout_bytes(&app_handle, &inner, &bytes).await;
                    }
                    CommandEvent::Stderr(bytes) => {
                        let text = String::from_utf8_lossy(&bytes).trim().to_string();
                        if !text.is_empty() {
                            let _ = app_handle.emit(
                                "rachel-runtime-event",
                                json!({
                                    "kind": "diagnostic",
                                    "level": "stderr",
                                    "message": text,
                                }),
                            );
                        }
                    }
                    CommandEvent::Error(error) => {
                        let _ = app_handle.emit(
                            "rachel-runtime-event",
                            json!({
                                "kind": "diagnostic",
                                "level": "error",
                                "message": error,
                            }),
                        );
                    }
                    CommandEvent::Terminated(payload) => {
                        inner.started.store(false, Ordering::Release);
                        inner.pid.store(0, Ordering::Release);
                        if let Ok(mut child) = inner.child.lock() {
                            *child = None;
                        }
                        if let Ok(mut buffer) = inner.stdout_buffer.lock() {
                            buffer.clear();
                        }

                        let pending = if let Ok(mut map) = inner.pending.lock() {
                            map.drain().map(|(_, sender)| sender).collect::<Vec<_>>()
                        } else {
                            Vec::new()
                        };
                        let reason = format!(
                            "Backend RACHEL encerrou inesperadamente: code={:?} signal={:?}",
                            payload.code, payload.signal
                        );
                        for sender in pending {
                            let _ = sender.send(Err(reason.clone())).await;
                        }
                        let _ = app_handle.emit(
                            "rachel-runtime-event",
                            json!({
                                "kind": "runtime.terminated",
                                "code": payload.code,
                                "signal": payload.signal,
                            }),
                        );
                        break;
                    }
                    _ => {}
                }
            }
        });

        Ok(())
    }

    async fn request(&self, app: &AppHandle, payload: Value) -> Result<Value, String> {
        self.ensure_started(app).await?;

        let sequence = self.inner.sequence.fetch_add(1, Ordering::AcqRel) + 1;
        let request_id = format!("req-{}-{sequence}", process::id());
        let envelope = json!({
            "request_id": request_id,
            "payload": payload,
        });
        let mut line = serde_json::to_vec(&envelope)
            .map_err(|error| format!("Falha serializando request residente: {error}"))?;
        line.push(b'\n');

        let (sender, mut receiver) = async_runtime::channel(1);
        {
            let mut pending = self
                .inner
                .pending
                .lock()
                .map_err(|_| "Backend pending lock poisoned".to_string())?;
            pending.insert(request_id.clone(), sender);
        }

        let write_result = {
            let mut child = self
                .inner
                .child
                .lock()
                .map_err(|_| "Backend child lock poisoned".to_string())?;
            match child.as_mut() {
                Some(child) => child
                    .write(&line)
                    .map_err(|error| format!("Falha escrevendo no backend residente: {error}")),
                None => Err("Backend residente nao possui processo ativo".to_string()),
            }
        };

        if let Err(error) = write_result {
            if let Ok(mut pending) = self.inner.pending.lock() {
                pending.remove(&request_id);
            }
            self.inner.started.store(false, Ordering::Release);
            return Err(error);
        }

        match receiver.recv().await {
            Some(result) => result,
            None => Err("Canal de resposta do backend residente foi fechado".to_string()),
        }
    }
}

async fn route_stdout_bytes(
    app: &AppHandle,
    inner: &Arc<BackendInner>,
    bytes: &[u8],
) {
    let incoming = String::from_utf8_lossy(bytes);
    let lines = {
        let mut completed = Vec::new();
        let Ok(mut buffer) = inner.stdout_buffer.lock() else {
            return;
        };
        buffer.push_str(&incoming);

        while let Some(index) = buffer.find('\n') {
            let drained = buffer.drain(..=index).collect::<String>();
            let line = drained.trim().to_string();
            if !line.is_empty() {
                completed.push(line);
            }
        }
        completed
    };

    for line in lines {
        match serde_json::from_str::<Value>(&line) {
            Ok(message) => route_backend_message(app, inner, message).await,
            Err(error) => {
                let _ = app.emit(
                    "rachel-runtime-event",
                    json!({
                        "kind": "diagnostic",
                        "level": "error",
                        "message": format!("JSON invalido do backend residente: {error}"),
                    }),
                );
            }
        }
    }
}

async fn route_backend_message(
    app: &AppHandle,
    inner: &Arc<BackendInner>,
    mut message: Value,
) {
    let kind = message
        .get("kind")
        .and_then(Value::as_str)
        .unwrap_or("response");

    if kind == "event" {
        let _ = app.emit("rachel-runtime-event", message);
        return;
    }
    if kind != "response" {
        let _ = app.emit("rachel-runtime-event", message);
        return;
    }

    let request_id = match message
        .get("request_id")
        .and_then(Value::as_str)
        .map(str::to_owned)
    {
        Some(value) => value,
        None => return,
    };

    let sender = inner
        .pending
        .lock()
        .ok()
        .and_then(|mut pending| pending.remove(&request_id));
    let Some(sender) = sender else {
        return;
    };

    let ok = message.get("ok").and_then(Value::as_bool) == Some(true);
    let result = if ok {
        let metrics = message.get("metrics").cloned();
        let mut payload = message
            .get_mut("payload")
            .map(Value::take)
            .unwrap_or(Value::Null);
        if let (Some(object), Some(metrics)) = (payload.as_object_mut(), metrics) {
            object.insert("runtime_metrics".to_string(), metrics);
        }
        Ok(payload)
    } else {
        let error = message
            .get("error")
            .and_then(|value| value.get("message"))
            .and_then(Value::as_str)
            .unwrap_or("Falha desconhecida do backend residente")
            .to_string();
        Err(error)
    };

    let _ = sender.send(result).await;
}

fn data_root(app: &AppHandle) -> Result<PathBuf, String> {
    let root = app
        .path()
        .app_local_data_dir()
        .map_err(|error| format!("Falha resolvendo AppLocalData: {error}"))?;
    fs::create_dir_all(&root)
        .map_err(|error| format!("Falha criando AppLocalData: {error}"))?;
    Ok(root)
}

fn state_root(app: &AppHandle) -> Result<PathBuf, String> {
    let state = data_root(app)?.join("STATE");
    fs::create_dir_all(&state)
        .map_err(|error| format!("Falha criando STATE: {error}"))?;
    Ok(state)
}

#[tauri::command]
async fn rachel_dashboard(
    app: AppHandle,
    backend: State<'_, BackendHost>,
) -> Result<Value, String> {
    backend.request(&app, json!({ "action": "dashboard" })).await
}

#[tauri::command]
async fn rachel_status(
    app: AppHandle,
    backend: State<'_, BackendHost>,
) -> Result<Value, String> {
    backend.request(&app, json!({ "action": "status" })).await
}

#[tauri::command]
async fn rachel_runtime_host_status(
    backend: State<'_, BackendHost>,
) -> Result<Value, String> {
    Ok(backend.snapshot())
}

#[tauri::command]
async fn rachel_chat(
    app: AppHandle,
    backend: State<'_, BackendHost>,
    content: String,
    conversation_id: Option<String>,
) -> Result<Value, String> {
    backend
        .request(
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
    backend: State<'_, BackendHost>,
    resume_store: State<'_, ResumeStore>,
    content: String,
    conversation_id: Option<String>,
    approval_id: Option<String>,
) -> Result<Value, String> {
    let resume_plan = approval_id
        .as_deref()
        .and_then(|id| resume_store.take(id));

    let result = backend
        .request(
            &app,
            json!({
                "action": "assist",
                "content": content,
                "conversation_id": conversation_id,
                "approval_id": approval_id,
                "resume_plan": resume_plan,
            }),
        )
        .await?;

    if approval_id.is_none()
        && result.get("state").and_then(Value::as_str) == Some("approval_required")
    {
        let pending_id = result
            .get("tool_result")
            .and_then(|value| value.get("approval"))
            .and_then(|value| value.get("id"))
            .and_then(Value::as_str);
        let plan = result.get("resume_plan");

        if let (Some(id), Some(plan)) = (pending_id, plan) {
            if plan.is_object() {
                resume_store.remember(id.to_string(), plan.clone());
            }
        }
    }

    Ok(result)
}

#[tauri::command]
async fn rachel_cancel(
    app: AppHandle,
    backend: State<'_, BackendHost>,
) -> Result<Value, String> {
    backend
        .request(&app, json!({ "action": "cancel_all" }))
        .await
}

#[tauri::command]
async fn rachel_security_snapshot(
    app: AppHandle,
    backend: State<'_, BackendHost>,
    limit: Option<i64>,
) -> Result<Value, String> {
    backend
        .request(
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
    backend: State<'_, BackendHost>,
    resume_store: State<'_, ResumeStore>,
    approval_id: String,
    allow: bool,
    confirmation: String,
) -> Result<Value, String> {
    let result = backend
        .request(
            &app,
            json!({
                "action": "security_decide",
                "approval_id": approval_id,
                "allow": allow,
                "confirmation": confirmation,
            }),
        )
        .await?;

    if !allow {
        resume_store.forget(&approval_id);
    }
    Ok(result)
}

#[tauri::command]
async fn rachel_memory_search(
    app: AppHandle,
    backend: State<'_, BackendHost>,
    query: String,
    limit: Option<i64>,
) -> Result<Value, String> {
    backend
        .request(
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
    backend: State<'_, BackendHost>,
    include_hardware: Option<bool>,
) -> Result<Value, String> {
    backend
        .request(
            &app,
            json!({
                "action": "voice_status",
                "include_hardware": include_hardware.unwrap_or(true),
            }),
        )
        .await
}

#[tauri::command]
async fn rachel_health(
    app: AppHandle,
    backend: State<'_, BackendHost>,
) -> Result<Value, String> {
    backend.request(&app, json!({ "action": "health" })).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(ResumeStore::default())
        .manage(BackendHost::default())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();
            let backend = app.state::<BackendHost>().inner().clone();
            async_runtime::spawn(async move {
                if let Err(error) = backend.ensure_started(&handle).await {
                    let _ = handle.emit(
                        "rachel-runtime-event",
                        json!({
                            "kind": "runtime.start_failed",
                            "message": error,
                        }),
                    );
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            rachel_dashboard,
            rachel_status,
            rachel_runtime_host_status,
            rachel_chat,
            rachel_assist,
            rachel_cancel,
            rachel_security_snapshot,
            rachel_security_decide,
            rachel_memory_search,
            rachel_voice_status,
            rachel_health
        ])
        .run(tauri::generate_context!())
        .expect("error while running RACHEL IA");
}
