"use client";

import type { ReactNode } from "react";
import Modal from "@/components/ui/modal";

/**
 * PHR adapter for the shared accessible modal. It preserves the PHR capability
 * boundary while inheriting focus trapping, focus restoration, Escape/backdrop
 * behaviour, scroll locking and labelled-dialog semantics.
 */
export default function PhrModal({
  open,
  title,
  onClose,
  children,
  closeLabel,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  closeLabel: string;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="lg" closeLabel={closeLabel}>
      {children}
    </Modal>
  );
}
