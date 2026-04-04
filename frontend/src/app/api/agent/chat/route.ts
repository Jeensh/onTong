/**
 * Streaming SSE proxy for /api/agent/chat.
 *
 * Next.js rewrites buffer chunked responses, breaking real-time SSE.
 * This route handler streams the backend response byte-by-byte so
 * thinking_step / content_delta events arrive instantly on external
 * clients (ngrok, LAN).
 */

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

export async function POST(request: Request) {
  const body = await request.text();

  const upstream = await fetch(`${BACKEND_URL}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Pipe the SSE stream through without buffering
  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstream.body!.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          controller.enqueue(value);
        }
      } catch {
        // client disconnected
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
