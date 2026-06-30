/**
 * Primary-action label vocabulary.
 *
 * This module is the single source of truth for the Vietnamese, task-oriented
 * primary-action labels shown on each Surface. The vocabulary mirrors the
 * guidance page at `/huong-dan` so a user reading the guide sees the exact same
 * call-to-action wording on the corresponding Surface (Requirement 5.5).
 *
 * Keeping the labels here (rather than inline per page) lets every Surface in
 * Epic 9 reference one consistent, reviewed set of labels and lets tests assert
 * the guide and the Surfaces never drift apart.
 *
 * Requirements: 5.5 (Vietnamese task-oriented primary-action labels consistent
 *               with the guidance page).
 */

/** A Surface that exposes a guided primary action on the guidance page. */
export type PrimarySurface =
  | "chat"
  | "chat_thinking"
  | "selfmed"
  | "ddi"
  | "council"
  | "scribe";

export type PrimaryAction = {
  /** Surface key. */
  surface: PrimarySurface;
  /** Destination route the action opens. */
  href: string;
  /** Vietnamese task-oriented label shown on the button/link. */
  label: string;
};

/**
 * Canonical primary actions, kept verbatim in sync with the task cards on
 * `/huong-dan`. If the guidance page wording changes, update it here too — the
 * accompanying test fails when the two drift.
 */
export const PRIMARY_ACTIONS: Record<PrimarySurface, PrimaryAction> = {
  chat: { surface: "chat", href: "/chat", label: "Mở hỏi CLARA" },
  chat_thinking: {
    surface: "chat_thinking",
    href: "/chat",
    label: "Mở chế độ Tư duy"
  },
  selfmed: { surface: "selfmed", href: "/selfmed", label: "Mở tủ thuốc" },
  ddi: { surface: "ddi", href: "/selfmed/ddi", label: "Kiểm tra tương tác" },
  council: { surface: "council", href: "/council", label: "Mở hội chẩn AI" },
  scribe: { surface: "scribe", href: "/scribe", label: "Mở ghi chép y khoa" }
};

/**
 * Return the Vietnamese task-oriented primary-action label for a Surface.
 * Falls back to a neutral, safe label for an unknown Surface so an internal
 * key never leaks into the UI.
 */
export function getPrimaryActionLabel(surface: string): string {
  const action = PRIMARY_ACTIONS[surface as PrimarySurface];
  return action ? action.label : "Mở";
}
