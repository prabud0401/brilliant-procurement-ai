import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(`${apiBaseUrl}/readyz`, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      return NextResponse.json({ status: "ok" });
    }
    return NextResponse.json(
      { status: "unavailable", detail: `Backend returned ${res.status}` },
      { status: 503 }
    );
  } catch (error) {
    return NextResponse.json(
      {
        status: "unavailable",
        error: error instanceof Error ? error.message : "Backend unreachable",
      },
      { status: 503 }
    );
  }
}
