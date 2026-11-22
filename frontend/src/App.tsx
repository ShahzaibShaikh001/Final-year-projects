import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { sendChat } from "./api";
import type { ChatMessage, Conversation, Paper } from "./types";

const YEARS = ["Any year", "2026", "2025", "2024", "2023", "2022", "2021", "2020"];
const COUNTS = Array.from({ length: 20 }, (_, i) => i + 1);

const EXAMPLES = [
  "Latest open-access papers on medical imaging",
  "Deep learning for ECG classification",
  "Transformer models in radiology 2024",
  "IEEE Access papers on lung CT segmentation",
];

function uid() {
  return crypto.randomUUID();
}

function newConversation(): Conversation {
  return { id: uid(), title: "New conversation", messages: [], selectedPaper: null };
}

function BrainIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9.5 4.5c-1.8 0-3.2 1.3-3.5 3C4.8 8 4 9.2 4 10.6c0 1 .4 1.9 1.1 2.5-.3.5-.5 1.1-.5 1.7 0 1.7 1.3 3.1 3 3.4.5 1.4 1.8 2.3 3.3 2.3.8 0 1.5-.2 2.1-.6.6.4 1.3.6 2.1.6 1.5 0 2.8-.9 3.3-2.3 1.7-.3 3-1.7 3-3.4 0-.6-.2-1.2-.5-1.7.7-.6 1.1-1.5 1.1-2.5 0-1.4-.8-2.6-2-3.1-.3-1.7-1.7-3-3.5-3-1 0-1.9.4-2.5 1-.6-.6-1.5-1-2.5-1Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M12 7.5v9.5M9 10h0M15 10h0M9 13h0M15 13h0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M12 5l-6 6M12 5l6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([newConversation()]);
  const [activeId, setActiveId] = useState(conversations[0].id);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [brainOpen, setBrainOpen] = useState(false);
  const [year, setYear] = useState("Any year");
  const [count, setCount] = useState(2);
  const bottomRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? conversations[0],
    [conversations, activeId]
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [active?.messages, busy]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!popRef.current) return;
      if (!popRef.current.contains(e.target as Node)) setBrainOpen(false);
    }
    if (brainOpen) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [brainOpen]);

  function patchActive(updater: (c: Conversation) => Conversation) {
    setConversations((prev) => prev.map((c) => (c.id === active.id ? updater(c) : c)));
  }

  function startNewChat() {
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    setInput("");
    setBrainOpen(false);
  }

  function clearAll() {
    const c = newConversation();
    setConversations([c]);
    setActiveId(c.id);
  }

  async function submit(text: string) {
    const message = text.trim();
    if (!message || busy) return;

    const userMsg: ChatMessage = { id: uid(), role: "user", content: message };
    patchActive((c) => ({
      ...c,
      title: c.title === "New conversation" ? message.slice(0, 42) : c.title,
      messages: [...c.messages, userMsg],
    }));
    setInput("");
    setBusy(true);
    setBrainOpen(false);

    try {
      const yearVal = year === "Any year" ? null : Number(year);
      const history = active.messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const data = await sendChat({
        message,
        year: yearVal,
        count,
        selected_paper: active.selectedPaper,
        history,
      });

      if (data.year) setYear(String(data.year));
      if (data.count) setCount(Number(data.count));

      const assistantMsg: ChatMessage = {
        id: uid(),
        role: "assistant",
        content: data.reply,
        kind: data.kind,
        topics: data.topics || [],
        papers: data.papers || [],
      };

      patchActive((c) => ({
        ...c,
        selectedPaper: data.kind === "results" ? null : c.selectedPaper,
        messages: [...c.messages, assistantMsg],
      }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      patchActive((c) => ({
        ...c,
        messages: [
          ...c.messages,
          { id: uid(), role: "assistant", content: msg, kind: "error" },
        ],
      }));
    } finally {
      setBusy(false);
    }
  }

  function selectPaper(paper: Paper) {
    patchActive((c) => ({
      ...c,
      selectedPaper: paper,
      messages: [
        ...c.messages,
        {
          id: uid(),
          role: "assistant",
          content: `Selected **${paper.title}** (${paper.source || "source"}${
            paper.year ? `, ${paper.year}` : ""
          })${paper.url || paper.pdf_url ? ` · [Open paper](${paper.url || paper.pdf_url})` : ""}\n\nAsk for a summary, methods, or findings — answers use the public abstract.`,
          kind: "selected",
        },
      ],
    }));
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <h1>
            Researcher<span>.</span>
          </h1>
          <p>Scholar · IEEE Access · Groq</p>
        </div>

        <button className="btn btn-primary" type="button" onClick={startNewChat}>
          +  New chat
        </button>

        <div className="section-head">
          <span>Your conversations</span>
          <button className="linkish" type="button" onClick={clearAll}>
            Clear All
          </button>
        </div>

        <div className="conv-list">
          {conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`btn conv-item ${c.id === active.id ? "active" : ""}`}
              onClick={() => setActiveId(c.id)}
            >
              <span aria-hidden="true">💬</span>
              <span>{c.title}</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="main">
        <div className="chat-scroll">
          <div className="pills">
            <span className="pill">Year · {year}</span>
            <span className="pill">{count} papers</span>
            <span className="pill">Abstract chat</span>
          </div>

          {active.messages.length === 0 ? (
            <div className="hero">
              <h2>What can I help with?</h2>
              <p>
                Search open-access papers on Google Scholar and IEEE Access, then chat
                using the public abstract.
              </p>
              <div className="examples">
                {EXAMPLES.map((ex) => (
                  <button key={ex} type="button" className="btn" onClick={() => submit(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {active.messages.map((m) => (
                <div key={m.id}>
                  <div className="message">
                    <div className={`avatar ${m.role === "user" ? "user" : ""}`}>
                      {m.role === "user" ? "U" : "R"}
                    </div>
                    <div>
                      {m.role === "assistant" && (
                        <div className="assistant-label">Researcher.</div>
                      )}
                      <div className="bubble">
                        <ReactMarkdown>{m.content}</ReactMarkdown>
                      </div>
                    </div>
                  </div>

                  {m.kind === "clarify" && m.topics && m.topics.length > 0 && (
                    <div className="topics">
                      {m.topics.map((t) => (
                        <button key={t} type="button" className="btn" onClick={() => submit(t)}>
                          {t}
                        </button>
                      ))}
                    </div>
                  )}

                  {m.kind === "results" && m.papers && m.papers.length > 0 && (
                    <div className="paper-actions">
                      {m.papers.map((p, idx) => (
                        <button
                          key={`${p.title}-${idx}`}
                          type="button"
                          className="btn"
                          onClick={() => selectPaper(p)}
                        >
                          {idx + 1}. {p.title} · {p.source}
                        </button>
                      ))}
                    </div>
                  )}

                  {m.kind === "selected" && (
                    <div className="quick">
                      {[
                        "Summarize this paper from the abstract.",
                        "What methods does the abstract mention?",
                        "What are the main findings?",
                      ].map((q) => (
                        <button key={q} type="button" className="btn" onClick={() => submit(q)}>
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {busy && <div className="typing">Researcher is working…</div>}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        <div className="composer-wrap" ref={popRef}>
          {brainOpen && (
            <div className="brain-pop" role="dialog" aria-label="Search filters">
              <h4>Search filters</h4>
              <div className="row">
                <label htmlFor="year">Year</label>
                <select
                  id="year"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                >
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </div>
              <div className="row">
                <label htmlFor="count">Number of papers</label>
                <select
                  id="count"
                  value={count}
                  onChange={(e) => setCount(Number(e.target.value))}
                >
                  {COUNTS.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>
              <p className="brain-hint">
                Same controls as the brain icon on the Figma composer — set these before you ask.
              </p>
            </div>
          )}

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(input);
            }}
          >
            <button
              type="button"
              className={`icon-btn ${brainOpen ? "open" : ""}`}
              aria-label="Open search filters"
              title="Year & paper count"
              onClick={() => setBrainOpen((v) => !v)}
            >
              <BrainIcon />
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message Researcher…"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit(input);
                }
              }}
            />
            <button
              type="submit"
              className="send-btn"
              aria-label="Send message"
              disabled={busy || !input.trim()}
            >
              <SendIcon />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
