import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { GET as healthzGET } from "@/app/healthz/route";
import { GET as readyzGET } from "@/app/readyz/route";
import { middleware } from "@/middleware";

describe("Health and Readiness Probes", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("healthz returns 200 ok unconditionally", async () => {
    const res = await healthzGET();
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toEqual({ status: "ok" });
  });

  it("readyz returns 200 when backend answers 200", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: "ready" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    const res = await readyzGET();
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/readyz$/),
      expect.objectContaining({
        cache: "no-store",
      })
    );
  });

  it("readyz returns 503 when backend returns non-200", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ status: "not ready" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      })
    );

    const res = await readyzGET();
    expect(res.status).toBe(503);
    const data = await res.json();
    expect(data.status).toBe("unavailable");
  });

  it("readyz returns 503 when backend fetch fails", async () => {
    fetchMock.mockRejectedValue(new Error("Network connection refused"));

    const res = await readyzGET();
    expect(res.status).toBe(503);
    const data = await res.json();
    expect(data.status).toBe("unavailable");
  });

  it("middleware allows /healthz and /readyz without authentication", () => {
    const reqHealth = new NextRequest("http://localhost:3000/healthz");
    const resHealth = middleware(reqHealth);
    expect(resHealth.status).toBe(200);
    expect(resHealth.headers.get("location")).toBeNull();

    const reqReady = new NextRequest("http://localhost:3000/readyz");
    const resReady = middleware(reqReady);
    expect(resReady.status).toBe(200);
    expect(resReady.headers.get("location")).toBeNull();
  });
});
