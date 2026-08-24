import { useEffect, useRef, useState } from "react";
import { sceneRegistry } from "./scene-observer";
import { scrollCoordinator } from "./scroll-coordinator";

export interface UseSceneProgressOptions {
  sticky?: boolean;
  onProgress?: (progress: number) => void;
}

export interface UseSceneProgressResult<T extends HTMLElement = HTMLElement> {
  ref: React.RefObject<T>;
  progress: number;
  isVisible: boolean;
}

export function useSceneProgress<T extends HTMLElement = HTMLElement>(
  sceneId: string,
  options?: UseSceneProgressOptions
): UseSceneProgressResult<T> {
  const ref = useRef<T>(null);
  const [progress, setProgress] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    // Ensure the single global scroll coordinator is active
    scrollCoordinator.start();

    const el = ref.current;
    if (!el) return;

    const unregister = sceneRegistry.register(sceneId, el, {
      sticky: optionsRef.current?.sticky,
      onProgress: (p) => {
        setProgress(p);
        if (optionsRef.current?.onProgress) {
          optionsRef.current.onProgress(p);
        }
      },
    });

    const unsubscribe = sceneRegistry.subscribeActiveScene((activeId) => {
      setIsVisible(activeId === sceneId);
    });

    return () => {
      unregister();
      unsubscribe();
    };
  }, [sceneId]);

  return { ref, progress, isVisible };
}
