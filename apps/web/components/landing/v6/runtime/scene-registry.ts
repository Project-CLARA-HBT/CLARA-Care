export interface RegisteredScene {
  id: string;
  element: HTMLElement;
  isIntersecting: boolean;
  intersectionRatio: number;
  onProgress?: (progress: number) => void;
  sticky?: boolean;
}

export type SceneChangeCallback = (activeId: string | null) => void;

class SceneRegistry {
  private scenes = new Map<string, RegisteredScene>();
  private observer: IntersectionObserver | null = null;
  private listeners = new Set<SceneChangeCallback>();
  private activeSceneId: string | null = null;

  private initObserver() {
    if (
      typeof window === "undefined" ||
      typeof IntersectionObserver === "undefined" ||
      this.observer
    ) {
      return;
    }

    this.observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const target = entry.target as HTMLElement;
          const id = target.dataset.sceneId;
          if (!id) return;

          const scene = this.scenes.get(id);
          if (scene) {
            scene.isIntersecting = entry.isIntersecting;
            scene.intersectionRatio = entry.intersectionRatio;
          }
        });

        this.updateActiveScene();
      },
      {
        root: null,
        rootMargin: "-10% 0px -10% 0px",
        threshold: [0, 0.1, 0.25, 0.5, 0.75, 1.0],
      }
    );

    // Observe already registered elements
    this.scenes.forEach((scene) => {
      this.observer?.observe(scene.element);
    });
  }

  register(
    id: string,
    element: HTMLElement,
    options?: { sticky?: boolean; onProgress?: (progress: number) => void }
  ): () => void {
    element.dataset.sceneId = id;
    const scene: RegisteredScene = {
      id,
      element,
      isIntersecting: false,
      intersectionRatio: 0,
      sticky: options?.sticky,
      onProgress: options?.onProgress,
    };

    this.scenes.set(id, scene);
    this.initObserver();
    this.observer?.observe(element);

    return () => {
      this.observer?.unobserve(element);
      this.scenes.delete(id);
      if (this.activeSceneId === id) {
        this.updateActiveScene();
      }
    };
  }

  updateProgressCallback(id: string, onProgress?: (progress: number) => void) {
    const scene = this.scenes.get(id);
    if (scene) {
      scene.onProgress = onProgress;
    }
  }

  getIntersectingScenes(): RegisteredScene[] {
    return Array.from(this.scenes.values()).filter((s) => s.isIntersecting);
  }

  getAllScenes(): RegisteredScene[] {
    return Array.from(this.scenes.values());
  }

  getActiveSceneId(): string | null {
    return this.activeSceneId;
  }

  subscribeActiveScene(callback: SceneChangeCallback): () => void {
    this.listeners.add(callback);
    callback(this.activeSceneId);
    return () => {
      this.listeners.delete(callback);
    };
  }

  private updateActiveScene() {
    let highestRatio = 0;
    let mostVisibleId: string | null = null;

    this.scenes.forEach((scene) => {
      if (scene.isIntersecting && scene.intersectionRatio > highestRatio) {
        highestRatio = scene.intersectionRatio;
        mostVisibleId = scene.id;
      }
    });

    if (mostVisibleId !== this.activeSceneId) {
      this.activeSceneId = mostVisibleId;
      this.listeners.forEach((cb) => cb(this.activeSceneId));
    }
  }

  destroy() {
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    this.scenes.clear();
    this.listeners.clear();
    this.activeSceneId = null;
  }
}

export const sceneRegistry = new SceneRegistry();
