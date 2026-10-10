import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Volume2 } from 'lucide-react';

type Reply = { id: string };
type Props = {
  disabled: boolean;
  send: (text: string) => Promise<Reply | undefined>;
  fetchApi: (path: string, options?: RequestInit) => Promise<Response>;
};

export function VoiceConversation({ disabled, send, fetchApi }: Props) {
  const [phase, setPhase] = useState('idle');
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');
  const running = useRef(false);
  const generation = useRef(0);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef('');
  const context = useRef<AudioContext | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const abort = useRef<AbortController | null>(null);
  const sender = useRef(send);
  sender.current = send;

  function clearAudio() {
    if (audio.current) {
      audio.current.pause();
      audio.current.onended = null;
      audio.current.onerror = null;
      audio.current = null;
    }
    if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    audioUrl.current = '';
  }
  function releaseInput() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    if (recorder.current?.state === 'recording') recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    void context.current?.close();
    context.current = null;
  }
  function stop() {
    running.current = false;
    generation.current += 1;
    abort.current?.abort();
    releaseInput();
    clearAudio();
    setPhase('idle');
  }
  useEffect(() => () => stop(), []);

  async function process(blob: Blob, turn: number) {
    if (!running.current || turn !== generation.current) return;
    try {
      setPhase('transcribing');
      abort.current = new AbortController();
      const body = new FormData();
      body.append('file', blob, 'voice.webm');
      const response = await fetchApi('/voice/transcribe', {
        method: 'POST',
        body,
        signal: abort.current.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Speech recognition failed.');
      if (!running.current || turn !== generation.current) return;
      setTranscript(data.text);
      setPhase('thinking');
      const reply = await sender.current(data.text);
      if (!running.current || turn !== generation.current) return;
      if (!reply) throw new Error('The question could not be completed.');
      setPhase('preparing speech');
      const spoken = await fetchApi(`/voice/speak/${reply.id}`, {
        method: 'POST',
        signal: abort.current.signal,
      });
      if (!spoken.ok) {
        const detail = await spoken.json();
        throw new Error(detail.detail || 'Speech synthesis failed.');
      }
      const bytes = await spoken.blob();
      if (!running.current || turn !== generation.current) return;
      audioUrl.current = URL.createObjectURL(bytes);
      const player = new Audio(audioUrl.current);
      audio.current = player;
      player.onended = () => {
        clearAudio();
        if (running.current && turn === generation.current) void listen(turn);
      };
      player.onerror = () => {
        stop();
        setError('The browser could not play the reply. Try starting voice again.');
      };
      setPhase('speaking');
      await player.play();
    } catch (caught) {
      if (!running.current || turn !== generation.current) return;
      stop();
      setError((caught as Error).message);
    }
  }

  async function listen(turn: number) {
    try {
      const input = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      if (!running.current || turn !== generation.current) {
        input.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = input;
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((type) =>
        MediaRecorder.isTypeSupported(type),
      );
      const capture = new MediaRecorder(input, mimeType ? { mimeType } : undefined);
      recorder.current = capture;
      const chunks: BlobPart[] = [];
      capture.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      let heardSpeech = false;
      capture.onstop = () => {
        if (!running.current || turn !== generation.current) return;
        if (!heardSpeech) {
          stop();
          setError('No speech detected. Start voice and speak close to your microphone.');
          return;
        }
        void process(new Blob(chunks, { type: capture.mimeType }), turn);
      };
      const meter = new AudioContext();
      context.current = meter;
      await meter.resume();
      const analyser = meter.createAnalyser();
      analyser.fftSize = 1024;
      meter.createMediaStreamSource(input).connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      const started = Date.now();
      let lastSpeech = started;
      setPhase('listening');
      capture.start(250);
      timer.current = setInterval(() => {
        analyser.getFloatTimeDomainData(samples);
        const energy = Math.sqrt(
          samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length,
        );
        if (energy > 0.02) {
          heardSpeech = true;
          lastSpeech = Date.now();
        }
        if ((heardSpeech && Date.now() - lastSpeech > 1400) || Date.now() - started > 25000)
          releaseInput();
      }, 100);
    } catch (caught) {
      if (!running.current || turn !== generation.current) return;
      stop();
      setError(
        (caught as Error).name === 'NotAllowedError'
          ? 'Microphone permission was denied. Allow it in your browser, then try again.'
          : (caught as Error).message,
      );
    }
  }
  function start() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError('Microphone capture needs a supported browser on HTTPS or localhost.');
      return;
    }
    setError('');
    running.current = true;
    generation.current += 1;
    setPhase('opening microphone');
    void listen(generation.current);
  }
  function interrupt() {
    clearAudio();
    generation.current += 1;
    void listen(generation.current);
  }

  return (
    <div className="voice-conversation">
      <div className="voice-controls">
        {phase === 'idle' ? (
          <button type="button" className="text-button" onClick={start} disabled={disabled}>
            <Mic size={16} /> Start voice
          </button>
        ) : (
          <>
            <span className="voice-phase" role="status">
              <span className="tiny-dot" />
              {phase}
            </span>
            {phase === 'listening' && (
              <button type="button" className="text-button" onClick={releaseInput}>
                Send now
              </button>
            )}
            {phase === 'speaking' && (
              <button type="button" className="text-button" onClick={interrupt}>
                <Volume2 size={14} /> Interrupt & speak
              </button>
            )}
            <button type="button" className="text-button" onClick={stop}>
              <Square size={13} /> End voice
            </button>
          </>
        )}
      </div>
      <small>Speak, then pause. Replies play aloud; the microphone reopens after each reply.</small>
      {transcript && <p className="voice-transcript">Heard: {transcript}</p>}
      {error && (
        <p role="alert" className="voice-error">
          {error}
        </p>
      )}
    </div>
  );
}
