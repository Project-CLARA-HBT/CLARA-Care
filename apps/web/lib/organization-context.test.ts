import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ACTIVE_ORGANIZATION_STORAGE_KEY,
  clearActiveOrganizationContext,
  clearOrganizationScopedClientState,
  getActiveOrganizationId,
  ORGANIZATION_CACHE_PREFIX,
  ORGANIZATION_CONTEXT_CHANGE_EVENT,
  setActiveOrganizationId,
  TENANT_CACHE_PREFIX,
} from "./organization-context";

describe("organization-context boundary", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("returns null when no active organization is set", () => {
    expect(getActiveOrganizationId()).toBeNull();
  });

  it("sets and retrieves active organization ID", () => {
    setActiveOrganizationId("org_hospital_bachmai");
    expect(getActiveOrganizationId()).toBe("org_hospital_bachmai");
    expect(window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY)).toBe(
      "org_hospital_bachmai",
    );
  });

  it("clears organization-scoped caches upon organization switch", () => {
    window.localStorage.setItem(
      `${ORGANIZATION_CACHE_PREFIX}patients`,
      "patient_list_data",
    );
    window.sessionStorage.setItem(
      `${TENANT_CACHE_PREFIX}roster`,
      "tenant_roster_data",
    );
    window.localStorage.setItem("clara-theme", "dark"); // Preserved non-tenant key

    setActiveOrganizationId("org_clinic_international");

    // Organization-scoped caches must be expunged
    expect(window.localStorage.getItem(`${ORGANIZATION_CACHE_PREFIX}patients`)).toBeNull();
    expect(window.sessionStorage.getItem(`${TENANT_CACHE_PREFIX}roster`)).toBeNull();
    // Non-tenant preferences must survive
    expect(window.localStorage.getItem("clara-theme")).toBe("dark");
  });

  it("dispatches ORGANIZATION_CONTEXT_CHANGE_EVENT on change", () => {
    const handler = vi.fn();
    window.addEventListener(ORGANIZATION_CONTEXT_CHANGE_EVENT, handler);

    setActiveOrganizationId("org_hospital_chotray");

    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.detail.previous).toBeNull();
    expect(event.detail.next).toBe("org_hospital_chotray");

    window.removeEventListener(ORGANIZATION_CONTEXT_CHANGE_EVENT, handler);
  });

  it("does not dispatch event or clear cache if setting identical organization ID", () => {
    setActiveOrganizationId("org_hospital_bachmai");

    const handler = vi.fn();
    window.addEventListener(ORGANIZATION_CONTEXT_CHANGE_EVENT, handler);
    window.localStorage.setItem(`${ORGANIZATION_CACHE_PREFIX}cached`, "data");

    setActiveOrganizationId("org_hospital_bachmai");

    expect(handler).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(`${ORGANIZATION_CACHE_PREFIX}cached`)).toBe("data");

    window.removeEventListener(ORGANIZATION_CONTEXT_CHANGE_EVENT, handler);
  });

  it("clears active context and tenant cache on clearActiveOrganizationContext", () => {
    setActiveOrganizationId("org_1");
    window.localStorage.setItem(`${ORGANIZATION_CACHE_PREFIX}key1`, "value1");

    clearActiveOrganizationContext();

    expect(getActiveOrganizationId()).toBeNull();
    expect(window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY)).toBeNull();
    expect(window.localStorage.getItem(`${ORGANIZATION_CACHE_PREFIX}key1`)).toBeNull();
  });
});
