import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  FormEvent,
} from "react";

import {
  invoke,
} from "@tauri-apps/api/core";

import "./App.css";


type View =
  | "overview"
  | "chat"
  | "cyber"
  | "memory"
  | "voice"
  | "system";


type RuntimeStatus = {
  status?: string;
  provider?: string;
  model?: string;
  member?: string;
  tool_count?: number;
};


type MemoryStatus = {
  available?: boolean;
  total?: number;
  active?: number;
  schema_version?: string;
  explicit_consent?: boolean;
  sensitive_data?: string;
};


type MemoryItem = {
  id?: string;
  content?: string;
  category?: string;
  relevance?: number;
  importance?: number;
  confidence?: number;
};


type VoiceStatus = {
  available?: boolean;
  checks?: Record<string, boolean>;
  input_devices?: Array<{
    id?: number;
    name?: string;
    input_channels?: number;
  }>;
  hardware_error?: string | null;
  configuration?: {
    voice?: string;
    stt_model?: string;
    capture_threshold?: number;
    barge_threshold?: number;
  };
  sessions?: {
    stored_sessions?: number;
    total_turns?: number;
    total_interruptions?: number;
  };
};


type Organ = {
  organ_id?: string;
  status?: string;
  detail?: string;
};


type Health = {
  total?: number;
  available?: number;
  failed?: number;
  items?: Organ[];
};


type Approval = {
  id: string;
  tool?: string;
  effect?: string;
  risk?: string;
  risk_label?: string;
  warning?: string;
  status?: string;
  seconds_remaining?: number;
  argument_fields?: Array<{
    name?: string;
    type?: string;
    length?: number;
  }>;
  confirmation?: {
    approve?: string;
    deny?: string;
  };
};


type SecuritySnapshot = {
  total?: number;
  risk_counts?: Record<string, number>;
  items?: Approval[];
};


type Dashboard = {
  runtime?: RuntimeStatus;
  cyber?: SecuritySnapshot;
  memory?: MemoryStatus;
  voice?: VoiceStatus;
  health?: Health;
};


type AssistResponse = {
  state?: string;
  conversation_id?: string;
  message?: {
    content?: string;
  };
  tool_result?: {
    state?: string;
    approval?: {
      id?: string;
    };
  } | null;
};


type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
};


type PendingAction = {
  content: string;
  approvalId: string;
};


type ConfirmState = {
  card: Approval;
  allow: boolean;
};


const nav: Array<{
  id: View;
  label: string;
  glyph: string;
}> = [
  {
    id: "overview",
    label: "Visão geral",
    glyph: "◈",
  },
  {
    id: "chat",
    label: "Rachel",
    glyph: "◇",
  },
  {
    id: "cyber",
    label: "Cyber",
    glyph: "⬡",
  },
  {
    id: "memory",
    label: "Bran",
    glyph: "◎",
  },
  {
    id: "voice",
    label: "Stella",
    glyph: "◖",
  },
  {
    id: "system",
    label: "Tyrion",
    glyph: "▦",
  },
];


function App() {

  const [
    view,
    setView,
  ] = useState<View>(
    "overview"
  );

  const [
    dashboard,
    setDashboard,
  ] = useState<Dashboard | null>(
    null
  );

  const [, setLoadingDashboard] = useState(true);

  const [
    offline,
    setOffline,
  ] = useState(false);

  const [
    conversationId,
    setConversationId,
  ] = useState<string | null>(
    null
  );

  const [
    messages,
    setMessages,
  ] = useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      content:
        "Sistema desktop operacional. Ned, Cyber, Bran, Stella e Tyrion estão conectados ao runtime local.",
    },
  ]);

  const [
    input,
    setInput,
  ] = useState("");

  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    pendingAction,
    setPendingAction,
  ] = useState<PendingAction | null>(
    null
  );

  const [
    cyber,
    setCyber,
  ] = useState<SecuritySnapshot>({
    total: 0,
    items: [],
  });

  const [
    confirmState,
    setConfirmState,
  ] = useState<ConfirmState | null>(
    null
  );

  const [
    confirmation,
    setConfirmation,
  ] = useState("");

  const [
    decisionBusy,
    setDecisionBusy,
  ] = useState(false);

  const [
    memoryQuery,
    setMemoryQuery,
  ] = useState("");

  const [
    memories,
    setMemories,
  ] = useState<MemoryItem[]>([]);

  const [
    memoryBusy,
    setMemoryBusy,
  ] = useState(false);

  const [
    voice,
    setVoice,
  ] = useState<VoiceStatus | null>(
    null
  );

  const [
    voiceBusy,
    setVoiceBusy,
  ] = useState(false);

  const [
    health,
    setHealth,
  ] = useState<Health | null>(
    null
  );

  const nextId =
    useRef(2);


  async function loadDashboard() {
    setLoadingDashboard(true);

    try {
      const result =
        await invoke<Dashboard>(
          "rachel_dashboard"
        );

      setDashboard(result);
      setCyber(
        result.cyber ?? {
          total: 0,
          items: [],
        }
      );
      setVoice(
        result.voice ?? null
      );
      setHealth(
        result.health ?? null
      );
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoadingDashboard(false);
    }
  }


  async function refreshCyber() {
    const result =
      await invoke<SecuritySnapshot>(
        "rachel_security_snapshot",
        {
          limit: 50,
        }
      );

    setCyber(result);
  }


  async function refreshHealth() {
    const result =
      await invoke<Health>(
        "rachel_health"
      );

    setHealth(result);
  }


  async function refreshVoice() {
    setVoiceBusy(true);

    try {
      const result =
        await invoke<VoiceStatus>(
          "rachel_voice_status",
          {
            includeHardware: true,
          }
        );

      setVoice(result);
    } finally {
      setVoiceBusy(false);
    }
  }


  useEffect(() => {
    void loadDashboard();
  }, []);


  function addAssistant(
    content: string,
  ) {
    setMessages(
      current => [
        ...current,
        {
          id: nextId.current++,
          role: "assistant",
          content,
        },
      ]
    );
  }


  async function processAssist(
    content: string,
    approvalId: string | null,
  ) {
    const result =
      await invoke<AssistResponse>(
        "rachel_assist",
        {
          content,
          conversationId,
          approvalId,
        }
      );

    if(
      typeof result.conversation_id
      === "string"
    ){
      setConversationId(
        result.conversation_id
      );
    }

    addAssistant(
      result.message?.content ??
      "A RACHEL concluiu sem retornar texto."
    );

    const requestedApproval =
      result.tool_result
        ?.approval
        ?.id;

    if(
      result.state === "approval_required"
      && typeof requestedApproval === "string"
    ){
      setPendingAction({
        content,
        approvalId: requestedApproval,
      });

      await refreshCyber();

      setView("cyber");
    }

    return result;
  }


  async function send(
    event: FormEvent,
  ) {
    event.preventDefault();

    const content =
      input.trim();

    if(
      !content
      || busy
    ){
      return;
    }

    setMessages(
      current => [
        ...current,
        {
          id: nextId.current++,
          role: "user",
          content,
        },
      ]
    );

    setInput("");
    setBusy(true);

    try {
      await processAssist(
        content,
        null
      );
    } catch(error) {
      addAssistant(
        `Falha no runtime local: ${String(error)}`
      );
    } finally {
      setBusy(false);
    }
  }


  async function executeApproved(
    pending: PendingAction,
  ) {
    setBusy(true);
    setView("chat");

    try {
      await processAssist(
        pending.content,
        pending.approvalId,
      );

      setPendingAction(null);

      await refreshCyber();
    } catch(error) {
      addAssistant(
        `Falha ao consumir autorização: ${String(error)}`
      );
    } finally {
      setBusy(false);
    }
  }


  function openDecision(
    card: Approval,
    allow: boolean,
  ) {
    setConfirmState({
      card,
      allow,
    });

    setConfirmation("");
  }


  async function decideCyber() {
    if(
      !confirmState
      || decisionBusy
    ){
      return;
    }

    const expected =
      confirmState.allow
        ? confirmState.card
            .confirmation
            ?.approve
        : confirmState.card
            .confirmation
            ?.deny;

    if(
      !expected
      || confirmation !== expected
    ){
      return;
    }

    setDecisionBusy(true);

    try {
      await invoke(
        "rachel_security_decide",
        {
          approvalId:
            confirmState.card.id,
          allow:
            confirmState.allow,
          confirmation,
        }
      );

      const matchingPending =
        pendingAction
        && pendingAction.approvalId
          === confirmState.card.id
          ? pendingAction
          : null;

      const allowed =
        confirmState.allow;

      setConfirmState(null);
      setConfirmation("");

      await refreshCyber();

      if(
        allowed
        && matchingPending
      ){
        await executeApproved(
          matchingPending
        );
      } else if(
        !allowed
        && matchingPending
      ){
        setPendingAction(null);

        addAssistant(
          "A ação foi negada pelo Cyber e não foi executada."
        );

        setView("chat");
      }
    } finally {
      setDecisionBusy(false);
    }
  }


  async function searchMemory(
    event: FormEvent,
  ) {
    event.preventDefault();

    const query =
      memoryQuery.trim();

    if(!query){
      return;
    }

    setMemoryBusy(true);

    try {
      const result =
        await invoke<{
          items?: MemoryItem[];
        }>(
          "rachel_memory_search",
          {
            query,
            limit: 20,
          }
        );

      setMemories(
        result.items ?? []
      );
    } finally {
      setMemoryBusy(false);
    }
  }


  const runtime =
    dashboard?.runtime;

  const memoryStatus =
    dashboard?.memory;

  const organsAvailable =
    health?.available
    ?? dashboard?.health?.available
    ?? 0;

  const organsTotal =
    health?.total
    ?? dashboard?.health?.total
    ?? 0;

  const pendingTotal =
    cyber.total ?? 0;


  return (
    <main className="app">

      <aside className="rail">

        <div className="brand">

          <div className="brand-core">
            <span>R</span>
          </div>

          <div>
            <strong>
              RACHEL
            </strong>

            <small>
              LOCAL INTELLIGENCE
            </small>
          </div>

        </div>


        <nav>

          {
            nav.map(
              item => (
                <button
                  key={item.id}
                  className={
                    view === item.id
                      ? "nav-item active"
                      : "nav-item"
                  }
                  onClick={
                    () => setView(
                      item.id
                    )
                  }
                >
                  <i>
                    {item.glyph}
                  </i>

                  <span>
                    {item.label}
                  </span>

                  {
                    item.id === "cyber"
                    && pendingTotal > 0
                    && (
                      <b>
                        {pendingTotal}
                      </b>
                    )
                  }
                </button>
              )
            )
          }

        </nav>


        <div className="rail-status">

          <div>
            <span
              className={
                offline
                  ? "live-dot bad"
                  : "live-dot"
              }
            />

            <strong>
              {
                offline
                  ? "CORE OFFLINE"
                  : "CORE ONLINE"
              }
            </strong>
          </div>

          <small>
            {
              organsTotal
                ? `${organsAvailable}/${organsTotal} órgãos`
                : "verificando órgãos"
            }
          </small>

        </div>

      </aside>


      <section className="workspace">

        <header className="topbar">

          <div>
            <p>
              RACHEL / DESKTOP
            </p>

            <h1>
              {
                nav.find(
                  item => item.id === view
                )?.label
              }
            </h1>
          </div>

          <div className="top-pills">

            <span className="pill cyber">
              CYBER GOVERNED
            </span>

            <span className="pill">
              {
                runtime?.provider
                ?? "LOCAL"
              }
            </span>

          </div>

        </header>


        <div className="content">

          {
            view === "overview"
            && (
              <section className="overview">

                <div className="hero">

                  <div className="hero-copy">

                    <span className="section-label">
                      SISTEMA OPERACIONAL
                    </span>

                    <h2>
                      Sua inteligência local,
                      <br />
                      viva e observável.
                    </h2>

                    <p>
                      Rachel coordena cognição,
                      ferramentas, memória,
                      segurança, voz e saúde do
                      sistema a partir de uma
                      única interface.
                    </p>

                    <div className="hero-actions">

                      <button
                        className="primary"
                        onClick={
                          () => setView(
                            "chat"
                          )
                        }
                      >
                        Conversar com Rachel
                      </button>

                      <button
                        className="ghost"
                        onClick={
                          () => void loadDashboard()
                        }
                      >
                        Atualizar sistema
                      </button>

                    </div>

                  </div>


                  <div className="core-stage">

                    <div className="core-orbit orbit-one" />
                    <div className="core-orbit orbit-two" />
                    <div className="core-orbit orbit-three" />

                    <div className="energy-core">
                      <div className="energy-inner">
                        R
                      </div>
                    </div>

                    <span className="particle p1" />
                    <span className="particle p2" />
                    <span className="particle p3" />
                    <span className="particle p4" />

                    <div className="core-caption">
                      <strong>
                        {
                          offline
                            ? "OFFLINE"
                            : "OPERATIONAL"
                        }
                      </strong>

                      <span>
                        RACHEL CORE
                      </span>
                    </div>

                  </div>

                </div>


                <div className="metric-grid">

                  <article className="metric-card">
                    <span>
                      ÓRGÃOS
                    </span>

                    <strong>
                      {organsAvailable}
                      <em>
                        /{organsTotal}
                      </em>
                    </strong>

                    <small>
                      Tyrion health
                    </small>
                  </article>

                  <article className="metric-card">
                    <span>
                      FERRAMENTAS
                    </span>

                    <strong>
                      {
                        runtime?.tool_count
                        ?? "—"
                      }
                    </strong>

                    <small>
                      Ned registry
                    </small>
                  </article>

                  <article className="metric-card">
                    <span>
                      MEMÓRIAS
                    </span>

                    <strong>
                      {
                        memoryStatus?.active
                        ?? "—"
                      }
                    </strong>

                    <small>
                      Bran active
                    </small>
                  </article>

                  <article className="metric-card alert-card">
                    <span>
                      APROVAÇÕES
                    </span>

                    <strong>
                      {pendingTotal}
                    </strong>

                    <small>
                      Cyber pending
                    </small>
                  </article>

                </div>


                <div className="overview-grid">

                  <article className="panel">

                    <div className="panel-head">

                      <div>
                        <span className="section-label">
                          COGNIÇÃO
                        </span>

                        <h3>
                          Ned Runtime
                        </h3>
                      </div>

                      <span className="state-badge ok">
                        ONLINE
                      </span>

                    </div>

                    <dl className="details">

                      <div>
                        <dt>
                          Membro
                        </dt>
                        <dd>
                          {runtime?.member ?? "ned"}
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Provider
                        </dt>
                        <dd>
                          {runtime?.provider ?? "—"}
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Modelo
                        </dt>
                        <dd>
                          {runtime?.model ?? "—"}
                        </dd>
                      </div>

                    </dl>

                  </article>


                  <article className="panel">

                    <div className="panel-head">

                      <div>
                        <span className="section-label">
                          SEGURANÇA
                        </span>

                        <h3>
                          Cyber
                        </h3>
                      </div>

                      <span
                        className={
                          pendingTotal
                            ? "state-badge warn"
                            : "state-badge ok"
                        }
                      >
                        {
                          pendingTotal
                            ? `${pendingTotal} PENDENTE`
                            : "SEGURO"
                        }
                      </span>

                    </div>

                    <p className="panel-text">
                      Autorizações são vinculadas
                      à ferramenta, efeito e
                      argumentos exatos, com
                      consumo único.
                    </p>

                    <button
                      className="text-button"
                      onClick={
                        () => setView(
                          "cyber"
                        )
                      }
                    >
                      Abrir painel de riscos →
                    </button>

                  </article>

                </div>

              </section>
            )
          }


          {
            view === "chat"
            && (
              <section className="chat-view">

                <div className="chat-head">

                  <div>
                    <span className="section-label">
                      NED / COGNITIVE ROUTER
                    </span>

                    <h2>
                      Rachel
                    </h2>
                  </div>

                  <span className="state-badge ok">
                    LOCAL
                  </span>

                </div>


                <div className="messages">

                  {
                    messages.map(
                      message => (
                        <article
                          key={message.id}
                          className={
                            `message ${message.role}`
                          }
                        >
                          <small>
                            {
                              message.role === "user"
                                ? "VOCÊ"
                                : "RACHEL"
                            }
                          </small>

                          <p>
                            {message.content}
                          </p>
                        </article>
                      )
                    )
                  }

                  {
                    busy
                    && (
                      <article className="message assistant thinking">
                        <small>
                          RACHEL
                        </small>

                        <p>
                          Processando no runtime local…
                        </p>
                      </article>
                    )
                  }

                </div>


                {
                  pendingAction
                  && (
                    <div className="approval-inline">

                      <div>
                        <span>
                          AUTORIZAÇÃO NECESSÁRIA
                        </span>

                        <strong>
                          Cyber bloqueou uma ação
                          até sua confirmação.
                        </strong>
                      </div>

                      <button
                        onClick={
                          () => setView(
                            "cyber"
                          )
                        }
                      >
                        Revisar
                      </button>

                    </div>
                  )
                }


                <form
                  className="composer"
                  onSubmit={send}
                >

                  <textarea
                    value={input}
                    onChange={
                      event => setInput(
                        event.target.value
                      )
                    }
                    placeholder="Converse, peça uma análise ou solicite uma ação..."
                    maxLength={50000}
                  />

                  <footer>

                    <span>
                      {
                        conversationId
                          ? "CONTEXTO PERSISTENTE"
                          : "NOVA CONVERSA"
                      }
                    </span>

                    <button
                      disabled={
                        busy
                        || !input.trim()
                      }
                    >
                      {
                        busy
                          ? "Processando"
                          : "Enviar"
                      }
                    </button>

                  </footer>

                </form>

              </section>
            )
          }


          {
            view === "cyber"
            && (
              <section>

                <div className="section-header">

                  <div>
                    <span className="section-label">
                      CYBER / AUTHORITY
                    </span>

                    <h2>
                      Painel de riscos
                    </h2>

                    <p>
                      Nenhum valor de argumento
                      sensível é exibido.
                    </p>
                  </div>

                  <button
                    className="ghost"
                    onClick={
                      () => void refreshCyber()
                    }
                  >
                    Atualizar
                  </button>

                </div>


                <div className="approval-list">

                  {
                    !cyber.items?.length
                    && (
                      <div className="empty-state">
                        <div>
                          ✓
                        </div>

                        <h3>
                          Nenhuma autorização pendente
                        </h3>

                        <p>
                          O Cyber não está aguardando
                          nenhuma decisão.
                        </p>
                      </div>
                    )
                  }


                  {
                    cyber.items?.map(
                      card => (
                        <article
                          className={
                            `approval-card risk-${card.risk ?? "unknown"}`
                          }
                          key={card.id}
                        >

                          <div className="approval-top">

                            <div>

                              <span
                                className={
                                  `risk-chip ${card.risk ?? ""}`
                                }
                              >
                                {
                                  card.risk_label
                                  ?? card.risk
                                  ?? "UNKNOWN"
                                }
                              </span>

                              <h3>
                                {card.tool}
                              </h3>

                              <p>
                                {card.warning}
                              </p>

                            </div>

                            <strong className="countdown">
                              {
                                card.seconds_remaining
                                ?? 0
                              }s
                            </strong>

                          </div>


                          <div className="approval-meta">

                            <span>
                              EFEITO
                              <strong>
                                {card.effect}
                              </strong>
                            </span>

                            <span>
                              CAMPOS
                              <strong>
                                {
                                  card.argument_fields
                                    ?.map(
                                      field =>
                                        field.name
                                    )
                                    .join(", ")
                                  || "nenhum"
                                }
                              </strong>
                            </span>

                          </div>


                          <div className="approval-actions">

                            <button
                              className="deny"
                              onClick={
                                () => openDecision(
                                  card,
                                  false
                                )
                              }
                            >
                              Negar
                            </button>

                            <button
                              className="approve"
                              onClick={
                                () => openDecision(
                                  card,
                                  true
                                )
                              }
                            >
                              Aprovar
                            </button>

                          </div>

                        </article>
                      )
                    )
                  }

                </div>

              </section>
            )
          }


          {
            view === "memory"
            && (
              <section>

                <div className="section-header">

                  <div>
                    <span className="section-label">
                      BRAN / MEMORY
                    </span>

                    <h2>
                      Memória governada
                    </h2>

                    <p>
                      Persistência com
                      consentimento explícito.
                    </p>
                  </div>

                  <span className="state-badge ok">
                    {
                      memoryStatus?.active
                      ?? 0
                    } ATIVAS
                  </span>

                </div>


                <div className="memory-stat-grid">

                  <article>
                    <span>
                      ATIVAS
                    </span>
                    <strong>
                      {
                        memoryStatus?.active
                        ?? 0
                      }
                    </strong>
                  </article>

                  <article>
                    <span>
                      TOTAL
                    </span>
                    <strong>
                      {
                        memoryStatus?.total
                        ?? 0
                      }
                    </strong>
                  </article>

                  <article>
                    <span>
                      CONSENTIMENTO
                    </span>
                    <strong>
                      EXPLÍCITO
                    </strong>
                  </article>

                </div>


                <form
                  className="memory-search"
                  onSubmit={searchMemory}
                >

                  <input
                    value={memoryQuery}
                    onChange={
                      event =>
                        setMemoryQuery(
                          event.target.value
                        )
                    }
                    placeholder="Pesquisar nas memórias da Rachel..."
                  />

                  <button
                    disabled={
                      memoryBusy
                      || !memoryQuery.trim()
                    }
                  >
                    {
                      memoryBusy
                        ? "Buscando"
                        : "Pesquisar"
                    }
                  </button>

                </form>


                <div className="memory-results">

                  {
                    memories.map(
                      item => (
                        <article
                          key={item.id}
                          className="memory-card"
                        >
                          <div>
                            <span>
                              {
                                item.category
                                ?? "MEMORY"
                              }
                            </span>

                            <strong>
                              {
                                item.relevance
                                ?.toFixed(2)
                                ?? "—"
                              }
                            </strong>
                          </div>

                          <p>
                            {item.content}
                          </p>
                        </article>
                      )
                    )
                  }

                </div>

              </section>
            )
          }


          {
            view === "voice"
            && (
              <section>

                <div className="section-header">

                  <div>
                    <span className="section-label">
                      STELLA / VOICE
                    </span>

                    <h2>
                      Voz em tempo real
                    </h2>

                    <p>
                      Diagnóstico local de
                      captura, STT, TTS e barge-in.
                    </p>
                  </div>

                  <button
                    className="ghost"
                    disabled={voiceBusy}
                    onClick={
                      () => void refreshVoice()
                    }
                  >
                    {
                      voiceBusy
                        ? "Verificando..."
                        : "Detectar hardware"
                    }
                  </button>

                </div>


                <div className="voice-grid">

                  <article className="panel">

                    <div className="voice-orb">
                      <span />
                      <i />
                    </div>

                    <h3>
                      {
                        voice?.available
                          ? "Stella disponível"
                          : "Diagnóstico parcial"
                      }
                    </h3>

                    <p className="panel-text">
                      {
                        voice?.configuration
                          ?.voice
                        ?? "Voz não informada"
                      }
                    </p>

                  </article>


                  <article className="panel">

                    <span className="section-label">
                      CONFIGURAÇÃO
                    </span>

                    <dl className="details">

                      <div>
                        <dt>
                          STT
                        </dt>
                        <dd>
                          {
                            voice?.configuration
                              ?.stt_model
                            ?? "—"
                          }
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Sessões
                        </dt>
                        <dd>
                          {
                            voice?.sessions
                              ?.stored_sessions
                            ?? 0
                          }
                        </dd>
                      </div>

                      <div>
                        <dt>
                          Interrupções
                        </dt>
                        <dd>
                          {
                            voice?.sessions
                              ?.total_interruptions
                            ?? 0
                          }
                        </dd>
                      </div>

                    </dl>

                  </article>

                </div>


                <div className="device-list">

                  {
                    voice?.input_devices
                      ?.map(
                        device => (
                          <article
                            key={device.id}
                          >
                            <span className="live-dot" />

                            <div>
                              <strong>
                                {device.name}
                              </strong>

                              <small>
                                {
                                  device.input_channels
                                  ?? 0
                                } canais de entrada
                              </small>
                            </div>
                          </article>
                        )
                      )
                  }

                </div>

              </section>
            )
          }


          {
            view === "system"
            && (
              <section>

                <div className="section-header">

                  <div>
                    <span className="section-label">
                      TYRION / INFRA
                    </span>

                    <h2>
                      Saúde dos órgãos
                    </h2>

                    <p>
                      Supervisão das fontes e
                      manifestos da Rachel.
                    </p>
                  </div>

                  <button
                    className="ghost"
                    onClick={
                      () => void refreshHealth()
                    }
                  >
                    Revalidar
                  </button>

                </div>


                <div className="system-summary">

                  <article>
                    <span>
                      TOTAL
                    </span>
                    <strong>
                      {health?.total ?? 0}
                    </strong>
                  </article>

                  <article>
                    <span>
                      DISPONÍVEIS
                    </span>
                    <strong>
                      {health?.available ?? 0}
                    </strong>
                  </article>

                  <article>
                    <span>
                      FALHAS
                    </span>
                    <strong>
                      {health?.failed ?? 0}
                    </strong>
                  </article>

                </div>


                <div className="organ-grid">

                  {
                    health?.items
                      ?.map(
                        organ => (
                          <article
                            key={organ.organ_id}
                            className="organ-card"
                          >
                            <span
                              className={
                                organ.status === "available"
                                  ? "organ-dot"
                                  : "organ-dot bad"
                              }
                            />

                            <div>
                              <strong>
                                {organ.organ_id}
                              </strong>

                              <small>
                                {
                                  organ.status
                                  ?? "unknown"
                                }
                              </small>
                            </div>
                          </article>
                        )
                      )
                  }

                </div>

              </section>
            )
          }

        </div>

      </section>


      {
        confirmState
        && (
          <div className="modal-backdrop">

            <div className="confirm-modal">

              <span className="section-label">
                CYBER / CONFIRMAÇÃO EXPLÍCITA
              </span>

              <h2>
                {
                  confirmState.allow
                    ? "Autorizar execução"
                    : "Negar solicitação"
                }
              </h2>

              <p>
                Digite exatamente a frase abaixo
                para confirmar sua decisão.
              </p>

              <code>
                {
                  confirmState.allow
                    ? confirmState.card
                        .confirmation
                        ?.approve
                    : confirmState.card
                        .confirmation
                        ?.deny
                }
              </code>

              <input
                autoFocus
                value={confirmation}
                onChange={
                  event =>
                    setConfirmation(
                      event.target.value
                    )
                }
                placeholder="Digite a confirmação..."
              />

              <div className="modal-actions">

                <button
                  className="ghost"
                  onClick={
                    () => {
                      setConfirmState(null);
                      setConfirmation("");
                    }
                  }
                >
                  Cancelar
                </button>

                <button
                  className={
                    confirmState.allow
                      ? "approve"
                      : "deny"
                  }
                  disabled={
                    decisionBusy
                    || confirmation !== (
                      confirmState.allow
                        ? confirmState.card
                            .confirmation
                            ?.approve
                        : confirmState.card
                            .confirmation
                            ?.deny
                    )
                  }
                  onClick={
                    () => void decideCyber()
                  }
                >
                  {
                    decisionBusy
                      ? "Aplicando..."
                      : confirmState.allow
                        ? "Aprovar e executar"
                        : "Negar"
                  }
                </button>

              </div>

            </div>

          </div>
        )
      }

    </main>
  );
}


export default App;
