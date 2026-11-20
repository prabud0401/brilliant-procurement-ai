import { cookies } from "next/headers";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";
import { DocumentsPageClient } from "./DocumentsPageClient";
import type { UserPrincipal } from "@/lib/types";

export default async function DocumentsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";

  let userRoles: string[] = [];

  try {
    const res = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    if (res.ok) {
      const user = (await res.json()) as UserPrincipal;
      userRoles = user.roles || [];
    }
  } catch {
    // fallback if API not ready during SSR
  }

  return <DocumentsPageClient userRoles={userRoles} />;
}
