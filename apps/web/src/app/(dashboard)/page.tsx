import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  FileText,
  ShoppingCart,
  CheckCircle2,
  Shield,
  Layers,
  Sparkles,
  Building,
  CreditCard,
  UserCheck,
} from "lucide-react";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";
import { formatMoneyAED } from "@/lib/formatters";
import type { UserPrincipal, UserRole } from "@/lib/types";

interface RoleCapabilityInfo {
  title: string;
  badgeLabel: string;
  badgeColor: string;
  summary: string;
  capabilities: string[];
}

const ROLE_CAPABILITIES: Record<UserRole, RoleCapabilityInfo> = {
  requester: {
    title: "Requester Workspace",
    badgeLabel: "Requester",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
    summary:
      "Employees who need goods or services (e.g. site engineers, department coordinators, or office managers).",
    capabilities: [
      "Raise purchase requests and attach supplier quotes or specifications",
      "Upload procurement documents and view AI extraction metadata for own files",
      "Track purchase request status through approval tiers in real time",
      "Ask grounded questions across your procurement documents with source citations",
    ],
  },
  buyer: {
    title: "Buyer Workspace",
    badgeLabel: "Buyer",
    badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
    summary:
      "Procurement officers responsible for sourcing, vendor comparison, PO creation, and three-way invoice matching.",
    capabilities: [
      "Process supplier quotes, delivery notes, and tax invoices through AI extraction",
      "Review and verify extracted fields using side-by-side document highlights and confidence scores",
      "Generate automated quote comparison matrices with 60/20/10/10 scoring and AI explanations",
      "Create purchase order drafts from winning quotations",
      "Perform line-level three-way matching across PO, delivery notes, and invoices",
      "Resolve matching variances within the AED 500 policy tolerance or escalate to managers",
    ],
  },
  manager: {
    title: "Manager (Approver) Workspace",
    badgeLabel: "Manager",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    summary:
      "Budget holders and department heads with financial delegation authority to approve procurement commitments.",
    capabilities: [
      "Review and approve purchase requests and purchase orders up to your delegated limit",
      "Examine quote comparison recommendations, weights, and vendor history before approving",
      "Resolve escalated three-way match exceptions requiring managerial sign-off",
      "Strict Segregation of Duties: self-approval of requests you created is automatically blocked",
    ],
  },
  admin: {
    title: "System Administration Workspace",
    badgeLabel: "Admin",
    badgeColor: "bg-amber-50 text-amber-800 border-amber-200",
    summary:
      "IT and procurement systems administrators managing policies, thresholds, integrations, and compliance.",
    capabilities: [
      "Manage user accounts, role delegations, and department financial approval limits",
      "Configure approval threshold tiers, match tolerances, and AI confidence review floors",
      "Monitor integration adapters (Odoo ERP, Microsoft SharePoint, Power Automate, Identity)",
      "Inspect the tamper-evident hash-chained audit log and export CSV compliance records",
    ],
  },
};

export default async function HomePage() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (!token) {
    redirect("/login");
  }

  const apiBaseUrl = process.env.API_BASE_URL || "http://localhost:8000";
  let user: UserPrincipal;

  try {
    const res = await fetch(`${apiBaseUrl}/api/v1/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    if (!res.ok) {
      redirect("/login?error=invalid_session");
    }

    user = (await res.json()) as UserPrincipal;
  } catch (err: unknown) {
    if (err && typeof err === "object" && "digest" in err) {
      throw err;
    }
    throw new Error("Unable to connect to backend procurement API.");
  }

  const userRoles = user.roles.map((r) => r.toLowerCase() as UserRole);

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                Welcome back, {user.display_name}
              </h1>
              {user.is_demo && (
                <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-800">
                  Demo Account
                </span>
              )}
            </div>
            <p className="mt-1.5 text-sm text-slate-600">
              Procurement Document Assistant • Demo Holdings LLC (United Arab Emirates)
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              API Connected
            </span>
          </div>
        </div>

        {/* User Details Grid */}
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 border-t border-slate-100 pt-6">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Building className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Department</p>
              <p className="text-sm font-semibold text-slate-900">
                {user.department_name || "General"}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <CreditCard className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Approval Limit</p>
              <p className="text-sm font-semibold text-slate-900">
                {formatMoneyAED(user.approval_limit_aed)}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
              <UserCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Account Email</p>
              <p className="text-sm font-semibold text-slate-900 truncate max-w-[180px]">
                {user.email}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <Shield className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500">Active Roles</p>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {user.roles.map((r) => (
                  <span
                    key={r}
                    className="inline-block rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700 capitalize"
                  >
                    {r}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Role Capabilities Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">
            What You Can Do in This System
          </h2>
          <p className="text-sm text-slate-500">
            Authorized procurement workflows and permissions according to your assigned role(s).
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {userRoles.map((role) => {
            const info = ROLE_CAPABILITIES[role];
            if (!info) return null;

            return (
              <div
                key={role}
                className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-slate-900">
                    {info.title}
                  </h3>
                  <span
                    className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium ${info.badgeColor}`}
                  >
                    {info.badgeLabel}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-600 leading-relaxed">
                  {info.summary}
                </p>

                <div className="mt-4 border-t border-slate-100 pt-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
                    Key Capabilities
                  </p>
                  <ul className="space-y-2">
                    {info.capabilities.map((cap, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2 text-xs text-slate-700 leading-normal"
                      >
                        <CheckCircle2
                          className="h-4 w-4 flex-shrink-0 text-emerald-600 pt-0.5"
                          aria-hidden="true"
                        />
                        <span>{cap}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* System Standards Banner */}
      <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-6">
        <div className="flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-blue-900 space-y-1">
            <p className="font-semibold text-sm text-blue-950">
              Procurement Document Assistant Standards & Compliance
            </p>
            <p>
              • All currency values are calculated in <strong>UAE Dirhams (AED)</strong> with standard UAE VAT (5%).
            </p>
            <p>
              • Audit log is cryptographically chained with SHA-256 hashes and recorded in the same database transaction.
            </p>
            <p>
              • AI extraction and quote explanations are strictly verified against source document facts before presentation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
