import { useEffect, useRef, useState, lazy, Suspense } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  FileText,
  Headphones,
  LoaderCircle,
  Mic,
  Plus,
  Send,
  ShieldCheck,
  Volume2,
  X,
} from 'lucide-react';
import { fetchApi, request, json } from './api';
import { VoiceConversation } from './VoiceConversation';
import './guided.css';

const Workbench = lazy(() => import('./Workbench'));
type Document = {
  id: string;
  title: string;
  source: string;
  version: number;
  passage_count: number;
  text_preview?: string;
};
type Turn = {
  id: string;
  question: string;
  answer: string;
  reason: string;
  disposition: string;
  citations: string[];
  evidence: { id: string; text: string; locator: string }[];
  elapsed_ms: number;
  trace: { stage: string; detail: string }[];
  language?: string;
};
const examples = {
  en: [
    'How many days of paid leave do I get?',
    'When is the weekly team meeting?',
    'How do I claim work equipment expenses?',
  ],
  hi: [
    'मुझे साल में कितने दिन की छुट्टी मिलती है?',
    'टीम की साप्ताहिक बैठक कब होती है?',
    'काम के उपकरणों का खर्च कैसे मिलेगा?',
  ],
};

function Scribble() {
  return (
    <svg viewBox="0 0 180 90" fill="none" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 60c18-28 24-46 41-44 24 3-6 44-8 36-3-11 27-32 37-21 12 12-16 31-11 17 6-16 34-22 44-4 8 14-3 23-1 8 3-18 21-13 43-1" />
        <path d="m152 39 12 14-19 5M35 77l94-6m-80 13 49-3" />
      </g>
    </svg>
  );
}

export default function Guided() {
  const [health, setHealth] = useState({
    models_ready: false,
    public: false,
    provider: '',
    model_error: '',
  });
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState<Document | null>(null);
  const [language, setLanguage] = useState<'en' | 'hi'>('en');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversation, setConversation] = useState(crypto.randomUUID());
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [phase, setPhase] = useState('idle');
  const [queue, setQueue] = useState('');
  const [tools, setTools] = useState(false);
  const [showDocuments, setShowDocuments] = useState(false);
  const [playing, setPlaying] = useState('');
  const uploadRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef('');
  const questionAbort = useRef<AbortController | null>(null);
  const activeGeneration = useRef(0);

  useEffect(() => {
    let mounted = true;
    const refresh = async () => {
      try {
        const result = await request<typeof health>('/health');
        if (mounted) setHealth(result);
      } catch {
        if (mounted) setError('Could not connect. Refresh the page to try again.');
      }
    };
    void refresh();
    void request<Document[]>('/documents')
      .then((d) => {
        if (mounted) setDocuments(d);
      })
      .catch(() => {});
    const timer = setInterval(refresh, 10000);
    return () => {
      mounted = false;
      clearInterval(timer);
      questionAbort.current?.abort();
      clearPlayback();
    };
  }, []);

  function clearPlayback() {
    audioRef.current?.pause();
    if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    audioRef.current = null;
    audioUrl.current = '';
    setPlaying('');
  }
  function choose(document: Document) {
    activeGeneration.current += 1;
    questionAbort.current?.abort();
    clearPlayback();
    setSelected(document);
    setTurns([]);
    setConversation(crypto.randomUUID());
    setQuestion('');
    setError('');
    setBusy(false);
    setShowDocuments(false);
    setPhase('idle');
  }
  async function demo() {
    setUploading(true);
    setError('');
    try {
      const document = await request<Document>('/demo', json({}));
      choose(document);
      setDocuments(await request<Document[]>('/documents'));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    setError('');
    if (file.size > 5 * 1024 * 1024) {
      setError('Choose a document smaller than 5 MB.');
      return;
    }
    setUploading(true);
    try {
      const body = new FormData();
      body.append('file', file);
      const document = await request<Document>('/documents', { method: 'POST', body });
      choose(document);
      setDocuments(await request<Document[]>('/documents'));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  }
  async function ask(text: string, signal?: AbortSignal) {
    if (!selected || busy || !text.trim()) return;
    const generation = activeGeneration.current;
    setBusy(true);
    setError('');
    setQueue('Finding your answer');
    clearPlayback();
    questionAbort.current = new AbortController();
    try {
      const turn = await request<Turn>(
        '/questions',
        {
          ...json({
            question: text,
            document_id: selected.id,
            conversation_id: conversation,
            language,
          }),
          signal: signal
            ? AbortSignal.any([signal, questionAbort.current.signal])
            : questionAbort.current.signal,
        },
        setQueue,
      );
      if (generation !== activeGeneration.current) return;
      setTurns((current) => [...current, turn]);
      setQuestion('');
      return turn;
    } catch (e) {
      if (generation === activeGeneration.current && (e as Error).name !== 'AbortError')
        setError((e as Error).message);
    } finally {
      if (generation === activeGeneration.current) {
        setBusy(false);
        setQueue('');
      }
    }
  }
  async function readAloud(turn: Turn) {
    if (playing === turn.id) {
      clearPlayback();
      return;
    }
    clearPlayback();
    setPlaying(turn.id);
    const generation = activeGeneration.current;
    try {
      const response = await fetchApi(`/voice/speak/${turn.id}`, { method: 'POST' });
      if (!response.ok) throw new Error('Could not prepare the audio. Please try again.');
      const blob = await response.blob();
      if (generation !== activeGeneration.current) return;
      audioUrl.current = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl.current);
      audioRef.current = audio;
      audio.onended = clearPlayback;
      audio.onerror = () => {
        clearPlayback();
        setError('Your browser could not play the audio.');
      };
      await audio.play();
    } catch (e) {
      clearPlayback();
      setError((e as Error).message);
    }
  }
  const last = turns.at(-1);
  const sample = selected?.source === 'Bundled company handbook';
  const voiceActive = phase !== 'idle';
  const status = busy
    ? queue
    : phase === 'idle'
      ? 'Ready when you are'
      : {
          listening: 'Listening to you',
          transcribing: 'Turning speech into text',
          thinking: 'Finding your answer',
          speaking: 'Speaking your answer',
          'preparing speech': 'Preparing your voice reply',
          'opening microphone': 'Opening your microphone',
        }[phase] || phase;

  if (tools)
    return (
      <>
        <div className="return-bar">
          <button onClick={() => setTools(false)}>
            <ArrowRight size={16} /> Back to your assistant
          </button>
          <span>Engineering workspace · references, reviews, evaluations & architecture</span>
        </div>
        <Suspense fallback={<p>Opening workspace…</p>}>
          <Workbench />
        </Suspense>
      </>
    );

  return (
    <div className="guided">
      <header className="site-header">
        <a
          className="wordmark"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
        >
          <span className="brand-mark">✳</span>evidra<span className="brand-dot">.</span>
        </a>
        <div className="header-right">
          <span className="demo-pill">
            <span /> Open model demo
          </span>
          <a href="#how-it-works">
            How it works <ArrowUpRight size={14} />
          </a>
        </div>
      </header>
      <main className="main-flow">
        <section className={`intro ${selected ? 'compact' : ''}`}>
          <div className="intro-kicker">
            <span /> A voice assistant, built from your documents
          </div>
          <h1>
            Your documents.
            <br />
            <span className="voice-word">
              Now with a voice.
              <svg viewBox="0 0 450 18" aria-hidden="true">
                <path d="M5 12Q195-6 444 9M25 17Q229 3 419 15" />
              </svg>
            </span>
          </h1>
          <p>
            Ask out loud. Hear an answer. See exactly where it came from.
            <br className="desktop-break" /> Try it with a sample handbook, then bring your own.
          </p>
          {!selected && (
            <div className="intro-note">
              <Scribble />
              <span>No setup. Just a little curiosity.</span>
            </div>
          )}
        </section>
        <ol className="steps" aria-label="Your next steps">
          {['Choose a document', 'Talk to your assistant', 'Check the source'].map((label, i) => (
            <li
              key={label}
              className={i === 0 || (i === 1 && selected) || (i === 2 && last) ? 'available' : ''}
              aria-current={(selected ? (last ? 2 : 1) : 0) === i ? 'step' : undefined}
            >
              <span>
                {(i === 0 && selected) || (i === 1 && last) ? <Check size={15} /> : `0${i + 1}`}
              </span>
              {label}
            </li>
          ))}
        </ol>
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError('')}>
              <X size={18} />
            </button>
          </div>
        )}
        {!health.models_ready && (
          <div className="warming" role="status">
            <LoaderCircle className="spin" size={16} />
            {health.model_error ||
              'The assistant is waking up. You can choose a document while it gets ready.'}
          </div>
        )}
        <input
          ref={uploadRef}
          type="file"
          accept=".pdf,.txt,.md"
          className="visually-hidden"
          aria-label="Upload a document"
          onChange={(e) => void upload(e.target.files?.[0])}
        />
        {!selected ? (
          <section className="choose-grid" aria-label="Choose a document">
            <button className="sample-card" onClick={() => void demo()} disabled={uploading}>
              <div className="card-label">
                THE QUICKEST WAY IN <span>~ 1 minute</span>
              </div>
              <div className="paper-illustration">
                <div className="paper">
                  <FileText size={26} />
                  <strong>Northstar</strong>
                  <span>Team handbook</span>
                  <i />
                  <i />
                  <i />
                </div>
                <span className="paper-sticker">
                  <Mic size={22} />
                </span>
                <span className="scribbled">give this a voice ↗</span>
              </div>
              <h2>Try the sample</h2>
              <p>
                Ask about time off, team meetings, or equipment. It’s a fictional handbook with real
                answers to explore.
              </p>
              <span className="card-action">
                {uploading ? 'Reading and indexing your document…' : 'Meet your assistant'}{' '}
                {uploading ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}
              </span>
            </button>
            <button
              className="upload-card"
              onClick={() => uploadRef.current?.click()}
              disabled={uploading}
            >
              <span className="upload-icon">
                <Plus size={26} />
              </span>
              <h2>Bring your own</h2>
              <p>
                A handbook, product guide, or set of notes.
                <br />
                Make something you already have easier to ask.
              </p>
              <span className="file-types">PDF · TXT · Markdown · up to 5 MB</span>
              <span className="card-action">
                Choose a document <ArrowRight size={18} />
              </span>
              <small>Use sample or non-sensitive files. Demo storage is temporary.</small>
            </button>
            {documents.some((d) => d.source !== 'Bundled synthetic fixture') && (
              <div className="existing-docs">
                <span>Already in this browser</span>
                {documents
                  .filter((d) => d.source !== 'Bundled synthetic fixture')
                  .map((d) => (
                    <button key={d.id} onClick={() => choose(d)}>
                      <FileText size={15} />
                      {d.title}
                      <ArrowRight size={14} />
                    </button>
                  ))}
              </div>
            )}
          </section>
        ) : (
          <>
            <section className="document-strip">
              <div className="document-symbol">
                <FileText size={23} />
              </div>
              <div>
                <span className="small-label">YOUR ASSISTANT KNOWS</span>
                <strong>{selected.title}</strong>
              </div>
              <span className="document-ready">
                <Check size={13} /> Ready · {selected.passage_count} passages
              </span>
              <button
                onClick={() => setShowDocuments(!showDocuments)}
                disabled={busy || voiceActive}
              >
                Change <ChevronDown size={15} />
              </button>
            </section>
            {selected.text_preview && (
              <details className="import-preview">
                <summary>Check the imported text</summary>
                <p>{selected.text_preview}</p>
                <small>
                  This is the beginning of the text we extracted. Answers search the whole document.
                </small>
              </details>
            )}
            {showDocuments && (
              <div className="document-picker">
                {documents.map((d) => (
                  <button key={d.id} onClick={() => choose(d)}>
                    <FileText size={16} />
                    {d.title}
                  </button>
                ))}
                <button onClick={() => uploadRef.current?.click()}>
                  <Plus size={16} />
                  Upload another document
                </button>
              </div>
            )}
            <section className="conversation-stage">
              <div className="voice-panel">
                <div className="voice-panel-top">
                  <span className="small-label">02 / LET’S TALK</span>
                  <label className="language-picker">
                    <span className="visually-hidden">Conversation language</span>
                    <select
                      value={language}
                      disabled={busy || voiceActive}
                      onChange={(e) => {
                        clearPlayback();
                        setLanguage(e.target.value as 'en' | 'hi');
                      }}
                    >
                      <option value="en">English</option>
                      <option value="hi">हिन्दी · Hindi</option>
                    </select>
                  </label>
                </div>
                <div className={`voice-orb ${phase} ${busy ? 'thinking' : ''}`} aria-hidden="true">
                  <div className="orb-ring ring-one" />
                  <div className="orb-ring ring-two" />
                  <div className="orb-core">
                    <Headphones size={40} strokeWidth={1.4} />
                  </div>
                  <span className="orb-spark spark-one">✦</span>
                  <span className="orb-spark spark-two">✧</span>
                </div>
                <h2>{language === 'hi' ? 'चलिए, बात करते हैं।' : 'Go ahead. Ask away.'}</h2>
                <p className="agent-status" role="status">
                  {status}
                </p>
                <VoiceConversation
                  key={`${selected.id}-${conversation}-${language}`}
                  disabled={!health.models_ready || busy || uploading || playing !== ''}
                  send={ask}
                  fetchApi={fetchApi}
                  language={language}
                  onPhase={setPhase}
                />
                <div className="type-divider">
                  <span />
                  or type your question
                  <span />
                </div>
                <form
                  className="question-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void ask(question);
                  }}
                >
                  <input
                    aria-label="Your question"
                    placeholder={
                      language === 'hi' ? 'अपना प्रश्न यहाँ लिखें…' : 'What would you like to know?'
                    }
                    value={question}
                    disabled={busy || voiceActive}
                    onChange={(e) => setQuestion(e.target.value)}
                    maxLength={4000}
                  />
                  <button
                    type="submit"
                    aria-label="Send question"
                    disabled={!question.trim() || busy || voiceActive || !health.models_ready}
                  >
                    {busy ? <LoaderCircle className="spin" size={18} /> : <Send size={18} />}
                  </button>
                </form>
                {
                  <div className="suggestions">
                    <span>Need a starting point?</span>
                    {(sample
                      ? examples[language]
                      : [
                          language === 'hi'
                            ? 'इस दस्तावेज़ का सारांश क्या है?'
                            : 'What is this document about?',
                        ]
                    ).map((q) => (
                      <button
                        key={q}
                        disabled={busy || voiceActive || !health.models_ready}
                        onClick={() => void ask(q)}
                      >
                        {q}
                        <ArrowUpRight size={14} />
                      </button>
                    ))}
                  </div>
                }
              </div>
              <section className="answer-panel" aria-label="Answers and sources" aria-live="polite">
                <div className="answer-panel-top">
                  <span className="small-label">03 / THE ANSWER & THE PROOF</span>
                  {turns.length > 0 && (
                    <button disabled={busy || voiceActive} onClick={() => choose(selected)}>
                      Start fresh <Plus size={14} />
                    </button>
                  )}
                </div>
                {!last ? (
                  <div className="answer-placeholder">
                    <div className="quote-doodle">
                      “<span>✦</span>
                    </div>
                    <h3>
                      Good answers
                      <br />
                      have something behind them.
                    </h3>
                    <p>
                      Your answer appears here, together with the passage it came from. No hunting
                      through pages.
                    </p>
                    <div className="answer-example">
                      <span>YOU COULD ASK</span>
                      <p>
                        “
                        {sample
                          ? examples[language][0]
                          : language === 'hi'
                            ? 'इस दस्तावेज़ का मुख्य विषय क्या है?'
                            : 'What does this document say about…?'}
                        ”
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="turn-list">
                    {[...turns].reverse().map((turn, index) => (
                      <article
                        className={`answer-turn ${index > 0 ? 'previous-turn' : ''}`}
                        key={turn.id}
                      >
                        <div className="asked-question">
                          <span>YOU ASKED</span>
                          <p>{turn.question}</p>
                        </div>
                        <div className="answer-meta">
                          <span
                            className={
                              turn.disposition === 'answer' ? 'source-badge' : 'review-badge'
                            }
                          >
                            {turn.disposition === 'answer' ? (
                              <>
                                <Check size={13} /> Answer with sources
                              </>
                            ) : turn.disposition === 'review' ? (
                              'Needs a person’s review'
                            ) : (
                              'Not enough information'
                            )}
                          </span>
                          <span>{(turn.elapsed_ms / 1000).toFixed(1)}s</span>
                        </div>
                        <p className="spoken-answer" lang={turn.language === 'hi' ? 'hi' : 'en'}>
                          {turn.answer || turn.reason}
                        </p>
                        <button
                          className="listen-answer"
                          onClick={() => void readAloud(turn)}
                          disabled={voiceActive || busy}
                        >
                          <Volume2 size={15} />
                          {playing === turn.id ? 'Stop audio' : 'Hear this answer'}
                        </button>
                        {turn.citations.length > 0 && (
                          <div className="source-evidence">
                            <span className="small-label">
                              <FileText size={13} /> FROM YOUR DOCUMENT
                            </span>
                            {turn.evidence
                              .filter((e) => turn.citations.includes(e.id))
                              .map((e) => (
                                <div key={e.id}>
                                  <blockquote>{e.text}</blockquote>
                                  <span className="source-location">
                                    {selected.title} / {e.locator}
                                  </span>
                                </div>
                              ))}
                          </div>
                        )}
                        <details className="answer-trace">
                          <summary>
                            How this answer was made <ChevronDown size={13} />
                          </summary>
                          {turn.trace.map((t, i) => (
                            <p key={i}>
                              <strong>{t.stage}</strong> {t.detail}
                            </p>
                          ))}
                        </details>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </section>
          </>
        )}
        <section className="how-section" id="how-it-works">
          <div>
            <span className="small-label">A LITTLE CONTEXT</span>
            <h2>
              A useful voice.
              <br />A checkable answer.
            </h2>
          </div>
          <div className="how-copy">
            <p>
              Evidra gives a document a voice. It finds relevant passages, creates a short answer,
              and reads it aloud. You can inspect the source every time.
            </p>
            <p>
              If the document doesn’t have an answer, the assistant tells you. English and Hindi
              conversations are available; Hindi questions are translated for search in English
              documents.
            </p>
            <details className="pipeline-detail">
              <summary>
                See what happens behind the scenes <ChevronDown size={14} />
              </summary>
              <div className="pipeline-flow">
                {[
                  'Microphone',
                  'Speech → text',
                  'Find passages',
                  'Check answer',
                  'Text → speech',
                ].map((s, i) => (
                  <span key={s}>
                    <b>{i + 1}</b>
                    {s}
                  </span>
                ))}
              </div>
              <p>
                Whisper · Qwen · Piper. Turn-taking voice, interruptible playback, separate visitor
                sessions, and a shared inference queue. Hindi is an early demo; pronunciation and
                translation can vary.
              </p>
            </details>
          </div>
        </section>
        <div className="demo-footnote">
          <ShieldCheck size={17} />
          <p>
            {health.public
              ? 'Each browser gets its own temporary workspace. Free GPU quotas apply; sign in to Hugging Face for your account’s quota.'
              : 'Local demo. Evidence mode returns excerpts; the hosted demo runs an open language model.'}
            <br />
            Use non-sensitive documents. Verify answers against their sources.
          </p>
          {health.public && (
            <a href="https://huggingface.co/spaces/rshalvi/evidra" target="_blank" rel="noreferrer">
              Hugging Face <ArrowUpRight size={13} />
            </a>
          )}
        </div>
      </main>
      <footer className="site-footer">
        <span>
          evidra. <span>A little more clarity.</span>
        </span>
        <button
          onClick={() => {
            clearPlayback();
            setTools(true);
          }}
        >
          Explore the engineering <ArrowUpRight size={14} />
        </button>
      </footer>
    </div>
  );
}
