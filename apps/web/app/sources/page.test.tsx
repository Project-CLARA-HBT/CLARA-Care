import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import SourcesCatalogPage, { metadata } from "./page";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

describe("SourcesCatalogPage (/sources — Evidence & Pharmacopoeia Catalog)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("exports metadata with canonical link and rich description", () => {
    expect(metadata.title).toContain("Danh mục Nguồn Y văn");
    expect(metadata.description).toContain("Dược thư Quốc gia Việt Nam");
    expect(metadata.description).toContain("DrugBank");
    expect(metadata.alternates?.canonical).toBe("/sources");
  });

  it("renders with PUBLIC_LEGAL shell mode and Sources Catalog layout archetype", () => {
    const { container } = render(<SourcesCatalogPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Sources Catalog");
  });

  it("renders breadcrumbs, header, and primary source tiers", () => {
    render(<SourcesCatalogPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Danh mục Nguồn Y văn & Dược thư Tham chiếu/i,
      }),
    ).toBeInTheDocument();

    // Source catalog tiers and major databases
    expect(screen.getByText(/Dược thư Quốc gia Việt Nam/i)).toBeInTheDocument();
    expect(screen.getByText(/DrugBank Comprehensive Pharmacoinformatics Database/i)).toBeInTheDocument();
    expect(screen.getByText(/US FDA DailyMed & National Drug Code Directory/i)).toBeInTheDocument();
    expect(screen.getByText(/PubMed \/ MEDLINE & Living Evidence Repositories/i)).toBeInTheDocument();
    expect(screen.getByText(/Hướng dẫn Chẩn đoán và Điều trị của Bộ Y Tế Việt Nam/i)).toBeInTheDocument();
  });

  it("supports interactive search filtering across knowledge sources", () => {
    render(<SourcesCatalogPage />);

    const searchInput = screen.getByRole("searchbox", {
      name: /Tìm kiếm nguồn y văn, dược thư hoặc hướng dẫn điều trị/i,
    });
    expect(searchInput).toBeInTheDocument();

    // Filter by "DrugBank"
    fireEvent.change(searchInput, { target: { value: "DrugBank" } });
    expect(screen.getByText(/DrugBank Comprehensive Pharmacoinformatics Database/i)).toBeInTheDocument();

    // Clear search and filter by tab button
    fireEvent.change(searchInput, { target: { value: "" } });
    const categoryTab = screen.getByRole("tab", { name: /Dược thư & Thuốc/i });
    fireEvent.click(categoryTab);
    expect(screen.getByText(/Dược thư Quốc gia Việt Nam/i)).toBeInTheDocument();
  });
});
