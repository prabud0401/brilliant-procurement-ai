import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";
import { MetricsClient } from "./MetricsClient";
import type { UserPrincipal } from "@/lib/types";
import { ShieldAlert } from "lucide-react";

export default async function AdminMetricsPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!token) {
    redirect("/login?error=session_expired");
  }

  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
  let user: UserPrincipal | null = null;

  try {
    const res = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.ok) {
      user = (await res.json()) as UserPrincipal;
    }
  } catch {
    // API failure handled in layout/client
  }

  const userRoles = user?.roles || [];
  const isAdmin = userRoles.includes("admin");

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-4xl py-12 px-4 sm:px-6">
        <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-8 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-100 text-rose-700">
            <ShieldAlert className="h-7 w-7" aria-hidden="true" />
          </div>
          <h2 className="mt-4 text-xl font-bold tracking-tight text-slate-900">
            Access Restricted: Administrator Only
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-slate-600 leading-relaxed">
            The System Observability & Business Metrics dashboard requires Administrator role
            permissions (design 7.2, US-19). Your account does not hold the admin privilege.
          </p>
        </div>
      </div>
    );
  }

  // Fetch initial metrics
  let initialMetrics = null;
  try {
    const mRes = await fetch(`${apiBaseUrl}/api/v1/admin/metrics`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (mRes.ok) {
      initialMetrics = await mRes.json();
    }
  } catch {
    // Client will retry
  }

  return <MetricsClient initialData={initialMetrics} />;
}
