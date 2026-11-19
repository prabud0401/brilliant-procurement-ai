import type { ProblemDetails } from "../types";
import type { paths } from "./schema";

/**
 * Base API URL resolver:
 * In server-side environments (SSR / Route Handlers), calls direct backend URL (e.g. http://api:8000 or http://localhost:8000).
 * In client-side environments (browser), calls the Next.js BFF proxy (/api/v1).
 */
export function getApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.API_BASE_URL || "http://localhost:8000";
  }
  return "";
}

export class ApiError extends Error {
  public problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title || `API Error ${problem.status}`);
    this.name = "ApiError";
    this.problem = problem;
  }
}

/**
 * Parses response into typed data or throws an ApiError with RFC 9457 ProblemDetails.
 */
export async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    let problem: ProblemDetails;

    if (contentType.includes("application/problem+json") || contentType.includes("application/json")) {
      try {
        problem = (await response.json()) as ProblemDetails;
      } catch {
        problem = {
          title: response.statusText || "Request failed",
          status: response.status,
          detail: "Failed to parse error response JSON",
        };
      }
    } else {
      const text = await response.text();
      problem = {
        title: response.statusText || "Request failed",
        status: response.status,
        detail: text || undefined,
      };
    }

    if (!problem.status) problem.status = response.status;
    if (!problem.request_id) {
      problem.request_id = response.headers.get("x-request-id") || undefined;
    }

    throw new ApiError(problem);
  }

  // Handle empty responses (204 No Content, etc.)
  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}

/**
 * Type-safe fetcher utility leveraging OpenAPI schema paths.
 */
export type ApiPaths = keyof paths;
