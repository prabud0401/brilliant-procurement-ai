import { describe, it, expect } from "vitest";
import { handleApiResponse, ApiError } from "@/lib/api/client";

describe("API Response Handler & Problem Details Mapping", () => {
  it("parses successful JSON response", async () => {
    const payload = { success: true, count: 42 };
    const mockResponse = new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

    const result = await handleApiResponse<typeof payload>(mockResponse);
    expect(result).toEqual(payload);
  });

  it("parses 204 No Content as empty object", async () => {
    const mockResponse = new Response(null, { status: 204 });
    const result = await handleApiResponse(mockResponse);
    expect(result).toEqual({});
  });

  it("throws ApiError with RFC 9457 ProblemDetails on 4xx/5xx responses", async () => {
    const problemPayload = {
      type: "https://pda.example/errors/unauthorized",
      title: "Unauthorized",
      status: 401,
      code: "INVALID_CREDENTIALS",
      detail: "Invalid email or password",
      request_id: "req-12345",
    };

    const mockResponse = new Response(JSON.stringify(problemPayload), {
      status: 401,
      headers: {
        "Content-Type": "application/problem+json",
        "X-Request-ID": "req-12345",
      },
    });

    try {
      await handleApiResponse(mockResponse);
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(401);
      expect(apiErr.problem.title).toBe("Unauthorized");
      expect(apiErr.problem.code).toBe("INVALID_CREDENTIALS");
      expect(apiErr.problem.detail).toBe("Invalid email or password");
      expect(apiErr.problem.request_id).toBe("req-12345");
    }
  });

  it("handles non-JSON error responses gracefully", async () => {
    const mockResponse = new Response("Gateway Timeout", {
      status: 504,
      statusText: "Gateway Timeout",
      headers: {
        "Content-Type": "text/plain",
        "X-Request-ID": "req-gw-504",
      },
    });

    try {
      await handleApiResponse(mockResponse);
      expect.fail("Should have thrown ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.problem.status).toBe(504);
      expect(apiErr.problem.detail).toBe("Gateway Timeout");
      expect(apiErr.problem.request_id).toBe("req-gw-504");
    }
  });
});
