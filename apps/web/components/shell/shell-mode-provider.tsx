"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { IconName } from "@/components/ui/icon";

/**
 * 5 Shell Display Modes:
 * - explore: Full navigation, rich contextual cards, discoverability.
 * - focus: Distraction-free for active input, consultations, or task execution.
 * - immersive: Fullscreen canvas where navigation recedes (Chat, Scribe, Council, Canvas).
 * - read: Optimized reading width and typography for clinical literature and leaflets.
 * - dense: High information density mode for clinician dashboards and data matrices.
 */
export type ShellDisplayMode = "explore" | "focus" | "immersive" | "read" | "dense";
export type ShellMode = ShellDisplayMode;

/**
 * 5 Primary Dock Morph States:
 * - EXPANDED: Full floating pill dock with icons, labels, badges and quick actions.
 * - COMPACT: Icon-only pill dock with tooltips and active indicator.
 * - ORB_ONLY: Minimized to the glowing CLARA Orb floating trigger.
 * - CONTEXTUAL: Adapts dock to current active entity or workflow actions.
 * - HIDDEN_WITH_ESCAPE: Hidden via Escape or user toggle, with subtle reveal trigger.
 */
export type DockMorphState =
  | "EXPANDED"
  | "COMPACT"
  | "ORB_ONLY"
  | "CONTEXTUAL"
  | "HIDDEN_WITH_ESCAPE";

/**
 * 7 CLARA Orb Interaction States:
 * - idle: Ambient calm breathing glow.
 * - hover: Interactive radiant highlight.
 * - listening: Active voice/input listening wave.
 * - processing: Revolving orbital shimmer indicating RAG/reasoning synthesis.
 * - ready: Action/response ready with crisp electric highlight.
 * - attention: Triage alert, caution, or pending notification beacon.
 * - error: Guardrail boundary block or network warning state.
 */
export type ClaraOrbState =
  | "idle"
  | "hover"
  | "listening"
  | "processing"
  | "ready"
  | "attention"
  | "error";

export type EntityType =
  | "patient"
  | "medication"
  | "consultation"
  | "visit"
  | "document"
  | "profile"
  | "topic"
  | "custom";

export interface ShellActiveEntity {
  id: string;
  type: EntityType;
  label: string;
  sublabel?: string;
  badge?: string;
  meta?: string;
  icon?: IconName;
  href?: string;
  onClear?: () => void;
}

export interface ShellModeMeta {
  id: ShellDisplayMode;
  labelVi: string;
  labelEn: string;
  descVi: string;
  descEn: string;
  icon: IconName;
}

export const SHELL_MODES_CONFIG: Record<ShellDisplayMode, ShellModeMeta> = {
  explore: {
    id: "explore",
    labelVi: "Khám phá",
    labelEn: "Explore",
    descVi: "Giao diện đầy đủ, mở rộng thông tin & điều hướng",
    descEn: "Full navigation with rich contextual guidance",
    icon: "calendar",
  },
  focus: {
    id: "focus",
    labelVi: "Tập trung",
    labelEn: "Focus",
    descVi: "Giảm thiểu sao nhãng, tập trung xử lý công việc",
    descEn: "Distraction-free for active clinical work",
    icon: "edit",
  },
  immersive: {
    id: "immersive",
    labelVi: "Toàn màn hình",
    labelEn: "Immersive",
    descVi: "Mở rộng tối đa không gian làm việc chuyên sâu",
    descEn: "Maximized canvas for deep workflows",
    icon: "zoom-in",
  },
  read: {
    id: "read",
    labelVi: "Đọc tài liệu",
    labelEn: "Reading",
    descVi: "Tối ưu hóa độ rộng và kiểu chữ cho văn bản y tế",
    descEn: "Comfortable typography for medical leaflets & guidelines",
    icon: "clinical-notes",
  },
  dense: {
    id: "dense",
    labelVi: "Dữ liệu cô đọng",
    labelEn: "Dense",
    descVi: "Tăng mật độ hiển thị bảng và dữ liệu lâm sàng",
    descEn: "High information density for clinical metrics",
    icon: "scan",
  },
};

export const SHELL_DISPLAY_MODES: ShellDisplayMode[] = [
  "explore",
  "focus",
  "immersive",
  "read",
  "dense",
];

export const DOCK_MORPH_STATES: DockMorphState[] = [
  "EXPANDED",
  "COMPACT",
  "ORB_ONLY",
  "CONTEXTUAL",
  "HIDDEN_WITH_ESCAPE",
];

export const CLARA_ORB_STATES: ClaraOrbState[] = [
  "idle",
  "hover",
  "listening",
  "processing",
  "ready",
  "attention",
  "error",
];

const SHELL_MODE_STORAGE_KEY = "clara_shell_display_mode";
const DOCK_STATE_STORAGE_KEY = "clara_shell_dock_state";

export interface ShellModeContextValue {
  // Shell Display Mode
  mode: ShellDisplayMode;
  setMode: (mode: ShellDisplayMode) => void;
  cycleMode: () => void;
  isExplore: boolean;
  isFocus: boolean;
  isImmersive: boolean;
  isRead: boolean;
  isDense: boolean;

  // Dock Morph State
  dockMorphState: DockMorphState;
  setDockMorphState: (state: DockMorphState) => void;
  cycleDockMorphState: () => void;
  isDockVisible: boolean;
  toggleDockVisibility: () => void;

  // CLARA Orb State
  orbState: ClaraOrbState;
  setOrbState: (state: ClaraOrbState) => void;

  // Active Entity Context
  activeEntity: ShellActiveEntity | null;
  setActiveEntity: (entity: ShellActiveEntity | null) => void;
  clearActiveEntity: () => void;

  // Command Palette
  isCommandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  openCommandPalette: () => void;
  closeCommandPalette: () => void;
  toggleCommandPalette: () => void;
}

export const ShellModeContext = createContext<ShellModeContextValue | null>(null);

export interface ShellModeProviderProps {
  children: ReactNode;
  initialMode?: ShellDisplayMode;
  initialDockState?: DockMorphState;
  initialOrbState?: ClaraOrbState;
  initialEntity?: ShellActiveEntity | null;
}

export function ShellModeProvider({
  children,
  initialMode,
  initialDockState,
  initialOrbState = "idle",
  initialEntity = null,
}: ShellModeProviderProps) {
  const [mode, setModeState] = useState<ShellDisplayMode>(initialMode ?? "explore");
  const [dockMorphState, setDockMorphStateState] = useState<DockMorphState>(
    initialDockState ?? "EXPANDED",
  );
  const [orbState, setOrbState] = useState<ClaraOrbState>(initialOrbState);
  const [activeEntity, setActiveEntity] = useState<ShellActiveEntity | null>(initialEntity);
  const [isCommandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Hydrate mode from localStorage if available
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SHELL_MODE_STORAGE_KEY) as ShellDisplayMode | null;
      if (stored && SHELL_DISPLAY_MODES.includes(stored)) {
        setModeState(stored);
      }
      const storedDock = window.localStorage.getItem(DOCK_STATE_STORAGE_KEY) as DockMorphState | null;
      if (storedDock && DOCK_MORPH_STATES.includes(storedDock)) {
        setDockMorphStateState(storedDock);
      }
    } catch {
      // LocalStorage access may fail in private mode
    }
  }, []);

  // Sync mode to document attribute for CSS targeting
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.dataset.shellMode = mode;
    }
  }, [mode]);

  const setMode = useCallback((nextMode: ShellDisplayMode) => {
    setModeState(nextMode);
    try {
      window.localStorage.setItem(SHELL_MODE_STORAGE_KEY, nextMode);
    } catch {
      // Persistence is optional
    }
  }, []);

  const cycleMode = useCallback(() => {
    setModeState((current) => {
      const currentIndex = SHELL_DISPLAY_MODES.indexOf(current);
      const nextIndex = (currentIndex + 1) % SHELL_DISPLAY_MODES.length;
      const nextMode = SHELL_DISPLAY_MODES[nextIndex];
      try {
        window.localStorage.setItem(SHELL_MODE_STORAGE_KEY, nextMode);
      } catch {
        // noop
      }
      return nextMode;
    });
  }, []);

  const setDockMorphState = useCallback((nextState: DockMorphState) => {
    setDockMorphStateState(nextState);
    try {
      window.localStorage.setItem(DOCK_STATE_STORAGE_KEY, nextState);
    } catch {
      // noop
    }
  }, []);

  const cycleDockMorphState = useCallback(() => {
    setDockMorphStateState((current) => {
      const currentIndex = DOCK_MORPH_STATES.indexOf(current);
      const nextIndex = (currentIndex + 1) % DOCK_MORPH_STATES.length;
      const nextState = DOCK_MORPH_STATES[nextIndex];
      try {
        window.localStorage.setItem(DOCK_STATE_STORAGE_KEY, nextState);
      } catch {
        // noop
      }
      return nextState;
    });
  }, []);

  const isDockVisible = dockMorphState !== "HIDDEN_WITH_ESCAPE";

  const toggleDockVisibility = useCallback(() => {
    setDockMorphStateState((current) => {
      const next = current === "HIDDEN_WITH_ESCAPE" ? "EXPANDED" : "HIDDEN_WITH_ESCAPE";
      try {
        window.localStorage.setItem(DOCK_STATE_STORAGE_KEY, next);
      } catch {
        // noop
      }
      return next;
    });
  }, []);

  const clearActiveEntity = useCallback(() => {
    if (activeEntity?.onClear) {
      activeEntity.onClear();
    }
    setActiveEntity(null);
  }, [activeEntity]);

  const openCommandPalette = useCallback(() => setCommandPaletteOpen(true), []);
  const closeCommandPalette = useCallback(() => setCommandPaletteOpen(false), []);
  const toggleCommandPalette = useCallback(
    () => setCommandPaletteOpen((prev) => !prev),
    [],
  );

  // Global Keyboard Shortcuts (Ctrl+K / Cmd+K, Escape)
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Toggle Command Palette on Cmd+K or Ctrl+K
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
        return;
      }

      // Escape key behavior: close palette if open, or toggle dock if focused outside inputs
      if (event.key === "Escape") {
        if (isCommandPaletteOpen) {
          event.preventDefault();
          setCommandPaletteOpen(false);
          return;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isCommandPaletteOpen]);

  const value = useMemo<ShellModeContextValue>(
    () => ({
      mode,
      setMode,
      cycleMode,
      isExplore: mode === "explore",
      isFocus: mode === "focus",
      isImmersive: mode === "immersive",
      isRead: mode === "read",
      isDense: mode === "dense",

      dockMorphState,
      setDockMorphState,
      cycleDockMorphState,
      isDockVisible,
      toggleDockVisibility,

      orbState,
      setOrbState,

      activeEntity,
      setActiveEntity,
      clearActiveEntity,

      isCommandPaletteOpen,
      setCommandPaletteOpen,
      openCommandPalette,
      closeCommandPalette,
      toggleCommandPalette,
    }),
    [
      mode,
      setMode,
      cycleMode,
      dockMorphState,
      setDockMorphState,
      cycleDockMorphState,
      isDockVisible,
      toggleDockVisibility,
      orbState,
      activeEntity,
      clearActiveEntity,
      isCommandPaletteOpen,
      openCommandPalette,
      closeCommandPalette,
      toggleCommandPalette,
    ],
  );

  return <ShellModeContext.Provider value={value}>{children}</ShellModeContext.Provider>;
}

const DEFAULT_SHELL_MODE_VALUE: ShellModeContextValue = {
  mode: "explore",
  setMode: () => {},
  cycleMode: () => {},
  isExplore: true,
  isFocus: false,
  isImmersive: false,
  isRead: false,
  isDense: false,

  dockMorphState: "EXPANDED",
  setDockMorphState: () => {},
  cycleDockMorphState: () => {},
  isDockVisible: true,
  toggleDockVisibility: () => {},

  orbState: "idle",
  setOrbState: () => {},

  activeEntity: null,
  setActiveEntity: () => {},
  clearActiveEntity: () => {},

  isCommandPaletteOpen: false,
  setCommandPaletteOpen: () => {},
  openCommandPalette: () => {},
  closeCommandPalette: () => {},
  toggleCommandPalette: () => {},
};

export function useShellMode(): ShellModeContextValue {
  const context = useContext(ShellModeContext);
  if (!context) {
    return DEFAULT_SHELL_MODE_VALUE;
  }
  return context;
}
