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


type Status = {
  provider?: string;
  model?: string;
  member?: string;
  tool_count?: number;
};


type Response = {
  conversation_id?: string;
  message?: {
    content?: string;
  };
};


type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
};


function App() {
  const [status, setStatus] =
    useState<Status | null>(null);

  const [offline, setOffline] =
    useState(false);

  const [conversationId, setConversationId] =
    useState<string | null>(null);

  const [input, setInput] =
    useState("");

  const [busy, setBusy] =
    useState(false);

  const [messages, setMessages] =
    useState<Message[]>([
      {
        id: 1,
        role: "assistant",
        content:
          "RACHEL Desktop inicializada. Bridge local conectado.",
      },
    ]);

  const nextId = useRef(2);


  async function refreshStatus() {
    try {
      const result =
        await invoke<Status>(
          "rachel_status"
        );

      setStatus(result);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }


  useEffect(() => {
    void refreshStatus();
  }, []);


  async function send(
    event: FormEvent,
  ) {
    event.preventDefault();

    const content =
      input.trim();

    if(!content || busy){
      return;
    }

    setMessages(current => [
      ...current,
      {
        id: nextId.current++,
        role: "user",
        content,
      },
    ]);

    setInput("");
    setBusy(true);

    try {
      const result =
        await invoke<Response>(
          "rachel_chat",
          {
            content,
            conversationId,
          },
        );

      if(result.conversation_id){
        setConversationId(
          result.conversation_id
        );
      }

      setMessages(current => [
        ...current,
        {
          id: nextId.current++,
          role: "assistant",
          content:
            result.message?.content ??
            "Resposta sem texto.",
        },
      ]);
    } catch(error) {
      setMessages(current => [
        ...current,
        {
          id: nextId.current++,
          role: "assistant",
          content:
            `Falha no bridge: ${String(error)}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }


  return (
    <main className="shell">

      <aside>

        <div className="logo">
          R
        </div>

        <span className="eyebrow">
          RACHEL IA
        </span>

        <h1>
          Desktop Runtime
        </h1>

        <div className="state">
          <i className={offline ? "bad" : ""} />
          {
            offline
              ? "Backend offline"
              : status
                ? "Backend conectado"
                : "Conectando"
          }
        </div>

        <dl>
          <dt>MEMBRO</dt>
          <dd>{status?.member ?? "—"}</dd>

          <dt>PROVIDER</dt>
          <dd>{status?.provider ?? "—"}</dd>

          <dt>MODELO</dt>
          <dd>{status?.model ?? "—"}</dd>

          <dt>TOOLS</dt>
          <dd>{status?.tool_count ?? "—"}</dd>
        </dl>

        <button
          className="refresh"
          onClick={() => void refreshStatus()}
        >
          Atualizar status
        </button>

      </aside>


      <section className="chat">

        <header>
          <div>
            <span>NED / LOCAL BRIDGE</span>
            <h2>Conversa com RACHEL</h2>
          </div>

          <strong>
            CYBER GOVERNED
          </strong>
        </header>


        <div className="messages">

          {messages.map(message => (
            <article
              key={message.id}
              className={message.role}
            >
              <small>
                {
                  message.role === "user"
                    ? "VOCÊ"
                    : "RACHEL"
                }
              </small>

              <p>{message.content}</p>
            </article>
          ))}

          {busy && (
            <article className="assistant">
              <small>RACHEL</small>
              <p>Processando localmente...</p>
            </article>
          )}

        </div>


        <form onSubmit={send}>

          <textarea
            value={input}
            onChange={
              event => setInput(
                event.target.value
              )
            }
            placeholder="Fale com a RACHEL..."
            maxLength={50000}
          />

          <footer>
            <span>
              {
                conversationId
                  ? "CONVERSA PERSISTENTE"
                  : "NOVA CONVERSA"
              }
            </span>

            <button
              disabled={
                busy ||
                !input.trim()
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

    </main>
  );
}


export default App;
