import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import type { ProblemDetails } from "@/lib/types";

export interface ErrorStateProps {
  error?: ProblemDetails | Error | string | null;
  title?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  error,
  title,
  onRetry,
  className = "",
}) => {
  let displayTitle = title || "An error occurred";
  let displayDetail: string | undefined = undefined;
  let errorCode: string | undefined = undefined;
  let requestId: string | undefined = undefined;
  let status: number | undefined = undefined;

  if (typeof error === "string") {
    displayDetail = error;
  } else if (error && "title" in error && typeof error.title === "string") {
    const problem = error as ProblemDetails;
    displayTitle = title || problem.title;
    displayDetail = problem.detail;
    errorCode = problem.code;
    requestId = problem.request_id;
    status = problem.status;
  } else if (error instanceof Error) {
    displayDetail = error.message;
  }

  return (
    <div
      className={`rounded-lg border border-rose-200 bg-rose-50/70 p-6 text-slate-800 ${className}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-600">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-rose-900">
              {displayTitle}
            </h3>
            {status && (
              <span className="rounded bg-rose-200/80 px-1.5 py-0.5 text-xs font-mono font-medium text-rose-800">
                HTTP {status}
              </span>
            )}
            {errorCode && (
              <span className="rounded bg-rose-200/80 px-1.5 py-0.5 text-xs font-mono font-medium text-rose-800">
                {errorCode}
              </span>
            )}
          </div>

          {displayDetail && (
            <p className="mt-1.5 text-sm text-rose-800 leading-relaxed">
              {displayDetail}
            </p>
          )}

          {requestId && (
            <div className="mt-3 flex items-center gap-2 text-xs text-rose-600">
              <span className="font-medium text-slate-500">Request ID:</span>
              <code className="rounded bg-rose-100/70 px-1.5 py-0.5 font-mono text-[11px] text-rose-900">
                {requestId}
              </code>
            </div>
          )}

          {onRetry && (
            <div className="mt-4">
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-rose-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Retry Request
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
