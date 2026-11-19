"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Building2, User } from "lucide-react";
import type { UserPrincipal, UserRole } from "@/lib/types";

export interface HeaderProps {
  user: UserPrincipal;
}

const ROLE_BADGE_STYLES: Record<
  UserRole,
  { label: string; bg: string; text: string; border: string }
> = {
  requester: {
    label: "Requester",
    bg: "bg-blue-50",
    text: "text-blue-700",
    border: "border-blue-200",
  },
  buyer: {
    label: "Buyer",
    bg: "bg-purple-50",
    text: "text-purple-700",
    border: "border-purple-200",
  },
  manager: {
    label: "Manager",
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
  },
  admin: {
    label: "Admin",
    bg: "bg-amber-50",
    text: "text-amber-800",
    border: "border-amber-200",
  },
};

export const Header: React.FC<HeaderProps> = ({ user }) => {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleSignOut = async () => {
    try {
      setLoggingOut(true);
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
      });
      router.push("/login");
      router.refresh();
    } catch {
      // In case of error, still redirect to login
      router.push("/login");
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur-sm shadow-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm">
            <Building2 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold text-slate-900 tracking-tight">
                Demo Holdings LLC
              </span>
              {user.is_demo && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600 border border-slate-200">
                  Demo
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              Procurement Document Assistant
            </p>
          </div>
        </div>

        {/* User profile & actions */}
        <div className="flex items-center gap-4 sm:gap-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-600 border border-slate-200">
              <User className="h-5 w-5" aria-hidden="true" />
            </div>

            <div className="hidden sm:block text-right">
              <div className="text-sm font-semibold text-slate-900">
                {user.display_name}
              </div>
              <div className="flex items-center justify-end gap-1.5 text-xs text-slate-500">
                {user.department_name && (
                  <span>{user.department_name}</span>
                )}
              </div>
            </div>
          </div>

          {/* Role Badges */}
          <div className="flex flex-wrap items-center gap-1.5">
            {user.roles.map((role) => {
              const roleKey = role.toLowerCase() as UserRole;
              const config = ROLE_BADGE_STYLES[roleKey] || {
                label: role,
                bg: "bg-slate-50",
                text: "text-slate-700",
                border: "border-slate-200",
              };

              return (
                <span
                  key={role}
                  className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${config.bg} ${config.text} ${config.border}`}
                >
                  {config.label}
                </span>
              );
            })}
          </div>

          {/* Sign Out Button */}
          <button
            type="button"
            onClick={handleSignOut}
            disabled={loggingOut}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50 transition-colors"
            title="Sign out of your account"
            aria-label="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">
              {loggingOut ? "Signing out..." : "Sign Out"}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
};
