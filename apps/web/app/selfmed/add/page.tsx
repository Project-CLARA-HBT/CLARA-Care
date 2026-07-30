"use client";

/**
 * Historical bookmark alias. New navigation must use
 * `/medicines/cabinet/add`; both URLs deliberately render the same consent-
 * gated Medicines component so this route cannot become a second workflow.
 */
export { default } from "@/components/medicines/cabinet-add-page";
