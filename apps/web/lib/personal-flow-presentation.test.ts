import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(__dirname, "..", path), "utf8");
}

describe("personal workspace progressive disclosure", () => {
  it("keeps Today focused on accepted tasks and one empty-state primary action", () => {
    const today = source("app/today/page.tsx");
    expect(today).not.toContain("QUICK_ACTIONS");
    expect(today).not.toContain("<StatCard");
    expect(today).toContain('"/lifemap/new"');
    expect(today).toContain('href="/chat"');
    expect(today).toContain('"today.emptyDescription"');
  });

  it("organizes Family support into shared, received and access-log tabs", () => {
    const family = source("app/family/page.tsx");
    expect(family).toContain('type FamilyTab = "shared" | "received" | "log"');
    expect(family).toContain('href="/family/invite"');
    expect(family).toContain('href="/family/accept"');
    expect(family).toContain("<TabPanel");
  });

  it("presents visits as a vertical chronological timeline stream with upcoming HeroObject", () => {
    const visits = source("app/visits/page.tsx");
    expect(visits).toContain("<HeroObject");
    expect(visits).toContain("<Timeline");
    expect(visits).toContain('href="/visits/new"');
    expect(visits).toContain('copy("visits.newVisitCta")');
    expect(visits).toContain('copy("visits.upcomingEyebrow")');
    expect(visits).toContain('copy("visits.pastVisitsEyebrow")');
  });

  it("organizes visit preparation into four guided steps in the new visit flow", () => {
    const newVisit = source("app/visits/new/new-visit-flow.tsx");
    expect(newVisit).toContain('type Step = "reason" | "symptoms" | "medications" | "summary"');
    expect(newVisit).toContain('"visitWizard.step.reason"');
    expect(newVisit).toContain('"visitWizard.step.symptoms"');
    expect(newVisit).toContain('"visitWizard.step.medications"');
    expect(newVisit).toContain('"visitWizard.step.summary"');
  });
});
