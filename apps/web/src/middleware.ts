import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME, decodeJwtPayload } from "@/lib/auth/session";

const PUBLIC_PATHS = [
  "/login",
  "/api/auth/login",
  "/api/v1/auth/login",
  "/favicon.ico",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Allow Next.js internal static assets and public paths
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/static") ||
    PUBLIC_PATHS.includes(pathname) ||
    pathname.match(/\.(png|jpg|jpeg|svg|ico|css|js|woff|woff2)$/)
  ) {
    // If authenticated user visits /login, redirect to home
    if (pathname === "/login") {
      const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
      if (token) {
        const payload = decodeJwtPayload(token);
        const now = Math.floor(Date.now() / 1000);
        if (payload && typeof payload.exp === "number" && payload.exp > now) {
          return NextResponse.redirect(new URL("/", request.url));
        }
      }
    }
    return addSecurityHeaders(NextResponse.next());
  }

  // 2. Auth guard for protected routes
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;

  // Unauthenticated -> redirect to /login
  if (!token) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        {
          type: "https://pda.example/errors/unauthorized",
          title: "Unauthorized",
          status: 401,
          code: "NOT_AUTHENTICATED",
          detail: "Authentication required to access this endpoint.",
        },
        { status: 401, headers: { "Content-Type": "application/problem+json" } }
      );
    }
    const loginUrl = new URL("/login", request.url);
    if (pathname !== "/") {
      loginUrl.searchParams.set("from", pathname);
    }
    return addSecurityHeaders(NextResponse.redirect(loginUrl));
  }

  // Validate token payload and expiration
  const payload = decodeJwtPayload(token);
  const now = Math.floor(Date.now() / 1000);

  if (!payload) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("error", "invalid_session");
    const resp = NextResponse.redirect(loginUrl);
    resp.cookies.set(SESSION_COOKIE_NAME, "", { maxAge: 0, path: "/" });
    return addSecurityHeaders(resp);
  }

  if (typeof payload.exp === "number" && payload.exp <= now) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("error", "session_expired");
    const resp = NextResponse.redirect(loginUrl);
    resp.cookies.set(SESSION_COOKIE_NAME, "", { maxAge: 0, path: "/" });
    return addSecurityHeaders(resp);
  }

  return addSecurityHeaders(NextResponse.next());
}

function addSecurityHeaders(response: NextResponse): NextResponse {
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self'",
      "frame-ancestors 'none'",
    ].join("; ")
  );
  if (process.env.NODE_ENV === "production") {
    response.headers.set(
      "Strict-Transport-Security",
      "max-age=31536000; includeSubDomains"
    );
  }
  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     */
    "/((?!_next/static|_next/image).*)",
  ],
};
