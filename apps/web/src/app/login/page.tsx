"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Building2,
  Lock,
  Mail,
  AlertCircle,
  Check,
  Shield,
  ArrowRight,
} from "lucide-react";
import type { ProblemDetails } from "@/lib/types";

interface DemoAccount {
  email: string;
  role: string;
  department: string;
  notes?: string;
}

const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    email: "requester.fac@demo-holdings.example",
    role: "Requester",
    department: "Facilities",
  },
  {
    email: "requester.it@demo-holdings.example",
    role: "Requester",
    department: "IT",
  },
  {
    email: "buyer1@demo-holdings.example",
    role: "Buyer",
    department: "Facilities",
  },
  {
    email: "buyer2@demo-holdings.example",
    role: "Buyer",
    department: "IT",
  },
  {
    email: "manager.facilities@demo-holdings.example",
    role: "Manager",
    department: "Facilities",
    notes: "AED 50,000 limit",
  },
  {
    email: "manager.it@demo-holdings.example",
    role: "Manager",
    department: "IT",
    notes: "AED 50,000 limit",
  },
  {
    email: "manager.projects@demo-holdings.example",
    role: "Manager",
    department: "Projects",
    notes: "AED 250,000 limit",
  },
  {
    email: "admin@demo-holdings.example",
    role: "Admin",
    department: "IT / Operations",
    notes: "Full admin privileges",
  },
  {
    email: "requester.finance@demo-holdings.example",
    role: "Requester",
    department: "Finance",
  },
  {
    email: "manager.finance@demo-holdings.example",
    role: "Manager",
    department: "Finance",
    notes: "AED 50,000 limit",
  },
  {
    email: "requester.hr@demo-holdings.example",
    role: "Requester",
    department: "HR",
  },
  {
    email: "manager.hr@demo-holdings.example",
    role: "Manager",
    department: "HR",
    notes: "AED 50,000 limit",
  },
  {
    email: "requester.ops@demo-holdings.example",
    role: "Requester",
    department: "Operations",
  },
  {
    email: "manager.ops@demo-holdings.example",
    role: "Manager",
    department: "Operations",
    notes: "AED 50,000 limit",
  },
  {
    email: "requester.projects@demo-holdings.example",
    role: "Requester",
    department: "Projects",
  },
];

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorProblem, setErrorProblem] = useState<ProblemDetails | null>(null);

  const errorParam = searchParams.get("error");
  const fromParam = searchParams.get("from");

  let urlMessage: string | null = null;
  if (errorParam === "session_expired") {
    urlMessage = "Your session has expired. Please sign in again.";
  } else if (errorParam === "invalid_session") {
    urlMessage = "Your session is invalid. Please sign in to continue.";
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorProblem(null);

    if (!email || !password) {
      setErrorProblem({
        title: "Validation Error",
        status: 422,
        detail: "Please enter both email and password.",
      });
      return;
    }

    try {
      setLoading(true);
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
      });

      if (!res.ok) {
        const problemData: ProblemDetails = await res.json().catch(() => ({
          title: "Sign-In Failed",
          status: res.status,
          detail: "Unable to sign in with provided credentials.",
        }));
        setErrorProblem(problemData);
        setLoading(false);
        return;
      }

      // Successful login
      const targetUrl = fromParam || "/";
      router.push(targetUrl);
      router.refresh();
    } catch {
      setErrorProblem({
        title: "Connection Error",
        status: 503,
        detail:
          "Unable to connect to the authentication service. Please check your network connection.",
      });
      setLoading(false);
    }
  };

  const handleSelectDemo = (demoEmail: string) => {
    setEmail(demoEmail);
    setErrorProblem(null);
  };

  return (
    <div className="flex min-h-screen flex-col justify-center bg-slate-50 py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-md">
          <Building2 className="h-8 w-8" aria-hidden="true" />
        </div>
        <h2 className="mt-4 text-center text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Demo Holdings LLC
        </h2>
        <p className="mt-1.5 text-center text-sm text-slate-600">
          Procurement Document Assistant
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="rounded-xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
          {urlMessage && (
            <div
              className="mb-6 rounded-md border border-amber-200 bg-amber-50 p-4 text-xs font-medium text-amber-800"
              role="alert"
            >
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0" />
                <span>{urlMessage}</span>
              </div>
            </div>
          )}

          {errorProblem && (
            <div
              className="mb-6 rounded-md border border-rose-200 bg-rose-50 p-4 text-slate-800"
              role="alert"
              aria-live="assertive"
            >
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-xs font-bold text-rose-900">
                    {errorProblem.title}
                  </h3>
                  {errorProblem.detail && (
                    <p className="mt-1 text-xs text-rose-700">
                      {errorProblem.detail}
                    </p>
                  )}
                  {errorProblem.request_id && (
                    <p className="mt-2 font-mono text-[10px] text-rose-600">
                      ID: {errorProblem.request_id}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-slate-700"
              >
                Work Email Address
              </label>
              <div className="relative mt-1.5">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Mail className="h-4 w-4" aria-hidden="true" />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@demo-holdings.example"
                  className="block w-full rounded-md border border-slate-300 pl-10 pr-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-slate-700"
              >
                Password
              </label>
              <div className="relative mt-1.5">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Lock className="h-4 w-4" aria-hidden="true" />
                </div>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full rounded-md border border-slate-300 pl-10 pr-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex w-full justify-center items-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50 transition-colors"
            >
              {loading ? (
                <span>Signing in...</span>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </>
              )}
            </button>
          </form>

          {/* Demo Accounts Panel */}
          <div className="mt-8 border-t border-slate-200 pt-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1.5">
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-blue-700">
                  Demo
                </span>
                <span className="text-xs font-semibold text-slate-700">
                  Seeded Test Accounts
                </span>
              </div>
              <span className="text-[11px] text-slate-500">
                Click to populate email
              </span>
            </div>

            <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
              {DEMO_ACCOUNTS.map((acc) => {
                const isSelected = email === acc.email;
                return (
                  <button
                    key={acc.email}
                    type="button"
                    onClick={() => handleSelectDemo(acc.email)}
                    className={`flex w-full items-center justify-between rounded-lg border p-2.5 text-left text-xs transition-colors ${
                      isSelected
                        ? "border-blue-500 bg-blue-50/70 text-blue-900"
                        : "border-slate-200 bg-slate-50/50 hover:bg-slate-100/70 text-slate-700"
                    }`}
                  >
                    <div className="truncate pr-2">
                      <div className="font-medium truncate">{acc.email}</div>
                      <div className="text-[11px] text-slate-500">
                        {acc.role} • {acc.department}
                        {acc.notes ? ` (${acc.notes})` : ""}
                      </div>
                    </div>
                    {isSelected && (
                      <Check className="h-4 w-4 text-blue-600 flex-shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>

            <p className="mt-3 text-[11px] text-slate-500 text-center">
              Demo passwords are securely provided via local environment (<code className="font-mono text-slate-700">DEMO_USER_PASSWORD</code>).
            </p>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-center gap-1.5 text-xs text-slate-500">
          <Shield className="h-4 w-4 text-slate-400" />
          <span>Protected with HTTP-only session cookies and CSRF verification</span>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-500 text-sm">
          Loading sign-in...
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
