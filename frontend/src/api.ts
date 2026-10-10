import { Client } from '@gradio/client';
let sessionPromise: Promise<string> | null = null;
let rejectedToken: string | null = null;
export let zeroGpu = false;
let computeClient: Promise<Client> | null = null;
async function visitorToken() {
  if (!sessionPromise)
    sessionPromise = (async () => {
      const existing = localStorage.getItem('evidra.session');
      if (existing && Number(existing.split('.')[1]) * 1000 > Date.now()) return existing;
      const response = await fetch('/api/session', { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not start a demo session.');
      if (data.token) localStorage.setItem('evidra.session', data.token);
      else localStorage.removeItem('evidra.session');
      return data.token as string;
    })().catch((error) => {
      sessionPromise = null;
      throw error;
    });
  return sessionPromise;
}
export async function fetchApi(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers);
  const token = await visitorToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (response.status === 401 && retry) {
    // Parallel startup requests must share one replacement session after restart.
    if (rejectedToken !== token) {
      rejectedToken = token;
      localStorage.removeItem('evidra.session');
      sessionPromise = null;
    }
    return fetchApi(path, options, false);
  }
  return response;
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
  onStatus?: (message: string) => void,
): Promise<T> {
  if (zeroGpu && options.method === 'POST' && ['/questions', '/evaluations'].includes(path)) {
    const token = await visitorToken();
    if (!computeClient)
      computeClient = Client.connect(`${window.location.origin}/compute`, {
        events: ['data', 'status'],
      }).catch((error) => {
        computeClient = null;
        throw error;
      });
    const client = await computeClient;
    const job = client.submit(path === '/questions' ? '/ask' : '/evaluate', [
      token,
      JSON.parse(String(options.body)),
    ]);
    const cancel = () => {
      void job.cancel();
    };
    options.signal?.addEventListener('abort', cancel, { once: true });
    let data: { ok: boolean; result?: T; error?: string }[] = [];
    try {
      for await (const event of job) {
        if (options.signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
        if (event.type === 'data') data = event.data as typeof data;
        if (event.type === 'status') {
          if (event.stage === 'error')
            throw new Error(
              typeof event.message === 'string' ? event.message : 'The model request failed.',
            );
          onStatus?.(
            event.stage === 'pending'
              ? event.position != null
                ? `Waiting in queue · position ${event.position + 1}`
                : 'Waiting for a free GPU'
              : 'Finding your answer',
          );
        }
      }
    } finally {
      options.signal?.removeEventListener('abort', cancel);
    }
    if (!data[0]?.ok)
      throw new Error(data[0]?.error || 'The GPU queue could not complete this request.');
    return data[0].result as T;
  }
  const response = await fetchApi(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'The request did not complete.' }));
    throw new Error(
      typeof body.detail === 'string' ? body.detail : 'Please check your input and try again.',
    );
  }
  const result = await response.json();
  if (path === '/health') zeroGpu = Boolean(result.zero_gpu);
  return result;
}
export const json = (body: unknown) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});
