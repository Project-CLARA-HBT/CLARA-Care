import { useEffect, useRef, useState } from "react";
import { sceneRegistry } from "./scene-registry";

export interface UseSceneProgressOptions {
  sticky?: boolean;
  onProgress?: (progress: number) => void;
}

export function useSceneProgress<T extends HTMLElement = HTMLElement>(
  sceneId: string,
  options?: UseSceneProgressOptions
) {
  const ref = useRef<T | null>(null);
  const [progress, setProgress] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
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
