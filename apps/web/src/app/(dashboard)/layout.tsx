import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE_NAME, isTokenExpired } from "@/lib/auth/session";
import { DashboardShell } from "@/components/layout/DashboardShell";
import type { UserPrincipal } from "@/lib/types";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!token || isTokenExpired(token)) {
    redirect("/login?error=session_expired");
  }

  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
  let user: UserPrincipal;

  try {
    const res = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    if (!res.ok) {
      redirect("/login?error=invalid_session");
    }

    user = (await res.json()) as UserPrincipal;
  } catch (err: unknown) {
    // Re-throw Next.js redirect errors so navigation proceeds
    if (err && typeof err === "object" && "digest" in err) {
      throw err;
    }
    throw new Error(
      "Backend procurement API is currently unreachable. Please verify the API service is running."
    );
  }

  return <DashboardShell user={user}>{children}</DashboardShell>;
}
