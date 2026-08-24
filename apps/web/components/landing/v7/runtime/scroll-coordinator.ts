import { sceneRegistry } from "./scene-registry";

class ScrollCoordinator {
  private isListening = false;
  private isRunning = false;
  private rafId: number | null = null;
  private subscribers = new Set<(scrollY: number) => void>();
  private lastScrollY = -1;
  private idleFrames = 0;
  private maxIdleFrames = 10;

  start() {
    if (typeof window === "undefined" || this.isListening) return;

    window.addEventListener("scroll", this.onScroll, { passive: true });
    window.addEventListener("resize", this.onResize, { passive: true });
    this.isListening = true;

    // Run initial frame
    this.wakeLoop();
  }

  stop() {
    if (typeof window === "undefined") return;

    window.removeEventListener("scroll", this.onScroll);
    window.removeEventListener("resize", this.onResize);
    this.isListening = false;

    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.isRunning = false;
    this.subscribers.clear();
  }

  subscribe(callback: (scrollY: number) => void): () => void {
    this.subscribers.add(callback);
    this.wakeLoop();
    return () => {
      this.subscribers.delete(callback);
    };
  }

  private onScroll = () => {
    this.idleFrames = 0;
    this.wakeLoop();
  };

  private onResize = () => {
    this.idleFrames = 0;
    this.wakeLoop();
  };

  private wakeLoop() {
    if (!this.isRunning) {
      this.isRunning = true;
      this.rafId = requestAnimationFrame(this.tick);
    }
  }

  private tick = () => {
    if (!this.isRunning) return;

    const currentScrollY = window.scrollY || window.pageYOffset || 0;
    const isScrolling = Math.abs(currentScrollY - this.lastScrollY) > 0.5;
    this.lastScrollY = currentScrollY;

    // Notify scroll subscribers
    this.subscribers.forEach((cb) => cb(currentScrollY));

    // Calculate progress for active intersecting scenes only
    const intersectingScenes = sceneRegistry.getIntersectingScenes();
    const windowHeight = window.innerHeight || 800;

    intersectingScenes.forEach((scene) => {
      const rect = scene.element.getBoundingClientRect();

      let progress = 0;
      if (scene.sticky) {
        // Sticky progression: from when top hits 0 to when bottom leaves top
        const totalTravel = rect.height - windowHeight;
        if (totalTravel > 0) {
          const traveled = -rect.top;
          progress = Math.min(Math.max(traveled / totalTravel, 0), 1);
        } else {
          progress = rect.top <= 0 ? 1 : 0;
        }
      } else {
        // Standard progression: from bottom entering screen to top leaving screen
        const start = windowHeight;
        const total = windowHeight + rect.height;
        const current = windowHeight - rect.top;
        progress = Math.min(Math.max(current / total, 0), 1);
      }

      // Fast write to CSS custom property
      scene.element.style.setProperty("--scene-progress", progress.toFixed(4));

      // Invoke JS callback if attached
      if (scene.onProgress) {
        scene.onProgress(progress);
      }
    });

    if (!isScrolling) {
      this.idleFrames++;
    } else {
      this.idleFrames = 0;
    }

    // If no scroll changes for several frames, pause the RAF loop to save battery
    if (this.idleFrames > this.maxIdleFrames) {
      this.isRunning = false;
      this.rafId = null;
    } else {
      this.rafId = requestAnimationFrame(this.tick);
    }
  };
}

export const scrollCoordinator = new ScrollCoordinator();
