"use client";

import { useSyncExternalStore } from "react";

import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

/**
 * React bridge for the persisted UI locale.
 *
 * The server snapshot is deliberately Vietnamese, CLARA's product default.
 * Browser updates use the same custom/storage events as the app shell, so a
 * language change updates independently-mounted consumer components too.
 */
export function useUILanguage(): UILanguage {
  return useSyncExternalStore(
    onUILanguageChange,
    getStoredUILanguage,
    () => "vi",
  );
}
