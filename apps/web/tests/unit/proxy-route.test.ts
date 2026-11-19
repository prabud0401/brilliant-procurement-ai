import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";

vi.mock("next/headers", () => ({
  cookies: async () => ({ get: () => ({ value: "test-session-token" }) }),
}));

import { GET, POST } from "@/app/api/v1/[...path]/route";

const ctx = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("BFF proxy route", () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("refuses dot segments so only /api/v1/* is reachable", async () => {
    const req = new NextRequest("http://localhost:3000/api/v1/x");
    const res = await GET(req, ctx(["..", "healthz"]));
    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("passes binary upload bodies and binary responses through unchanged", async () => {
    const bytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0xff, 0x00, 0xe2, 0x80]);
    fetchMock.mockResolvedValue(
      new Response(bytes, {
        status: 200,
        headers: { "content-type": "application/pdf", "content-disposition": "inline" },
      })
    );
    const req = new NextRequest("http://localhost:3000/api/v1/documents", {
      method: "POST",
      body: bytes,
      headers: {
        "content-type": "multipart/form-data; boundary=x",
        origin: "http://localhost:3000",
        host: "localhost:3000",
      },
    });
    const res = await POST(req, ctx(["documents"]));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/documents$/);
    expect(new Uint8Array(init.body as ArrayBuffer)).toEqual(bytes);
    expect(init.headers.Authorization).toBe("Bearer test-session-token");
    expect(new Uint8Array(await res.arrayBuffer())).toEqual(bytes);
    expect(res.headers.get("content-disposition")).toBe("inline");
  });

  it("does not reveal the internal API address when the API is down", async () => {
    fetchMock.mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await GET(new NextRequest("http://localhost:3000/api/v1/me"), ctx(["me"]));
    expect(res.status).toBe(503);
    expect(await res.text()).not.toMatch(/http:\/\//);
  });
});
