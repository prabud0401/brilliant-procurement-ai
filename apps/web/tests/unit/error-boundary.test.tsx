import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import GlobalError from "@/app/error";

describe("Error Boundary (NFR-REL-04, NFR-OBS-01)", () => {
  it("displays friendly API unreachable state when fetch fails without crashing", () => {
    const error = new Error("Backend procurement API is currently unreachable. ECONNREFUSED");
    const reset = vi.fn();

    render(<GlobalError error={error} reset={reset} />);

    expect(
      screen.getByText("Procurement API Service Unreachable")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The web application is currently unable to communicate with the backend procurement API/i)
    ).toBeInTheDocument();

    const tryAgainBtn = screen.getByRole("button", { name: /Try Again/i });
    expect(tryAgainBtn).toBeInTheDocument();
    fireEvent.click(tryAgainBtn);
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("displays friendly generic error state for unexpected application errors", () => {
    const error = new Error("Unexpected null reference");
    const reset = vi.fn();

    render(<GlobalError error={error} reset={reset} />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(
      screen.getByText(/An unexpected error occurred while processing your request/i)
    ).toBeInTheDocument();
  });
});
