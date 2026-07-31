"use client";

/**
 * Canonical entry point for adding or scanning an item in the Medicines
 * cabinet. The implementation lives in the maintained Medicines component;
 * the historical `/selfmed/add` URL imports the same component solely as a
 * compatibility alias.
 */
export { default } from "@/components/medicines/cabinet-add-page";
