import { describe, it, expect } from "vitest";
import {
  getSessionCookieOptions,
  decodeJwtPayload,
  isTokenExpired,
} from "@/lib/auth/session";

describe("Session & Cookie Security Helpers", () => {
  describe("getSessionCookieOptions", () => {
    it("returns httpOnly: true, sameSite: 'lax', path: '/'", () => {
      const opts = getSessionCookieOptions("localhost:3000");
      expect(opts.httpOnly).toBe(true);
      expect(opts.sameSite).toBe("lax");
      expect(opts.path).toBe("/");
      expect(opts.maxAge).toBe(3600);
    });

    it("keeps secure: false for localhost even when NODE_ENV is production", () => {
      const originalEnv = process.env.NODE_ENV;
      (process.env as Record<string, string | undefined>).NODE_ENV = "production";
      try {
        const opts = getSessionCookieOptions("localhost:3000");
        expect(opts.secure).toBe(false);

        const opts127 = getSessionCookieOptions("127.0.0.1:3000");
        expect(opts127.secure).toBe(false);

        const opts3015 = getSessionCookieOptions("localhost:3015");
        expect(opts3015.secure).toBe(false);
      } finally {
        (process.env as Record<string, string | undefined>).NODE_ENV = originalEnv;
      }
    });

    it("sets secure: true in production for external hostnames", () => {
      const originalEnv = process.env.NODE_ENV;
      (process.env as Record<string, string | undefined>).NODE_ENV = "production";
      try {
        const opts = getSessionCookieOptions("pda.demo-holdings.example");
        expect(opts.secure).toBe(true);
      } finally {
        (process.env as Record<string, string | undefined>).NODE_ENV = originalEnv;
      }
    });
  });

  describe("decodeJwtPayload", () => {
    it("decodes a valid JWT payload safely without throwing", () => {
      // payload: {"sub":"user-1","roles":["buyer"],"exp":1800000000}
      const token =
        "header." +
        Buffer.from(
          JSON.stringify({
            sub: "user-1",
            roles: ["buyer"],
            exp: 1800000000,
          })
        )
          .toString("base64")
          .replace(/=/g, "") +
        ".signature";

      const payload = decodeJwtPayload(token);
      expect(payload).not.toBeNull();
      expect(payload?.sub).toBe("user-1");
      expect(payload?.roles).toEqual(["buyer"]);
      expect(payload?.exp).toBe(1800000000);
    });

    it("returns null for malformed tokens", () => {
      expect(decodeJwtPayload("not-a-jwt")).toBeNull();
      expect(decodeJwtPayload("header.invalid-base64.signature")).toBeNull();
    });
  });

  describe("isTokenExpired", () => {
    it("returns false for token expiring in the future", () => {
      const futureExp = Math.floor(Date.now() / 1000) + 3600;
      const token =
        "header." +
        Buffer.from(JSON.stringify({ exp: futureExp })).toString("base64") +
        ".sig";
      expect(isTokenExpired(token)).toBe(false);
    });

    it("returns true for token expired in the past", () => {
      const pastExp = Math.floor(Date.now() / 1000) - 3600;
      const token =
        "header." +
        Buffer.from(JSON.stringify({ exp: pastExp })).toString("base64") +
        ".sig";
      expect(isTokenExpired(token)).toBe(true);
    });

    it("returns true for malformed token or missing exp", () => {
      expect(isTokenExpired("invalid")).toBe(true);
    });
  });
});
