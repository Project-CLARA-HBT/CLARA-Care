import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MedicalTerm } from "@/components/ui/medical-term";

describe("MedicalTerm", () => {
  it("renders a trusted concept in the selected consumer locale", () => {
    render(<MedicalTerm concept="uncertainty" locale="vi" />);
    expect(screen.getByText("Phần chưa chắc chắn")).toBeInTheDocument();
  });

  it("renders expandable context without accepting unstructured references", () => {
    const { container } = render(
      <MedicalTerm concept="medication_interaction" locale="en" expandable />,
    );
    expect(screen.getByText("Medication interaction")).toBeInTheDocument();
    expect(container.querySelector("details")).toHaveAttribute(
      "data-medical-concept",
      "medication_interaction",
    );
    const unknown = render(<MedicalTerm concept="model generated diagnosis" />);
    expect(unknown.container).toBeEmptyDOMElement();
  });
});
