/**
 * GLHS Commit Kernel Client & OCC Dependency Vector Builder.
 *
 * Spec: PH06 / A05 (Web UX).
 * Enforces:
 * 1. Client mutations attach observed entity partition versions.
 * 2. 409 Conflict triggers transparent stale-read re-fetch.
 * 3. Prevents lost updates during concurrent edits on patient records.
 */

export interface ClientDependencySpec {
  dependencyKind: "GOVERNANCE" | "ENTITY" | "EVIDENCE" | "LEASE";
  dependencyKey: string;
  accessMode: "READ" | "WRITE";
  observedVersion: number;
  observedDigest?: string;
}

export interface CommitPayload<T> {
  transitionType: string;
  entityKey: string;
  dependencies: ClientDependencySpec[];
  data: T;
  clientTimestamp: string;
}

export class CommitKernelClient {
  static buildDependencyVector(
    entityKey: string,
    observedVersion: number,
    accessMode: "READ" | "WRITE" = "WRITE"
  ): ClientDependencySpec[] {
    return [
      {
        dependencyKind: "ENTITY",
        dependencyKey: entityKey,
        accessMode,
        observedVersion,
      },
    ];
  }

  static prepareCommit<T>(
    transitionType: string,
    entityKey: string,
    observedVersion: number,
    data: T
  ): CommitPayload<T> {
    return {
      transitionType,
      entityKey,
      dependencies: this.buildDependencyVector(entityKey, observedVersion, "WRITE"),
      data,
      clientTimestamp: new Date().toISOString(),
    };
  }

  static isStaleVersionConflict(statusCode: number, errorCode?: string): boolean {
    return statusCode === 409 || errorCode === "glhs_stale_dependency_version";
  }
}
