import { NextResponse } from "next/server";
import { verifyCsrf } from "@/lib/csrf";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";

export async function POST(request: Request) {
  const csrf = verifyCsrf("POST", request.headers);
  if (!csrf.valid) {
    return NextResponse.json(csrf.error, {
      status: csrf.error?.status || 403,
      headers: { "Content-Type": "application/problem+json" },
    });
  }

  const response = NextResponse.json({ ok: true }, { status: 200 });

  // Expire and clear the session cookie
  response.cookies.set(SESSION_COOKIE_NAME, "", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
    expires: new Date(0),
  });

  return response;
}
