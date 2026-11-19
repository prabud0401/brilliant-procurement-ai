import React from "react";
import { Header } from "./Header";
import { Navigation } from "./Navigation";
import type { UserPrincipal } from "@/lib/types";

export interface DashboardShellProps {
  user: UserPrincipal;
  children: React.ReactNode;
}

export const DashboardShell: React.FC<DashboardShellProps> = ({
  user,
  children,
}) => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header user={user} />
      <Navigation userRoles={user.roles} />
      <main className="flex-1 py-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">{children}</div>
      </main>
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        Demo Holdings LLC • Procurement Document Assistant • Synthetic Demo Data (AED)
      </footer>
    </div>
  );
};
