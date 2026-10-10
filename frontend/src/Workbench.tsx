import React, { useEffect, useRef, useState } from 'react';

import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  FileText,
  FlaskConical,
  GitBranch,
  Headphones,
  Leaf,
  LoaderCircle,
  MessageCircle,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  Upload,
  Volume2,
  X,
} from 'lucide-react';
import './style.css';
import { VoiceConversation } from './VoiceConversation';
import { fetchApi, request, json, zeroGpu } from './api';

type Reference = {
  id: string;
  title: string;
  version: number;
  digest: string;
  source: string;
  passage_count: number;
  created_at: string;
};
type Evidence = { id: string; locator: string; text: string; score?: number };
type Turn = {
  id: string;
  question: string;
  answer: string;
  reason: string;
  disposition: string;
  citations: string[];
  evidence: Evidence[];
  trace: { stage: string; detail: string }[];
  elapsed_ms: number;
  document_version: number;
  document_title: string;
  provider: string;
};
type Review = Turn & { status: string; note: string; created_at: string };
type Row = {
  id: string;
  category: string;
  question: string;
  expected: string;
  baseline: Turn;
  candidate: Turn;
};
type Score = {
  matched: number;
  total: number;
  agreement: number;
  median_ms: number;
  p95_ms: number;
};
type Run = {
  id: string;
  status: string;
  completed: number;
  total: number;
  rows?: Row[];
  baseline?: Score;
  candidate?: Score;
  error?: string;
  config?: { baseline_name: string; provider: string; dataset_version: string };
};
type Page = 'Conversations' | 'References' | 'Review queue' | 'Evaluations' | 'Architecture';

const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

function Doodle({ kind = 'plant', className = '' }: { kind?: string; className?: string }) {
  return (
    <svg className={`doodle ${className}`} viewBox="0 0 160 150" fill="none" aria-hidden="true">
      {kind === 'plant' ? (
        <g stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M73 118c-5-30 3-55 17-83M79 87C47 82 43 59 37 46c27-3 45 14 42 41ZM86 67c27 0 39-17 41-35-24 2-41 13-41 35Z M88 43c-18-2-24-17-22-29 19 0 24 11 22 29Z" />
          <path d="m50 110 53 1-7 26-37-1-9-26Z M59 119l38 1 M35 116l-10 5m107-32 7-6 M115 15l3-7m-6 3 9 1" />
        </g>
      ) : kind === 'orbit' ? (
        <g stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <ellipse cx="80" cy="75" rx="65" ry="24" transform="rotate(-28 80 75)" />
          <ellipse cx="80" cy="75" rx="24" ry="61" transform="rotate(-28 80 75)" />
          <circle cx="80" cy="75" r="12" />
          <path d="m122 29 3-10 4 9 9 4-10 2-4 10-2-10-8-3 8-2Z M24 109l-5 6m13 3-2 7" />
        </g>
      ) : (
        <g stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m33 112 16-72 63 8-11 74-68-10Z M54 55l42 6 M50 69l43 6 M48 83l23 3 M83 88l7 9 18-16 M25 30l-8-8m109 91 11 3m-7-14 8-3" />
          <path d="M45 26c29-13 67-9 84 14m-9-3 11 4-2-12" />
        </g>
      )}
    </svg>
  );
}
function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value}`}>
      <span />
      {value === 'answer'
        ? 'Evidence found'
        : value === 'review'
          ? 'Needs a second look'
          : value === 'abstain'
            ? 'More evidence needed'
            : value}
    </span>
  );
}

export default function Workbench() {
  const [page, setPage] = useState<Page>('Conversations');
  const [references, setReferences] = useState<Reference[]>([]);
  const [selected, setSelected] = useState('');
  const [provider, setProvider] = useState('');
  const [publicDemo, setPublicDemo] = useState(false);
  const [modelsReady, setModelsReady] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState('');
  const [conversation, setConversation] = useState(
    () => localStorage.getItem('evidra.conversation') || crypto.randomUUID(),
  );
  const [reviews, setReviews] = useState<Review[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [detail, setDetail] = useState<(Reference & { passages: Evidence[] }) | null>(null);
  const [inspected, setInspected] = useState<Turn | null>(null);
  const [uploading, setUploading] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
  const [audioBusy, setAudioBusy] = useState(false);
  const [evalDetail, setEvalDetail] = useState<Row | null>(null);
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const end = useRef<HTMLDivElement>(null);
  const importFile = useRef<HTMLInputElement>(null);
  const recordingFile = useRef<HTMLInputElement>(null);
  const active = references.find((item) => item.id === selected);
  const pending = reviews.filter((item) => item.status === 'pending').length;
  const latest = runs[0];

  async function refresh() {
    const [docs, queue, history] = await Promise.all([
      request<Reference[]>('/documents'),
      request<Review[]>('/reviews'),
      request<Run[]>('/evaluations'),
    ]);
    setReferences(docs);
    setReviews(queue);
    setRuns(history);
    setSelected(
      (current) =>
        current ||
        docs.find((d) => d.source === 'Bundled synthetic fixture')?.id ||
        docs[0]?.id ||
        '',
    );
  }
  useEffect(() => {
    Promise.all([
      refresh(),
      request<{ provider: string; public: boolean; models_ready: boolean; model_error: string }>(
        '/health',
      ).then((h) => {
        setProvider(h.provider);
        setPublicDemo(h.public);
        setModelsReady(h.models_ready);
        if (h.model_error) setError(h.model_error);
      }),
      request<Turn[]>(`/conversations/${conversation}`).then(setTurns),
    ]).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (modelsReady) return;
    const timer = setInterval(
      () =>
        request<{ models_ready: boolean; model_error: string }>('/health')
          .then((h) => {
            setModelsReady(h.models_ready);
            if (h.model_error) setError(h.model_error);
          })
          .catch((e) => setError(e.message)),
      6000,
    );
    return () => clearInterval(timer);
  }, [modelsReady]);
  useEffect(() => {
    localStorage.setItem('evidra.conversation', conversation);
  }, [conversation]);
  useEffect(() => {
    if (turns.length) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [turns]);
  useEffect(() => {
    if (!latest || !['pending', 'running'].includes(latest.status)) return;
    const timer = setInterval(
      () =>
        request<Run[]>('/evaluations')
          .then(setRuns)
          .catch((e) => setError(e.message)),
      1200,
    );
    return () => clearInterval(timer);
  }, [latest?.id, latest?.status]);
  useEffect(() => {
    if (page === 'References' && selected)
      request<Reference & { passages: Evidence[] }>(`/documents/${selected}`)
        .then(setDetail)
        .catch((e) => setError(e.message));
  }, [page, selected]);

  function newConversation() {
    setConversation(crypto.randomUUID());
    setTurns([]);
    setInspected(null);
    setQuestion('');
  }
  function selectReference(id: string) {
    setSelected(id);
    newConversation();
  }
  async function ask(text = question) {
    if (!text.trim() || !selected || busy || !modelsReady) return;
    setBusy(true);
    setError('');
    setQuestion('');
    try {
      const result = await request<Turn>(
        '/questions',
        json({ question: text, document_id: selected, conversation_id: conversation }),
      );
      setTurns((previous) => [...previous, result]);
      setInspected(result);
      await refresh();
      return result;
    } catch (e) {
      setError((e as Error).message);
      setQuestion(text);
    } finally {
      setBusy(false);
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    setUploading(true);
    setError('');
    const data = new FormData();
    data.append('file', file);
    data.append('title', file.name.replace(/\.[^.]+$/, ''));
    try {
      const doc = await request<Reference>('/documents', { method: 'POST', body: data });
      await refresh();
      selectReference(doc.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (importFile.current) importFile.current.value = '';
    }
  }
  async function evaluate() {
    setRunBusy(true);
    setError('');
    try {
      const demo = references.find((d) => d.source === 'Bundled synthetic fixture');
      if (!demo) throw new Error('Import the bundled Aster reference before running its suite.');
      await request('/evaluations', json({ document_id: demo.id }));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunBusy(false);
    }
  }
  async function resolve(item: Review) {
    setError('');
    try {
      await request(`/reviews/${item.id}`, {
        ...json({
          status: item.status === 'pending' ? 'resolved' : 'pending',
          note: reviewNotes[item.id] ?? item.note,
        }),
        method: 'PATCH',
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function transcribe(file?: File) {
    if (!file) return;
    setAudioBusy(true);
    setError('');
    const data = new FormData();
    data.append('file', file);
    try {
      const result = await request<{ text: string }>('/voice/transcribe', {
        method: 'POST',
        body: data,
      });
      setQuestion(result.text);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAudioBusy(false);
      if (recordingFile.current) recordingFile.current.value = '';
    }
  }
  async function speak(turn: Turn) {
    setAudioBusy(true);
    setError('');
    try {
      const response = await fetchApi(`/voice/speak/${turn.id}`, { method: 'POST' });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail);
      }
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setAudioBusy(false);
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        setAudioBusy(false);
        setError('Could not play the generated audio.');
      };
      await audio.play();
    } catch (e) {
      setError((e as Error).message);
      setAudioBusy(false);
    }
  }
  const nav = [
    { name: 'Conversations', icon: MessageCircle },
    { name: 'References', icon: BookOpen },
    { name: 'Review queue', icon: ClipboardCheck },
    { name: 'Evaluations', icon: FlaskConical },
    { name: 'Architecture', icon: GitBranch },
  ] as const;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage('Conversations');
          }}
        >
          <span className="brand-mark">
            <Leaf size={22} />
          </span>
          evidra<span className="brand-dot">✳</span>
        </a>
        <div className="workspace-label">
          <span className="avatar">S</span>
          <div>
            Your workspace<small>A place to think clearly</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <div className="nav-caption">THE WORKBENCH</div>
        <nav aria-label="Workspace">
          {nav.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={`nav-item ${page === name ? 'active' : ''}`}
              onClick={() => {
                setPage(name);
                setError('');
              }}
            >
              <Icon size={18} />
              {name}
              {name === 'Review queue' && pending > 0 && (
                <span className="nav-count">{pending}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Doodle kind="plant" />
          <span className="handwritten">
            Good answers
            <br />
            have roots.
          </span>
          <p>
            A little more evidence.
            <br />A little less guesswork.
          </p>
        </div>
        <div className="sidebar-bottom">
          <span className="tiny-dot" />
          <span>Independent by design</span>
          <CircleHelp size={15} />
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={13} />
            <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span className="mode-pill">
              <span className={`tiny-dot ${provider ? '' : 'offline'}`} />
              {provider && provider !== 'extractive'
                ? 'Open model'
                : provider
                  ? 'Local evidence'
                  : 'Connecting'}
            </span>
            <span className="profile-bubble">S</span>
          </div>
        </header>
        {!modelsReady && (
          <div className="demo-notice" role="status">
            The open models are warming up. References and architecture are available while you
            wait.
          </div>
        )}
        {publicDemo && (
          <div className="demo-notice">
            Public demo · your browser has a separate session, valid for 24 hours. Use sample
            documents; records may disappear when hosting restarts. Voice recordings are processed
            on this server and are not saved.
            {zeroGpu && (
              <>
                {' '}
                Free GPU use has daily limits.{' '}
                <a
                  href="https://huggingface.co/spaces/rshalvi/evidra"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open on Hugging Face and sign in for your account's quota.
                </a>
              </>
            )}
          </div>
        )}
        {error && (
          <div role="alert" className="error-banner">
            {error}
            <button aria-label="Dismiss error" onClick={() => setError('')}>
              <X size={16} />
            </button>
          </div>
        )}

        {page === 'Conversations' && (
          <main className="conversation-layout">
            <section className="conversation-main">
              <div className="page-kicker">
                <span className="eyebrow">FOLLOW THE EVIDENCE</span>
                <button className="text-button" onClick={newConversation}>
                  <Plus size={15} />
                  New conversation
                </button>
              </div>
              <div className="conversation-scroll">
                {turns.length === 0 ? (
                  <>
                    <div className="welcome">
                      <div className="hello-icon">
                        <Sparkles size={24} />
                      </div>
                      <h1>
                        Let's make room
                        <br />
                        for{' '}
                        <span className="underlined">
                          better answers.
                          <svg viewBox="0 0 300 18" aria-hidden="true">
                            <path d="M3 11Q147-2 296 9M28 16Q177 5 271 13" />
                          </svg>
                        </span>
                      </h1>
                      <p>
                        Ask a question. Follow the sources.
                        <br />
                        Know when it's time for a second opinion.
                      </p>
                      <Doodle kind="orbit" className="hero-doodle" />
                    </div>
                    <div className="reference-strip">
                      <span className="file-icon">
                        <FileText size={19} />
                      </span>
                      <div>
                        <small>YOUR REFERENCE</small>
                        <strong>{active?.title || 'Loading your references…'}</strong>
                      </div>
                      <span className="version">v{active?.version || 1}</span>
                      <button className="text-button" onClick={() => setPage('References')}>
                        Take a look
                        <ArrowUpRight size={14} />
                      </button>
                    </div>
                    <div className="suggestion-heading">
                      A few places to start<span className="handwritten">pick a thread ↙</span>
                    </div>
                    <div className="suggestions">
                      {[
                        {
                          title: 'Find a fact',
                          text: 'How many participants enrolled in the Aster study?',
                          icon: BookOpen,
                        },
                        {
                          title: 'Notice a gap',
                          text: 'What dosing instructions are provided?',
                          icon: CircleHelp,
                        },
                        {
                          title: 'Ask for a review',
                          text: 'A participant reported a rash after the visit.',
                          icon: ShieldCheck,
                        },
                      ].map(({ title, text, icon: Icon }) => (
                        <button
                          className="suggestion"
                          key={title}
                          onClick={() => ask(text)}
                          disabled={busy || !selected}
                        >
                          <Icon size={18} />
                          <strong>{title}</strong>
                          <span>{text}</span>
                          <ArrowUpRight size={16} />
                        </button>
                      ))}
                    </div>
                    <div className="quiet-note">
                      <ShieldCheck size={16} />
                      <span>
                        Our sample reference is entirely fictional. You're free to explore.
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="turn-list">
                    {turns.map((turn) => (
                      <article className="turn" key={turn.id}>
                        <div className="user-question">
                          <span className="profile-bubble">S</span>
                          <div>{turn.question}</div>
                        </div>
                        <div className="assistant-answer">
                          <span className="answer-mark">
                            <Leaf size={17} />
                          </span>
                          <div className="answer-body">
                            <div className="answer-title">
                              evidra
                              <Badge value={turn.disposition} />
                            </div>
                            <p>{turn.answer || turn.reason}</p>
                            {turn.answer && (
                              <small className="answer-note">
                                {turn.provider === 'extractive'
                                  ? 'A direct excerpt from your reference.'
                                  : 'Model-generated response. Review its cited evidence.'}
                              </small>
                            )}
                            <div className="answer-actions">
                              <button className="text-button" onClick={() => setInspected(turn)}>
                                <BookOpen size={14} />
                                Show the evidence
                              </button>
                              {turn.disposition === 'answer' && (
                                <button
                                  className="text-button"
                                  onClick={() => speak(turn)}
                                  disabled={audioBusy}
                                >
                                  <Volume2 size={14} />
                                  Read aloud
                                </button>
                              )}
                              <span>{turn.elapsed_ms.toFixed(0)} ms</span>
                            </div>
                          </div>
                        </div>
                      </article>
                    ))}
                    <div ref={end} />
                  </div>
                )}
                {busy && (
                  <div className="thinking">
                    <LoaderCircle className="spin" size={17} />
                    Looking through your reference…
                  </div>
                )}
              </div>
              <div className="composer-wrap">
                <VoiceConversation
                  key={`${selected}:${conversation}`}
                  disabled={busy || audioBusy || !selected || !modelsReady}
                  send={ask}
                  fetchApi={fetchApi}
                />
                <form
                  className="composer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    ask();
                  }}
                >
                  <textarea
                    aria-label="Ask your reference"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="What's on your mind?"
                    rows={2}
                    maxLength={4000}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        e.preventDefault();
                        ask();
                      }
                    }}
                  />
                  <div className="composer-bottom">
                    <div className="reference-select">
                      <BookOpen size={14} />
                      <select
                        aria-label="Selected reference"
                        value={selected}
                        onChange={(e) => selectReference(e.target.value)}
                      >
                        {references.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.title} · v{d.version}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="composer-tools">
                      <button
                        type="button"
                        className="icon-button"
                        aria-label="Transcribe an audio file"
                        title="Transcribe an audio file (optional local speech)"
                        onClick={() => recordingFile.current?.click()}
                        disabled={audioBusy}
                      >
                        <Headphones size={17} />
                      </button>
                      <button
                        className="send-button"
                        aria-label="Send question"
                        disabled={busy || !question.trim() || !selected || !modelsReady}
                      >
                        {busy ? (
                          <LoaderCircle size={17} className="spin" />
                        ) : (
                          <ArrowRight size={19} />
                        )}
                      </button>
                    </div>
                  </div>
                </form>
                <p className="composer-footnote">
                  {provider && provider !== 'extractive'
                    ? 'Open model · verify important claims against the source.'
                    : 'Local evidence mode · source excerpts, no LLM required.'}
                  <span>Ctrl + Enter to send</span>
                </p>
              </div>
            </section>
            <aside className="evidence-panel">
              <div className="panel-heading">
                <span>
                  <BookOpen size={17} />
                  The paper trail
                </span>
                <span className="panel-dot" />
              </div>
              {inspected ? (
                <>
                  <Badge value={inspected.disposition} />
                  <p className="panel-reason">{inspected.reason}</p>
                  <div className="eyebrow">SOURCE PASSAGES</div>
                  {inspected.evidence.map((e, index) => (
                    <div
                      className={`evidence-card ${inspected.citations.includes(e.id) ? 'cited' : ''}`}
                      key={e.id}
                    >
                      <div>
                        <span className="source-index">{index + 1}</span>
                        <strong>{e.locator}</strong>
                        {inspected.citations.includes(e.id) && <Check size={14} />}
                      </div>
                      <p>{e.text}</p>
                    </div>
                  ))}
                  <details className="trace">
                    <summary>
                      How we got here
                      <ChevronDown size={14} />
                    </summary>
                    {inspected.trace.map((step, index) => (
                      <div className="trace-step" key={index}>
                        <strong>{step.stage}</strong>
                        <p>{step.detail}</p>
                      </div>
                    ))}
                  </details>
                  <small className="panel-limit">
                    References are checked for membership. Interpretation still needs judgment.
                  </small>
                </>
              ) : (
                <div className="evidence-empty">
                  <Doodle kind="notes" />
                  <h3>Nothing to untangle. Yet.</h3>
                  <p>
                    Your supporting passages and decision trail will appear here after you ask a
                    question.
                  </p>
                  <div className="dashed-note">
                    <Check size={15} />
                    Sources you can inspect
                    <br />
                    <Check size={15} />
                    Decisions you can follow
                    <br />
                    <Check size={15} />
                    Gaps we won't paper over
                  </div>
                </div>
              )}
              <div className="panel-footer">
                <ShieldCheck size={14} />
                Evidence first. Always curious.
              </div>
            </aside>
          </main>
        )}

        {page === 'References' && (
          <main className="page-content">
            <PageHeading
              eyebrow="YOUR SOURCE OF TRUTH"
              title="A shelf for your references."
              subtitle="Keep the original close. Every import gets its own version and fingerprint."
              action={
                <button
                  className="primary-button"
                  disabled={uploading}
                  onClick={() => importFile.current?.click()}
                >
                  {uploading ? <LoaderCircle size={16} className="spin" /> : <Upload size={16} />}
                  Import a reference
                </button>
              }
            />
            <div className="library-layout">
              <div className="reference-list">
                {references.map((doc) => (
                  <button
                    className={`reference-item ${selected === doc.id ? 'selected' : ''}`}
                    key={doc.id}
                    onClick={() => selectReference(doc.id)}
                  >
                    <span className="file-icon">
                      <FileText size={21} />
                    </span>
                    <div>
                      <strong>{doc.title}</strong>
                      <span>
                        {doc.passage_count} passages · v{doc.version} · {date(doc.created_at)}
                      </span>
                    </div>
                    <ChevronRight size={16} />
                  </button>
                ))}
                <div className="upload-hint">
                  <Doodle kind="notes" />
                  <p>Bring a little context.</p>
                  <small>
                    Text, Markdown or searchable PDF.
                    <br />
                    Up to 5 MB. Scanned PDFs need OCR.
                  </small>
                </div>
              </div>
              <section className="document-preview">
                {detail ? (
                  <>
                    <div className="preview-heading">
                      <div>
                        <span className="eyebrow">REFERENCE PREVIEW</span>
                        <h2>{detail.title}</h2>
                      </div>
                      <span className="version">v{detail.version}</span>
                    </div>
                    <p className="muted">{detail.source}</p>
                    <div className="hash">SHA-256 · {detail.digest.slice(0, 20)}…</div>
                    {detail.passages.map((p) => (
                      <article className="passage" key={p.id}>
                        <h3>{p.locator}</h3>
                        <p>{p.text}</p>
                      </article>
                    ))}
                  </>
                ) : (
                  <p className="muted">Choose a reference to read it here.</p>
                )}
              </section>
            </div>
          </main>
        )}

        {page === 'Review queue' && (
          <main className="page-content">
            <PageHeading
              eyebrow="A HUMAN IN THE LOOP"
              title="Some things deserve a second look."
              subtitle="Review the original message, leave a note, and keep the decision attached to its evidence."
            />
            <div className="section-line">
              <span>{pending} awaiting review</span>
              <small>Original responses stay unchanged.</small>
            </div>
            {reviews.length === 0 ? (
              <Empty
                kind="plant"
                title="A quiet queue is a good start."
                text="Messages that need human judgment will land here. Try the safety scenario in Conversations."
              />
            ) : (
              <div className="review-grid">
                {reviews.map((item) => (
                  <article className="review-card" key={item.id}>
                    <div className="card-row">
                      <Badge value={item.status} />
                      <small>{date(item.created_at)}</small>
                    </div>
                    <h3>{item.question}</h3>
                    <p>{item.reason}</p>
                    <span className="review-reference">
                      <FileText size={14} />
                      {item.document_title} · v{item.document_version}
                    </span>
                    <label>
                      Reviewer's note
                      <textarea
                        placeholder="What did you find?"
                        value={reviewNotes[item.id] ?? item.note}
                        onChange={(e) =>
                          setReviewNotes((previous) => ({ ...previous, [item.id]: e.target.value }))
                        }
                      />
                    </label>
                    <button className="secondary-button" onClick={() => resolve(item)}>
                      <Check size={15} />
                      {item.status === 'pending' ? 'Save & resolve' : 'Reopen review'}
                    </button>
                  </article>
                ))}
              </div>
            )}
          </main>
        )}

        {page === 'Evaluations' && (
          <main className="page-content">
            <PageHeading
              eyebrow="SHOW YOUR WORK"
              title="Less guesswork. More checking."
              subtitle="Run the same 40 fictional cases through a baseline and the guarded pipeline."
              action={
                <button
                  className="primary-button"
                  disabled={runBusy || ['pending', 'running'].includes(latest?.status)}
                  onClick={evaluate}
                >
                  {runBusy || ['pending', 'running'].includes(latest?.status) ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : (
                    <FlaskConical size={16} />
                  )}
                  Run the Aster suite
                </button>
              }
            />
            <div className="evaluation-note">
              <CircleHelp size={17} />
              <span>
                This measures expected routing on synthetic fixtures, not medical accuracy.{' '}
                {['ollama', 'transformers'].includes(provider)
                  ? 'The baseline uses the same model with the evidence constraints disabled.'
                  : 'The baseline returns unfiltered excerpts; no LLM runs in this mode.'}
              </span>
            </div>
            {latest ? (
              <>
                <div className="section-line">
                  <span>
                    Latest run <Badge value={latest.status} />
                  </span>
                  <small>
                    {latest.completed} / {latest.total} cases ·{' '}
                    {latest.config?.dataset_version || 'Aster suite'}
                  </small>
                </div>
                {latest.error && (
                  <p role="alert" className="error-banner">
                    {latest.error}
                  </p>
                )}
                {latest.candidate && latest.baseline && (
                  <div className="score-grid">
                    <ScoreCard label="Guarded pipeline" score={latest.candidate} accent />
                    <ScoreCard
                      label={latest.config?.baseline_name || 'Baseline'}
                      score={latest.baseline}
                    />
                    <div className="metric-card">
                      <span className="eyebrow">RESPONSE TIME</span>
                      <strong>
                        {latest.candidate.median_ms.toFixed(1)}
                        <small> ms</small>
                      </strong>
                      <p>Median · p95 {latest.candidate.p95_ms.toFixed(1)} ms</p>
                      <span className="handwritten">measured, not guessed ↗</span>
                    </div>
                  </div>
                )}
                <div className="results-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Case</th>
                        <th>Expected</th>
                        <th>Baseline</th>
                        <th>Guarded</th>
                        <th>Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latest.rows?.map((row) => (
                        <tr key={row.id}>
                          <td>
                            <button className="table-question" onClick={() => setEvalDetail(row)}>
                              <small>
                                {row.id} · {row.category}
                              </small>
                              {row.question}
                            </button>
                          </td>
                          <td>{row.expected}</td>
                          <td>
                            <Badge value={row.baseline.disposition} />
                          </td>
                          <td>
                            <Badge value={row.candidate.disposition} />
                          </td>
                          <td>
                            {row.expected === row.candidate.disposition ? (
                              <span className="match">
                                <Check size={15} />
                                Match
                              </span>
                            ) : (
                              <span className="mismatch">Inspect</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="muted">
                  {runs.length} saved {runs.length === 1 ? 'run' : 'runs'}. Public regression
                  fixtures; a held-out benchmark is future work.
                </p>
              </>
            ) : (
              <Empty
                kind="orbit"
                title="Put the pipeline through its paces."
                text="Forty small questions, including the awkward ones. You'll see every outcome, not just the good ones."
              />
            )}
          </main>
        )}

        {page === 'Architecture' && (
          <main className="page-content">
            <PageHeading
              eyebrow="UNDER THE HOOD"
              title="Small pieces. Clear responsibilities."
              subtitle="A modular monolith: one API, explicit stages, and a trail you can inspect."
            />
            <div className="architecture-flow">
              {[
                'React workspace',
                'FastAPI boundary',
                'Intent + retrieval',
                'Excerpts / Ollama',
                'Citation checks',
                'Answer / review',
              ].map((label, index) => (
                <React.Fragment key={label}>
                  <div>
                    <span>0{index + 1}</span>
                    <strong>{label}</strong>
                  </div>
                  {index < 5 && <ArrowRight size={18} />}
                </React.Fragment>
              ))}
            </div>
            <div className="architecture-grid">
              {[
                {
                  title: 'Keep sources immutable',
                  text: 'Every import has a content hash and version. A conversation points to the exact reference it used.',
                },
                {
                  title: 'Be honest about the model',
                  text: 'The default mode quotes retrieved passages. Ollama is a separate adapter with explicit failures and no silent fallback.',
                },
                {
                  title: 'Make failure inspectable',
                  text: 'Missing evidence leads to abstention. Safety mentions and invalid provider responses lead to a review queue.',
                },
                {
                  title: 'Measure a real comparison',
                  text: 'The same cases run against a baseline and guarded pipeline. Saved runs include configuration, outcomes and timings.',
                },
                {
                  title: 'Start local, grow deliberately',
                  text: 'SQLite keeps setup light. PostgreSQL is supported through configuration. Workers and semantic retrieval are documented extensions.',
                },
                {
                  title: 'Keep the boundary clear',
                  text: 'This local workspace has no tenant authentication. Use fictional fixtures; public deployment requires additional access controls.',
                },
              ].map((item) => (
                <article className="architecture-card" key={item.title}>
                  <GitBranch size={19} />
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </article>
              ))}
            </div>
            <div className="architecture-footer">
              <Doodle kind="plant" />
              <div>
                <h3>Built to be understood.</h3>
                <p>
                  The repository includes system design, decisions, failure behavior, and an
                  evaluation protocol.
                </p>
              </div>
            </div>
          </main>
        )}
      </div>
      <input
        hidden
        type="file"
        accept=".txt,.md,.pdf"
        ref={importFile}
        onChange={(e) => upload(e.target.files?.[0])}
      />
      <input
        hidden
        type="file"
        accept="audio/*"
        ref={recordingFile}
        onChange={(e) => transcribe(e.target.files?.[0])}
      />
      {evalDetail && (
        <div className="modal-backdrop" onClick={() => setEvalDetail(null)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Evaluation case details"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close icon-button"
              aria-label="Close case details"
              onClick={() => setEvalDetail(null)}
            >
              <X size={20} />
            </button>
            <span className="eyebrow">
              {evalDetail.id} · {evalDetail.category}
            </span>
            <h2>{evalDetail.question}</h2>
            <p>
              Expected: <strong>{evalDetail.expected}</strong>
            </p>
            <Badge value={evalDetail.candidate.disposition} />
            <p>{evalDetail.candidate.answer || evalDetail.candidate.reason}</p>
            <h3>Retrieved evidence</h3>
            {evalDetail.candidate.evidence.map((e) => (
              <div className="evidence-card" key={e.id}>
                <strong>{e.locator}</strong>
                <p>{e.text}</p>
              </div>
            ))}
          </section>
        </div>
      )}
    </div>
  );
}

function PageHeading({
  eyebrow,
  title,
  subtitle,
  action,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {action}
    </div>
  );
}
function Empty({ kind, title, text }: { kind: string; title: string; text: string }) {
  return (
    <div className="empty-state">
      <Doodle kind={kind} />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
function ScoreCard({
  label,
  score,
  accent = false,
}: {
  label: string;
  score: Score;
  accent?: boolean;
}) {
  return (
    <div className={`metric-card ${accent ? 'accent' : ''}`}>
      <span className="eyebrow">{label}</span>
      <strong>
        {score.agreement}
        <small>%</small>
      </strong>
      <p>
        {score.matched} of {score.total} routing decisions match
      </p>
      <div className="progress">
        <span style={{ width: `${score.agreement}%` }} />
      </div>
    </div>
  );
}
