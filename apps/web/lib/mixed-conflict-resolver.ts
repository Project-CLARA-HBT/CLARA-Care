/**
 * Mixed Conflict Resolution & Staleness Classifier (Lease / Consent / OCC Version).
 *
 * Spec: PH08 / A05 (Web UX).
 * Classifies HTTP 409 / 403 conflict responses into precise actionable clinical UX guidance:
 * 1. OCC_VERSION_STALE: Another clinician committed a change; auto-refresh state.
 * 2. LEASE_EXPIRED: Exclusive consultation lease expired; prompt re-acquisition.
 * 3. CONSENT_REVOKED: Patient revoked purpose consent mid-flight; hard-stop action.
 * 4. POLICY_DRIFT: Central clinical safety guidelines updated; prompt acknowledgment.
 */

export type ConflictCategory =
  | "OCC_VERSION_STALE"
  | "LEASE_EXPIRED"
  | "CONSENT_REVOKED"
  | "POLICY_DRIFT"
  | "UNKNOWN_CONFLICT";

export interface ConflictResolutionGuide {
  category: ConflictCategory;
  titleVi: string;
  titleEn: string;
  actionVi: string;
  actionEn: string;
  autoRetryAllowed: boolean;
}

export class MixedConflictResolver {
  static classify(
    statusCode: number,
    errorCode?: string,
    detailMessage?: string
  ): ConflictResolutionGuide {
    const code = (errorCode ?? "").toLowerCase();
    const msg = (detailMessage ?? "").toLowerCase();

    if (code.includes("consent") || msg.includes("consent") || statusCode === 403) {
      return {
        category: "CONSENT_REVOKED",
        titleVi: "Sự đồng ý đã bị rút lại",
        titleEn: "Consent Revoked",
        actionVi: "Bệnh nhân đã thay đổi quyền riêng tư. Dừng thao tác dữ liệu.",
        actionEn: "Patient revoked data processing consent. Operation halted.",
        autoRetryAllowed: false,
      };
    }

    if (code.includes("lease") || msg.includes("lease")) {
      return {
        category: "LEASE_EXPIRED",
        titleVi: "Phiên giữ quyền chỉnh sửa đã hết hạn",
        titleEn: "Editing Lease Expired",
        actionVi: "Yêu cầu cấp lại quyền chỉnh sửa độc quyền.",
        actionEn: "Re-acquire exclusive editing lease.",
        autoRetryAllowed: false,
      };
    }

    if (code.includes("policy") || msg.includes("policy")) {
      return {
        category: "POLICY_DRIFT",
        titleVi: "Chính sách an toàn y tế đã cập nhật",
        titleEn: "Clinical Safety Policy Updated",
        actionVi: "Tải lại trang để áp dụng phiên bản hướng dẫn mới.",
        actionEn: "Refresh page to apply updated clinical guidelines.",
        autoRetryAllowed: false,
      };
    }

    if (statusCode === 409 || code.includes("version") || code.includes("stale")) {
      return {
        category: "OCC_VERSION_STALE",
        titleVi: "Dữ liệu vừa được cập nhật bởi người khác",
        titleEn: "Data Updated Concurrently",
        actionVi: "Hệ thống đang tải dữ liệu mới nhất để bạn kiểm tra lại.",
        actionEn: "Refreshing latest changes for your review.",
        autoRetryAllowed: true,
      };
    }

    return {
      category: "UNKNOWN_CONFLICT",
      titleVi: "Xung đột thao tác",
      titleEn: "Operation Conflict",
      actionVi: "Vui lòng tải lại và thử lại.",
      actionEn: "Please refresh and retry.",
      autoRetryAllowed: false,
    };
  }
}
