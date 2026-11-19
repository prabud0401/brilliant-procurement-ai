import type { ProblemDetails } from "./types";

/**
 * CSRF Protection via Origin and Host verification (OWASP Standard for BFF / Modern Web Apps).
 *
 * For state-changing requests (POST, PUT, PATCH, DELETE), this validator compares the
 * Origin (or Referer) header sent by the browser against the expected Host / X-Forwarded-Host.
 * If there is a mismatch or missing Origin on a cross-site attempt, the request is rejected with HTTP 403.
 * Safe methods (GET, HEAD, OPTIONS) bypass CSRF checks.
 */

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export interface CsrfValidationResult {
  valid: boolean;
  error?: ProblemDetails;
}

export function verifyCsrf(
  method: string,
  headers: Headers | Record<string, string | undefined>
): CsrfValidationResult {
  const upperMethod = method.toUpperCase();
  if (SAFE_METHODS.has(upperMethod)) {
    return { valid: true };
  }

  const getHeader = (name: string): string | null => {
    if (typeof (headers as Headers).get === "function") {
      return (headers as Headers).get(name);
    }
    const rec = headers as Record<string, string | undefined>;
    return rec[name.toLowerCase()] ?? rec[name] ?? null;
  };

  const originHeader = getHeader("origin");
  const refererHeader = getHeader("referer");
  const hostHeader = getHeader("x-forwarded-host") || getHeader("host");

  if (!originHeader && !refererHeader) {
    return {
      valid: false,
      error: {
        type: "https://pda.example/errors/csrf-missing",
        title: "Forbidden",
        status: 403,
        code: "CSRF_MISSING",
        detail: "State-changing request missing Origin and Referer headers.",
      },
    };
  }

  const candidateUrl = originHeader || refererHeader!;
  try {
    const parsed = new URL(candidateUrl);
    const originHost = parsed.host; // includes hostname and port if present

    if (!hostHeader) {
      return {
        valid: false,
        error: {
          type: "https://pda.example/errors/csrf-no-host",
          title: "Forbidden",
          status: 403,
          code: "CSRF_FAILED",
          detail: "Unable to verify request target host.",
        },
      };
    }

    // Compare originHost with hostHeader (case-insensitive)
    if (originHost.toLowerCase() !== hostHeader.toLowerCase()) {
      return {
        valid: false,
        error: {
          type: "https://pda.example/errors/csrf-mismatch",
          title: "Forbidden",
          status: 403,
          code: "CSRF_FAILED",
          detail: `Cross-site request forgery detected: origin ${originHost} does not match host ${hostHeader}.`,
        },
      };
    }

    return { valid: true };
  } catch {
    return {
      valid: false,
      error: {
        type: "https://pda.example/errors/csrf-malformed",
        title: "Forbidden",
        status: 403,
        code: "CSRF_FAILED",
        detail: "Malformed Origin or Referer header.",
      },
    };
  }
}
