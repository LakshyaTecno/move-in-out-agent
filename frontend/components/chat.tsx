"use client";

import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";

import { api, type ChatMessage, type MoveRequest } from "@/lib/api";

const SUGGESTIONS = [
  "What documents do I need?",
  "Which slots are free next weekend?",
  "What's the status of my request?",
];

export function Chat({ requestId, onRequestUpdate }: { requestId: string; onRequestUpdate: (r: MoveRequest) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [notice, setNotice] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.chatHistory(requestId).then(setMessages).catch(() => {});
  }, [requestId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, thinking]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || thinking) return;
    setInput("");
    setNotice("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setThinking(true);
    try {
      // One silent retry: the first call after the free host wakes up can time out.
      const { reply, request } = await api.chat(requestId, message).catch(() => api.chat(requestId, message));
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
      onRequestUpdate(request);
    } catch (e) {
      setNotice(`${(e as Error).message} You can keep going with the form on the right.`);
    } finally {
      setThinking(false);
    }
  }

  return (
    <section className="flex h-[70vh] min-h-[420px] flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700">Move assistant</div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                m.role === "user" ? "bg-brand text-white" : "bg-slate-100 text-slate-800"
              }`}
            >
              {m.role === "assistant" ? (
                <div className="chat-md">
                  <Markdown>{m.content}</Markdown>
                </div>
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        {thinking && <div className="text-sm text-slate-400">Assistant is working on it…</div>}
        {notice && <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">{notice}</div>}
        <div ref={endRef} />
      </div>
      {messages.length <= 1 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 hover:border-brand hover:text-brand"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="flex gap-2 border-t border-slate-100 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. I'm renting B-302, moving in next Saturday morning"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand focus:outline-none"
        />
        <button
          disabled={thinking || !input.trim()}
          className="rounded-lg bg-brand px-4 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </section>
  );
}
