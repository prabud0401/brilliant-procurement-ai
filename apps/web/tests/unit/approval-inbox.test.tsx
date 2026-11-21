import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import ApprovalsInboxPage from "@/app/(dashboard)/approvals/page";

describe("ApprovalsInboxPage - Admin Segregation of Duties", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders friendly SoD message without '403' in heading when forbidden", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      status: 403,
      ok: false,
      json: async () => ({}),
    } as Response);

    render(<ApprovalsInboxPage />);

    await waitFor(() => {
      const deniedCard = screen.getByTestId("approvals-access-denied");
      expect(deniedCard).toBeInTheDocument();
    });

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(/Segregation of Duties/i);
    expect(heading).not.toHaveTextContent("403");
    expect(screen.queryByText(/403 Forbidden/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});
