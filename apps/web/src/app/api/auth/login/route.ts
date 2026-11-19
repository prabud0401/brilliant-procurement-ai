import { NextResponse } from "next/server";
import { verifyCsrf } from "@/lib/csrf";
import {
  SESSION_COOKIE_NAME,
  getSessionCookieOptions,
} from "@/lib/auth/session";
import type { ProblemDetails } from "@/lib/types";

export async function POST(request: Request) {
  // 1. CSRF Verification
  const csrf = verifyCsrf("POST", request.headers);
  if (!csrf.valid) {
    return NextResponse.json(csrf.error, {
      status: csrf.error?.status || 403,
      headers: { "Content-Type": "application/problem+json" },
    });
  }

  // 2. Parse credentials
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    const problem: ProblemDetails = {
      type: "https://pda.example/errors/bad-request",
      title: "Bad Request",
      status: 400,
      code: "MALFORMED_JSON",
      detail: "Invalid JSON payload in request body.",
    };
    return NextResponse.json(problem, {
      status: 400,
      headers: { "Content-Type": "application/problem+json" },
    });
  }

  const { email, password } = body;
  if (!email || !password) {
    const problem: ProblemDetails = {
      type: "https://pda.example/errors/validation",
      title: "Validation Error",
      status: 422,
      code: "MISSING_CREDENTIALS",
      detail: "Both email and password are required.",
    };
    return NextResponse.json(problem, {
      status: 422,
      headers: { "Content-Type": "application/problem+json" },
    });
  }

  const requestId = request.headers.get("x-request-id") || crypto.randomUUID();
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";

  // 3. Authenticate with backend FastAPI
  try {
    const apiRes = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify({ email, password }),
    });

    if (!apiRes.ok) {
      const errorData = await apiRes.json().catch(() => ({
        type: "https://pda.example/errors/login-failed",
        title: apiRes.statusText || "Authentication Failed",
        status: apiRes.status,
        code: "INVALID_CREDENTIALS",
        detail: "Invalid email or password",
        request_id: requestId,
      }));
      return NextResponse.json(errorData, {
        status: apiRes.status,
        headers: {
          "Content-Type": "application/problem+json",
          "X-Request-ID": requestId,
        },
      });
    }

    const tokenData = await apiRes.json();
    const accessToken = tokenData.access_token;

    if (!accessToken) {
      const problem: ProblemDetails = {
        type: "https://pda.example/errors/server-error",
        title: "Internal Server Error",
        status: 500,
        code: "TOKEN_MISSING",
        detail: "API login response did not contain an access token.",
        request_id: requestId,
      };
      return NextResponse.json(problem, {
        status: 500,
        headers: { "Content-Type": "application/problem+json" },
      });
    }

    // 4. Fetch user details from /api/v1/me using the token
    const meRes = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Request-ID": requestId,
      },
    });

    let userData = null;
    if (meRes.ok) {
      userData = await meRes.json();
    }

    // 5. Build response without exposing the token in JSON
    const hostHeader = request.headers.get("x-forwarded-host") || request.headers.get("host");
    const cookieOptions = getSessionCookieOptions(hostHeader);

    const response = NextResponse.json(
      {
        ok: true,
        user: userData,
      },
      {
        status: 200,
        headers: {
          "X-Request-ID": requestId,
        },
      }
    );

    // 6. Set httpOnly, Secure, SameSite=Lax cookie
    response.cookies.set(SESSION_COOKIE_NAME, accessToken, cookieOptions);

    return response;
  } catch {
    const problem: ProblemDetails = {
      type: "https://pda.example/errors/api-unreachable",
      title: "API Unreachable",
      status: 503,
      code: "API_UNAVAILABLE",
      detail: "Backend procurement API is currently unreachable. Please verify the service is running.",
      request_id: requestId,
    };
    return NextResponse.json(problem, {
      status: 503,
      headers: {
        "Content-Type": "application/problem+json",
        "X-Request-ID": requestId,
      },
    });
  }
}
