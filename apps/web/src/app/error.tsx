"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Structured error logging without dumping credentials or raw secrets
    console.error("[PDA Web Error Boundary]", {
      message: error.message,
      digest: error.digest,
    });
  }, [error]);

  const isApiUnreachable =
    error.message.includes("unreachable") ||
    error.message.includes("ECONNREFUSED") ||
    error.message.includes("fetch failed");

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-12 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-100 text-rose-600">
        <AlertTriangle className="h-8 w-8" aria-hidden="true" />
      </div>

      <h1 className="mt-6 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
        {isApiUnreachable
          ? "Procurement API Service Unreachable"
          : "Something went wrong"}
      </h1>

      <p className="mt-2 max-w-md text-sm text-slate-600 leading-relaxed">
        {isApiUnreachable
          ? "The web application is currently unable to communicate with the backend procurement API. Please ensure the backend container or server is running."
          : "An unexpected error occurred while processing your request. Please try again or return to the home page."}
      </p>

      {error.digest && (
        <p className="mt-3 text-xs font-mono text-slate-400">
          Digest: {error.digest}
        </p>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          type="button"
          onClick={() => reset()}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Try Again
        </button>

        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          <Home className="h-4 w-4" aria-hidden="true" />
          Go to Home
        </Link>
      </div>
    </div>
  );
}
