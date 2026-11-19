import { describe, it, expect } from "vitest";
import { verifyCsrf } from "@/lib/csrf";

describe("CSRF Protection via Origin and Host Verification", () => {
  it("allows safe HTTP methods without Origin or Referer", () => {
    const safeMethods = ["GET", "HEAD", "OPTIONS"];
    for (const method of safeMethods) {
      const result = verifyCsrf(method, {});
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    }
  });

  it("rejects state-changing methods when both Origin and Referer are missing", () => {
    const stateMethods = ["POST", "PUT", "PATCH", "DELETE"];
    for (const method of stateMethods) {
      const result = verifyCsrf(method, { host: "localhost:3000" });
      expect(result.valid).toBe(false);
      expect(result.error?.status).toBe(403);
      expect(result.error?.code).toBe("CSRF_MISSING");
    }
  });

  it("accepts state-changing request when Origin matches Host header", () => {
    const headers = {
      origin: "http://localhost:3000",
      host: "localhost:3000",
    };
    const result = verifyCsrf("POST", headers);
    expect(result.valid).toBe(true);
  });

  it("accepts state-changing request when Origin matches X-Forwarded-Host header", () => {
    const headers = {
      origin: "https://pda.demo-holdings.example",
      "x-forwarded-host": "pda.demo-holdings.example",
    };
    const result = verifyCsrf("POST", headers);
    expect(result.valid).toBe(true);
  });

  it("accepts state-changing request with matching Referer when Origin is absent", () => {
    const headers = {
      referer: "http://localhost:3000/login",
      host: "localhost:3000",
    };
    const result = verifyCsrf("POST", headers);
    expect(result.valid).toBe(true);
  });

  it("rejects state-changing request when Origin does not match Host (cross-site attempt)", () => {
    const headers = {
      origin: "https://malicious-site.example",
      host: "localhost:3000",
    };
    const result = verifyCsrf("POST", headers);
    expect(result.valid).toBe(false);
    expect(result.error?.status).toBe(403);
    expect(result.error?.code).toBe("CSRF_FAILED");
    expect(result.error?.detail).toContain("Cross-site request forgery detected");
  });

  it("rejects malformed Origin or Referer URL", () => {
    const headers = {
      origin: "not-a-valid-url",
      host: "localhost:3000",
    };
    const result = verifyCsrf("POST", headers);
    expect(result.valid).toBe(false);
    expect(result.error?.status).toBe(403);
    expect(result.error?.code).toBe("CSRF_FAILED");
  });
});
