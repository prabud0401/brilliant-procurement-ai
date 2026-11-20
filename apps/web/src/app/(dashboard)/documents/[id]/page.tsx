import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";
import { ReviewClient } from "@/components/documents/ReviewClient";
import type { UserPrincipal } from "@/lib/types";
import type { DocumentResponse, ExtractionResponse } from "@/lib/documents/types";

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string; highlight?: string }>;
}

export default async function DocumentReviewPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const { page, highlight } = await searchParams;

  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";

  // 1. Fetch user roles
  let userRoles: string[] = [];
  try {
    const meRes = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (meRes.ok) {
      const user = (await meRes.json()) as UserPrincipal;
      userRoles = user.roles || [];
    }
  } catch {
    // fallback
  }

  // 2. Fetch document metadata
  const docRes = await fetch(`${apiBaseUrl}/api/v1/documents/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (docRes.status === 404) {
    notFound();
  }

  if (!docRes.ok) {
    throw new Error(`Failed to load document (${docRes.statusText})`);
  }

  const documentData: DocumentResponse = await docRes.json();

  // 3. Fetch latest extraction
  let extractionData: ExtractionResponse | null = null;
  const extRes = await fetch(`${apiBaseUrl}/api/v1/documents/${id}/extraction`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  if (extRes.ok) {
    extractionData = await extRes.json();
  }

  const initialPage = page ? parseInt(page, 10) || 1 : 1;

  return (
    <ReviewClient
      initialDocument={documentData}
      initialExtraction={extractionData}
      userRoles={userRoles}
      initialPage={initialPage}
      initialHighlightId={highlight}
    />
  );
}
