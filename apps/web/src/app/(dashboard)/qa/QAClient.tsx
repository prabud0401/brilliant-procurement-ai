"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import {
  HelpCircle,
  Send,
  Sparkles,
  ExternalLink,
  AlertCircle,
  RotateCcw,
  FileText,
  User,
  Bot,
  AlertTriangle,
} from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import type { UserPrincipal } from "@/lib/types";

export interface Citation {
  document_id: string;
  title: string;
  page: number;
  chunk_id: string;
}

export interface AnswerItem {
  text: string;
  citations: Citation[];
}

export interface QuestionResponse {
  answer: AnswerItem[];
  refused: boolean;
  refusal_reason: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text?: string;
  answerItems?: AnswerItem[];
  refused?: boolean;
  refusalReason?: string;
  timestamp: Date;
}

const SAMPLE_QUESTIONS = [
  "What is the total amount and VAT on quote Q-1042?",
  "What are the payment terms offered by Gulf Line IT Trading?",
  "Which vendor provided the quotation for server hardware?",
  "What is the warranty period specified for the equipment?",
];

export function QAClient({ user }: { user: UserPrincipal | null }) {
  const toast = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === "function") {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const questionText = input.trim();
    if (!questionText || isLoading) return;

    if (questionText.length > 500) {
      toast.error("Question exceeds maximum length of 500 characters");
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: questionText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetch("/api/v1/qa/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ question: questionText }),
      });

      if (!res.ok) {
        const errorJson = await res.json().catch(() => ({}));
        const detail =
          errorJson.detail ||
          errorJson.title ||
          "Failed to retrieve an answer from the procurement assistant.";

        setErrorMsg(detail);
        toast.error(detail);

        const assistantError: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          refused: true,
          refusalReason: detail,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantError]);
        return;
      }

      const data: QuestionResponse = await res.json();

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        refused: data.refused,
        refusalReason: data.refusal_reason || undefined,
        answerItems: data.answer || [],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      const msg = "Backend procurement API is currently unreachable. Please check your connection.";
      setErrorMsg(msg);
      toast.error(msg);

      const networkError: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        refused: true,
        refusalReason: msg,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, networkError]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const clearSession = () => {
    setMessages([]);
    setErrorMsg(null);
    setInput("");
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-10rem)] max-w-5xl flex-col">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Document Assistant Q&A
            </h1>
            <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
              Grounded AI
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Ask questions grounded strictly in procurement documents you have access to.
          </p>
        </div>

        {messages.length > 0 && (
          <button
            type="button"
            onClick={clearSession}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Clear Session
          </button>
        )}
      </div>

      {/* Chat conversation area */}
      <div className="flex-1 overflow-y-auto py-6 space-y-6">
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl text-center py-12 px-4">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
              <Sparkles className="h-7 w-7" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-slate-900">
              Ask about your procurement documents
            </h2>
            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              Inquire about quotes, pricing terms, invoice totals, or PO lines. Every response provides
              verifiable citations linking directly to the cited document page.
            </p>

            <div className="mt-8 text-left">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
                Suggested Questions
              </p>
              <div className="space-y-2">
                {SAMPLE_QUESTIONS.map((q, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setInput(q);
                      textareaRef.current?.focus();
                    }}
                    className="w-full text-left rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-700 shadow-sm hover:border-blue-400 hover:bg-blue-50/50 transition-colors flex items-center justify-between group"
                  >
                    <span>{q}</span>
                    <HelpCircle className="h-4 w-4 text-slate-400 group-hover:text-blue-500 shrink-0 ml-2" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3.5 ${
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            }`}
          >
            {/* Avatar icon */}
            <div
              className={`flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full text-xs font-medium shadow-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-white"
              }`}
            >
              {msg.role === "user" ? (
                <User className="h-4 w-4" />
              ) : (
                <Bot className="h-4 w-4" />
              )}
            </div>

            {/* Bubble / Card */}
            <div
              className={`max-w-2xl rounded-2xl px-4 py-3 shadow-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-tr-none"
                  : "bg-white border border-slate-200 text-slate-800 rounded-tl-none"
              }`}
            >
              {msg.role === "user" ? (
                <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
              ) : msg.refused ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-amber-600 font-semibold text-sm">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>Unable to Answer</span>
                  </div>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {msg.refusalReason ||
                      "I could not find an answer in the accessible procurement documents."}
                  </p>
                  <p className="text-xs text-slate-500">
                    The assistant refuses questions when no supporting evidence exists in authorized
                    documents or when asked out-of-scope topics.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Render Answer items with numbered citations */}
                  <div className="space-y-2.5">
                    {msg.answerItems?.map((item, idx) => (
                      <p key={idx} className="text-sm text-slate-800 leading-relaxed">
                        {item.text}
                        {item.citations.length > 0 && (
                          <span className="ml-1 inline-flex items-center gap-1">
                            {item.citations.map((c, cIdx) => (
                              <Link
                                key={cIdx}
                                href={`/documents/${c.document_id}?page=${c.page}&highlight=${encodeURIComponent(
                                  c.chunk_id
                                )}`}
                                className="inline-flex items-center rounded bg-blue-50 px-1.5 py-0.5 text-[11px] font-semibold text-blue-600 hover:bg-blue-100 hover:text-blue-800 transition-colors"
                                title={`Open ${c.title}, page ${c.page}`}
                              >
                                [{cIdx + 1}]
                              </Link>
                            ))}
                          </span>
                        )}
                      </p>
                    ))}
                  </div>

                  {/* Supporting citations list */}
                  {msg.answerItems &&
                    msg.answerItems.flatMap((i) => i.citations).length > 0 && (
                      <div className="mt-4 border-t border-slate-100 pt-3">
                        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                          Supporting Citations
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {Array.from(
                            new Map(
                              msg.answerItems
                                .flatMap((i) => i.citations)
                                .map((c) => [`${c.document_id}-${c.page}-${c.chunk_id}`, c])
                            ).values()
                          ).map((citation, cIdx) => (
                            <Link
                              key={cIdx}
                              href={`/documents/${citation.document_id}?page=${
                                citation.page
                              }&highlight=${encodeURIComponent(citation.chunk_id)}`}
                              className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors shadow-2xs"
                            >
                              <FileText className="h-3.5 w-3.5 text-blue-600" />
                              <span>
                                {citation.title || "Document"}, p. {citation.page}
                              </span>
                              <ExternalLink className="h-3 w-3 text-slate-400" />
                            </Link>
                          ))}
                        </div>
                      </div>
                    )}
                </div>
              )}

              <p
                className={`mt-1.5 text-[10px] ${
                  msg.role === "user" ? "text-blue-200 text-right" : "text-slate-400"
                }`}
              >
                {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start gap-3.5">
            <div className="flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-full bg-slate-800 text-white text-xs font-medium shadow-sm">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-2xl rounded-tl-none border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2.5">
                <div className="flex space-x-1">
                  <div className="h-2 w-2 rounded-full bg-blue-600 animate-bounce [animation-delay:-0.3s]" />
                  <div className="h-2 w-2 rounded-full bg-blue-600 animate-bounce [animation-delay:-0.15s]" />
                  <div className="h-2 w-2 rounded-full bg-blue-600 animate-bounce" />
                </div>
                <span className="text-xs text-slate-500">
                  Retrieving relevant document chunks and grounding citations...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input box */}
      <div className="border-t border-slate-200 bg-white pt-3">
        {errorMsg && (
          <div className="mb-2 flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="font-semibold text-rose-800 hover:text-rose-900"
            >
              Dismiss
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="relative">
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about quotes, invoices, or POs (e.g., 'What is the total on quote Q-1042?')..."
            maxLength={500}
            className="w-full resize-none rounded-xl border border-slate-300 py-3 pl-4 pr-24 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
            disabled={isLoading}
          />

          <div className="absolute right-3 bottom-3 flex items-center gap-2">
            <span
              className={`text-[11px] font-mono ${
                input.length > 450 ? "text-amber-600 font-bold" : "text-slate-400"
              }`}
            >
              {input.length}/500
            </span>
            <button
              type="submit"
              disabled={!input.trim() || isLoading || input.length > 500}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm hover:bg-blue-500 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
              aria-label="Send question"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
        <p className="mt-1 text-center text-[11px] text-slate-400">
          Answers generated from accessible documents with citation grounding. Do not enter personal credentials.
        </p>
      </div>
    </div>
  );
}
