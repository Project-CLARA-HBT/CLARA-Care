"use client";

/**
 * Canonical entry point for adding or scanning an item in the Medicines
 * cabinet. The implementation remains in the legacy route module for now so
 * existing bookmarks keep their exact behavior during the compatibility
 * window. New links must use this canonical Medicines-owned route.
 */
export { default } from "@/app/selfmed/add/page";
