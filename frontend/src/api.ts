import type { Paper } from "./types";

const API = "/api";

export async function sendChat(payload: {
  message: string;
  year: number | null;
  count: number;
  selected_paper: Paper | null;
  history: { role: string; content: string }[];
}) {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Chat request failed");
  }
  return res.json() as Promise<{
    kind: string;
    reply: string;
    topics: string[];
    papers: Paper[];
    search_query: string;
    year: number | null;
    count: number | null;
  }>;
}
