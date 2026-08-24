import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mockListClinicalFeedback = vi.fn();
const mockUpdateFeedbackTriage = vi.fn();
const mockExportFeedbackToBenchmark = vi.fn();
const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

vi.mock("@/lib/clinical-feedback", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/clinical-feedback")>();
  return {
    ...actual,
    listClinicalFeedback: () => mockListClinicalFeedback(),
    updateFeedbackTriage: (id: string | number, updates: any) =>
      mockUpdateFeedbackTriage(id, updates),
    exportFeedbackToBenchmark: (id: string | number) =>
      mockExportFeedbackToBenchmark(id),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

import ClinicalFeedbackTriagePage from "@/app/admin/feedback/page";
import { SEED_CLINICAL_FEEDBACK } from "@/lib/clinical-feedback";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockListClinicalFeedback.mockResolvedValue([...SEED_CLINICAL_FEEDBACK]);
  mockUpdateFeedbackTriage.mockImplementation(async (id, updates) => {
    const item = SEED_CLINICAL_FEEDBACK.find((i) => String(i.id) === String(id));
    return {
      ...(item ?? SEED_CLINICAL_FEEDBACK[0]),
      ...updates,
      id,
      updated_at: new Date().toISOString(),
    };
  });
  mockExportFeedbackToBenchmark.mockResolvedValue({
    success: true,
    benchmark_id: "BENCH-GOLDEN-FB-801",
  });
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("ClinicalFeedbackTriagePage (Spec v5 Section 6.71)", () => {
  describe("1. Shell and Role-based Access Control", () => {
    it("renders forbidden notice when user role is not admin (Property P7)", async () => {
      roleState.role = "doctor";
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
      });

      expect(mockListClinicalFeedback).not.toHaveBeenCalled();
    });

    it("renders AdminShell, header, and command strip for admin role", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(mockListClinicalFeedback).toHaveBeenCalled();
      });

      expect(
        screen.getByRole("heading", { level: 1, name: /Clinical Feedback Triage Queue/i }),
      ).toBeInTheDocument();
      expect(screen.getByText("TRIAGE-Q")).toBeInTheDocument();
    });
  });

  describe("2. Summary KPIs and Accuracy Rating Breakdown", () => {
    it("renders all 4 summary KPI cards with accurate calculations", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText(/Total Feedback/i)).toBeInTheDocument();
      });

      expect(screen.getByText("Total Feedback")).toBeInTheDocument();
      expect(screen.getByText("Avg Accuracy Rating")).toBeInTheDocument();
      expect(screen.getByText(/Critical Unresolved/i)).toBeInTheDocument();
      expect(screen.getByText("Resolution Rate")).toBeInTheDocument();
    });

    it("renders the Accuracy Rating Breakdown and Clinical Risk Category panels", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("Accuracy Rating Breakdown")).toBeInTheDocument();
      });

      expect(screen.getByText("Accuracy Rating Breakdown")).toBeInTheDocument();
      expect(screen.getByText("Clinical Risk Category Breakdown")).toBeInTheDocument();

      // Check rating rows
      expect(screen.getByText(/5 stars \(Accurate\)/i)).toBeInTheDocument();
      expect(screen.getByText(/1 star \(Critical Hazard\)/i)).toBeInTheDocument();

      // Check category rows
      expect(screen.getAllByText(/Dosage & Drug Interaction/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Contraindication & Red Flag/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Clinical Hallucination/i).length).toBeGreaterThan(0);
    });
  });

  describe("3. Dense Stream Table and Multi-dimensional Filtering", () => {
    it("renders the dense feedback table with all seed items and headers", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      expect(screen.getByText("#FB-801")).toBeInTheDocument();
      expect(screen.getByText("#FB-802")).toBeInTheDocument();
      expect(screen.getByText("#FB-803")).toBeInTheDocument();
      expect(screen.getByText("#FB-804")).toBeInTheDocument();
      expect(screen.getByText("#FB-805")).toBeInTheDocument();
      expect(screen.getByText("#FB-806")).toBeInTheDocument();

      // Check table column headers
      expect(screen.getByText("ID & Date")).toBeInTheDocument();
      expect(screen.getByText("Rating")).toBeInTheDocument();
      expect(screen.getByText("Submitter")).toBeInTheDocument();
      expect(screen.getByText("Category & Risk")).toBeInTheDocument();
      expect(screen.getByText("Status")).toBeInTheDocument();
    });

    it("filters stream items by Triage Status (e.g. Pending, In Triage, Resolved)", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      // Filter by Resolved
      const resolvedFilterBtn = screen.getByRole("button", { name: /Resolved/i });
      fireEvent.click(resolvedFilterBtn);

      await waitFor(() => {
        expect(screen.queryByText("#FB-801")).not.toBeInTheDocument(); // was "new"
        expect(screen.getByText("#FB-805")).toBeInTheDocument(); // resolved
        expect(screen.getByText("#FB-806")).toBeInTheDocument(); // resolved
      });
    });

    it("filters stream items by search query", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search query, notes, ID.../i);
      fireEvent.change(searchInput, { target: { value: "Metformin" } });

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
        expect(screen.queryByText("#FB-802")).not.toBeInTheDocument();
        expect(screen.queryByText("#FB-803")).not.toBeInTheDocument();
      });
    });

    it("filters stream items by Severity dropdown", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      const severitySelect = screen.getByLabelText(/Severity:/i);
      fireEvent.change(severitySelect, { target: { value: "low" } });

      await waitFor(() => {
        expect(screen.queryByText("#FB-801")).not.toBeInTheDocument(); // critical
        expect(screen.getByText("#FB-805")).toBeInTheDocument(); // low
        expect(screen.getByText("#FB-806")).toBeInTheDocument(); // low
      });
    });
  });

  describe("4. Resolution Inspector Drawer and Triage Workflow", () => {
    it("opens the Inspector Drawer with clinical context when clicking Inspect", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByText(/1. Feedback & Submitter Metadata/i)).toBeInTheDocument();
        expect(screen.getByText(/2. Clinical Query & CLARA Output/i)).toBeInTheDocument();
        expect(screen.getByText(/3. Clinician Observation & Proposal/i)).toBeInTheDocument();
        expect(screen.getByText(/4. Triage Resolution & Workflow/i)).toBeInTheDocument();
      });

      // Verify clinical query and response are displayed
      expect(screen.getAllByText(/Bệnh nhân suy thận eGFR 28 mL\/min/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Chống chỉ định tuyệt đối Metformin khi eGFR < 30/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Ngừng ngay Metformin/i)).toBeInTheDocument();
    });

    it("allows updating triage status, resolution note, and saves changes", async () => {
      const { container } = render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      // Open inspector for FB-801
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(container.querySelector("#triage-status-select")).toBeInTheDocument();
      });

      // Change status to in_triage
      const statusSelect = container.querySelector("#triage-status-select") as HTMLSelectElement;
      fireEvent.change(statusSelect, { target: { value: "in_triage" } });

      // Add resolution note
      const notesTextarea = screen.getByLabelText(/Resolution Notes & Corrective Actions/i);
      fireEvent.change(notesTextarea, {
        target: { value: "Escalated to Renal safety committee for prompt constraint update." },
      });

      // Save changes
      const saveBtn = screen.getByRole("button", { name: /Save Changes/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockUpdateFeedbackTriage).toHaveBeenCalledWith("FB-801", expect.objectContaining({
          triage_status: "in_triage",
          resolution_note: "Escalated to Renal safety committee for prompt constraint update.",
        }));
      });

      // Toast appears
      expect(screen.getByText(/Successfully updated feedback #FB-801 triage status/i)).toBeInTheDocument();
    });

    it("exports clinical feedback item to Golden RAG Benchmark", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      // Open inspector for FB-801
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Export RAG Golden/i })).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /Export RAG Golden/i });
      fireEvent.click(exportBtn);

      await waitFor(() => {
        expect(mockExportFeedbackToBenchmark).toHaveBeenCalledWith("FB-801");
      });

      // Toast appears
      expect(screen.getByText(/Exported feedback #FB-801 to RAG Golden Benchmark/i)).toBeInTheDocument();
    });
  });
});
