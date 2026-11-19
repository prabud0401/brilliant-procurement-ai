import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  SESSION_COOKIE_NAME,
  isTokenExpired,
} from "@/lib/auth/session";
import type { ProblemDetails } from "@/lib/types";

export async function GET(request: Request) {
  const cookieStore = await cookies();
  const sessionToken = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!sessionToken || isTokenExpired(sessionToken)) {
    const problem: ProblemDetails = {
      type: "https://pda.example/errors/unauthorized",
      title: "Unauthorized",
      status: 401,
      code: "NOT_AUTHENTICATED",
      detail: "No active session or session token has expired.",
    };
    return NextResponse.json(problem, {
      status: 401,
      headers: { "Content-Type": "application/problem+json" },
    });
  }

  const requestId = request.headers.get("x-request-id") || crypto.randomUUID();
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";

  try {
    const meRes = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: {
        Authorization: `Bearer ${sessionToken}`,
        "X-Request-ID": requestId,
      },
    });

    if (!meRes.ok) {
      const errorJson = await meRes.json().catch(() => ({
        type: "https://pda.example/errors/unauthorized",
        title: "Unauthorized",
        status: meRes.status,
        code: "INVALID_SESSION",
        detail: "Session is invalid.",
      }));
      return NextResponse.json(errorJson, {
        status: meRes.status,
        headers: {
          "Content-Type": "application/problem+json",
          "X-Request-ID": requestId,
        },
      });
    }

    const userData = await meRes.json();
    return NextResponse.json(
      { authenticated: true, user: userData },
      {
        status: 200,
        headers: { "X-Request-ID": requestId },
      }
    );
  } catch {
    const problem: ProblemDetails = {
      type: "https://pda.example/errors/api-unreachable",
      title: "API Unreachable",
      status: 503,
      code: "API_UNAVAILABLE",
      detail: "Backend procurement API is currently unreachable.",
      request_id: requestId,
    };
    return NextResponse.json(problem, {
      status: 503,
      headers: { "Content-Type": "application/problem+json" },
    });
  }
}
