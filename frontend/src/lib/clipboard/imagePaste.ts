/**
 * Upload an image blob to the backend and return the asset path.
 */

const API_BASE = "/api/files";

export async function uploadImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/upload/image`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Image upload failed (${res.status}): ${detail}`);
  }

  const data = await res.json();
  return data.path as string; // e.g. "assets/abc123.png"
}
