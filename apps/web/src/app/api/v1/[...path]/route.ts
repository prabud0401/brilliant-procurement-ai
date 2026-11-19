import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { verifyCsrf } from "@/lib/csrf";
import {
  SESSION_COOKIE_NAME,
  getSessionCookieOptions,
} from "@/lib/auth/session";
import type { ProblemDetails } from "@/lib/types";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

async function handleProxy(
  request: NextRequest,
  method: string,
  context: RouteContext
): Promise<NextResponse> {
  const { path } = await context.params;
  const pathStr = path.join("/");

  // 1. Intercept auth/login to ensure access token is set in httpOnly cookie and never returned in JSON
  if (pathStr === "auth/login" && method === "POST") {
    const csrf = verifyCsrf("POST", request.headers);
    if (!csrf.valid) {
      return NextResponse.json(csrf.error, {
        status: csrf.error?.status || 403,
        headers: { "Content-Type": "application/problem+json" },
      });
    }

    let credentials: { email?: string; password?: string };
    try {
      credentials = await request.json();
    } catch {
      return NextResponse.json(
        {
          type: "https://pda.example/errors/bad-request",
          title: "Bad Request",
          status: 400,
          code: "MALFORMED_JSON",
          detail: "Invalid JSON in login body.",
        },
        { status: 400, headers: { "Content-Type": "application/problem+json" } }
      );
    }

    const requestId = request.headers.get("x-request-id") || crypto.randomUUID();
    const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";

    try {
      const backendRes = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": requestId,
        },
        body: JSON.stringify(credentials),
      });

      if (!backendRes.ok) {
        const errorJson = await backendRes.json().catch(() => ({
          title: backendRes.statusText || "Unauthorized",
          status: backendRes.status,
          detail: "Login failed",
        }));
        return NextResponse.json(errorJson, {
          status: backendRes.status,
          headers: {
            "Content-Type": "application/problem+json",
            "X-Request-ID": requestId,
          },
        });
      }

      const tokenJson = await backendRes.json();
      const accessToken = tokenJson.access_token;

      // Fetch user data
      const meRes = await fetch(`${apiBaseUrl}/api/v1/me`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "X-Request-ID": requestId,
        },
      });
      const userData = meRes.ok ? await meRes.json() : null;

      const hostHeader = request.headers.get("x-forwarded-host") || request.headers.get("host");
      const cookieOpts = getSessionCookieOptions(hostHeader);

      const resp = NextResponse.json(
        { ok: true, user: userData },
        { status: 200, headers: { "X-Request-ID": requestId } }
      );
      resp.cookies.set(SESSION_COOKIE_NAME, accessToken, cookieOpts);
      return resp;
    } catch {
      return NextResponse.json(
        {
          type: "https://pda.example/errors/api-unreachable",
          title: "API Unreachable",
          status: 503,
          code: "API_UNAVAILABLE",
          detail: "Backend procurement API is currently unreachable.",
          request_id: requestId,
        },
        { status: 503, headers: { "Content-Type": "application/problem+json" } }
      );
    }
  }

  // 2. CSRF Verification for state-changing requests
  const csrf = verifyCsrf(method, request.headers);
  if (!csrf.valid) {
    return NextResponse.json(csrf.error, {
      status: csrf.error?.status || 403,
      headers: { "Content-Type": "application/problem+json" },
    });
  }

  // 3. Resolve request ID
  const requestId = request.headers.get("x-request-id") || crypto.randomUUID();

  // 4. Read session token from cookie
  const cookieStore = await cookies();
  const sessionToken = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  // 5. Construct target URL
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
  const url = new URL(request.url);
  const targetUrl = `${apiBaseUrl}/api/v1/${pathStr}${url.search}`;

  // 6. Build headers to forward
  const forwardHeaders: Record<string, string> = {
    "X-Request-ID": requestId,
  };

  if (sessionToken) {
    forwardHeaders["Authorization"] = `Bearer ${sessionToken}`;
  }

  const contentType = request.headers.get("content-type");
  if (contentType) {
    forwardHeaders["Content-Type"] = contentType;
  }

  const idempotencyKey = request.headers.get("idempotency-key");
  if (idempotencyKey) {
    forwardHeaders["Idempotency-Key"] = idempotencyKey;
  }

  // 7. Extract body if method allows
  let body: BodyInit | undefined = undefined;
  if (!["GET", "HEAD"].includes(method.toUpperCase())) {
    try {
      body = await request.text();
    } catch {
      body = undefined;
    }
  }

  // 8. Forward request to backend FastAPI
  try {
    const apiResponse = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body,
    });

    const respContentType = apiResponse.headers.get("content-type") || "";
    const respHeaders: Record<string, string> = {
      "X-Request-ID": apiResponse.headers.get("x-request-id") || requestId,
    };
    if (respContentType) {
      respHeaders["Content-Type"] = respContentType;
    }

    const responseBody = await apiResponse.text();

    return new NextResponse(responseBody, {
      status: apiResponse.status,
      headers: respHeaders,
    });
  } catch {
    const problem: ProblemDetails = {
      type: "https://pda.example/errors/api-unreachable",
      title: "API Unreachable",
      status: 503,
      code: "API_UNAVAILABLE",
      detail: `Backend procurement API is currently unreachable at ${apiBaseUrl}. Please ensure the service is running.`,
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

export async function GET(request: NextRequest, context: RouteContext) {
  return handleProxy(request, "GET", context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return handleProxy(request, "POST", context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return handleProxy(request, "PUT", context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return handleProxy(request, "PATCH", context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return handleProxy(request, "DELETE", context);
}
