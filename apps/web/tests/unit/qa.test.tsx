import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QAClient } from "@/app/(dashboard)/qa/QAClient";
import { ToastProvider } from "@/components/ui/Toast";

describe("QAClient Component (US-17, US-18, US-20)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const renderWithToast = (ui: React.ReactElement) => {
    return render(<ToastProvider>{ui}</ToastProvider>);
  };

  it("renders empty state with welcoming instructions and sample questions", () => {
    renderWithToast(<QAClient user={null} />);
    expect(
      screen.getByText("Ask about your procurement documents")
    ).toBeInTheDocument();
    expect(
      screen.getByText("What is the total amount and VAT on quote Q-1042?")
    ).toBeInTheDocument();
  });

  it("clicking a sample question populates the input textarea", () => {
    renderWithToast(<QAClient user={null} />);
    const sampleBtn = screen.getByText(
      "What is the total amount and VAT on quote Q-1042?"
    );
    fireEvent.click(sampleBtn);

    const textarea = screen.getByPlaceholderText(/Ask a question about quotes/i);
    expect(textarea).toHaveValue("What is the total amount and VAT on quote Q-1042?");
  });

  it("submitting an answerable question renders answer and citation links (US-17, US-20)", async () => {
    const mockResponse = {
      answer: [
        {
          text: "The quote total is AED 12,500 with 5% VAT.",
          citations: [
            {
              document_id: "doc-1234-uuid",
              title: "Quote Q-1042 (Gulf Line)",
              page: 2,
              chunk_id: "c12",
            },
          ],
        },
      ],
      refused: false,
      refusal_reason: null,
    };

    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    renderWithToast(<QAClient user={null} />);
    const textarea = screen.getByPlaceholderText(/Ask a question about quotes/i);
    fireEvent.change(textarea, { target: { value: "What is the quote total?" } });

    const sendBtn = screen.getByLabelText("Send question");
    fireEvent.click(sendBtn);

    // Expect user message
    expect(screen.getByText("What is the quote total?")).toBeInTheDocument();

    // Expect answer text
    await waitFor(() => {
      expect(
        screen.getByText("The quote total is AED 12,500 with 5% VAT.")
      ).toBeInTheDocument();
    });

    // Expect citation link pointing to cited page with highlight
    const citationLink = screen.getByRole("link", {
      name: /Quote Q-1042 \(Gulf Line\), p\. 2/i,
    });
    expect(citationLink).toBeInTheDocument();
    expect(citationLink).toHaveAttribute(
      "href",
      "/documents/doc-1234-uuid?page=2&highlight=c12"
    );
  });

  it("submitting an unanswerable question displays a refusal message (US-18)", async () => {
    const mockRefusal = {
      answer: [],
      refused: true,
      refusal_reason: "I could not find an answer in the accessible procurement documents.",
    };

    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => mockRefusal,
    } as Response);

    renderWithToast(<QAClient user={null} />);
    const textarea = screen.getByPlaceholderText(/Ask a question about quotes/i);
    fireEvent.change(textarea, {
      target: { value: "What was the weather in Dubai yesterday?" },
    });

    const sendBtn = screen.getByLabelText("Send question");
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText("Unable to Answer")).toBeInTheDocument();
      expect(
        screen.getByText(
          "I could not find an answer in the accessible procurement documents."
        )
      ).toBeInTheDocument();
    });
  });
});
