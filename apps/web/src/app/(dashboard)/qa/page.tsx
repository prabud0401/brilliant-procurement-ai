import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";
import { QAClient } from "./QAClient";
import type { UserPrincipal } from "@/lib/types";
import { ShieldAlert } from "lucide-react";

export default async function QAPage() {
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
    // API down handled by layout or fallback
  }

  const userRoles = user?.roles || [];
  const isOperationalRole = userRoles.some((r) =>
    ["requester", "buyer", "manager"].includes(r.toLowerCase())
  );
  const isAdminOnly = userRoles.includes("admin") && !isOperationalRole;

  if (isAdminOnly) {
    return (
      <div className="mx-auto max-w-4xl py-12 px-4 sm:px-6">
        <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-8 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
            <ShieldAlert className="h-7 w-7" aria-hidden="true" />
          </div>
          <h2 className="mt-4 text-xl font-bold tracking-tight text-slate-900">
            Q&A Restricted for Administrator Role
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-slate-600 leading-relaxed">
            Per security policy, the Document Q&A feature is reserved for operational
            procurement roles (Requester, Buyer, and Manager). Administrator accounts do not participate
            in procurement Q&A to prevent accidental access to unredacted business data.
          </p>
        </div>
      </div>
    );
  }

  return <QAClient user={user} />;
}
