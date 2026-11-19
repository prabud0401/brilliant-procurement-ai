export const SESSION_COOKIE_NAME = "pda_session";

/**
 * Parses and returns secure cookie options.
 * The cookie is httpOnly, SameSite=Lax, and Secure in production (except on plain-http localhost).
 */
export function getSessionCookieOptions(hostHeader?: string | null): {
  httpOnly: boolean;
  sameSite: "lax" | "strict" | "none";
  secure: boolean;
  path: string;
  maxAge: number;
} {
  const isProd = process.env.NODE_ENV === "production";
  const hostname = (hostHeader || "").split(":")[0].toLowerCase();
  const isLocalhost = !hostname || hostname === "localhost" || hostname === "127.0.0.1";

  // COOKIE_SECURE=true|false overrides; otherwise Secure in production except on localhost.
  const override = process.env.COOKIE_SECURE;
  const secure =
    override === "true" ? true : override === "false" ? false : isProd && !isLocalhost;

  return {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: 60 * 60, // 1 hour (FastAPI token TTL)
  };
}

/**
 * Safely decodes base64url JWT payload without throwing.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = Buffer.from(base64, "base64").toString("utf8");
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

/**
 * Checks whether a given JWT string has expired based on its 'exp' claim.
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") {
    return true;
  }
  // Allow a 10-second clock skew buffer
  const nowInSeconds = Math.floor(Date.now() / 1000);
  return payload.exp <= nowInSeconds + 10;
}
