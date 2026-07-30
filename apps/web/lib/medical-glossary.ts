import type { UILanguage } from "@/lib/ui-language";

/**
 * Versioned, static consumer glossary. This is presentation-only data: it
 * never infers a condition, interprets a medication, or changes a released
 * safety disposition. Callers must pass an explicit concept id or an exact
 * reference returned by a trusted, structured response.
 */
export const MEDICAL_GLOSSARY_VERSION = "2026-07-30.v1" as const;

export type MedicalGlossaryAudience = "lay" | "expanded" | "professional";

export type MedicalConceptId =
  | "adverse_effect"
  | "allergy"
  | "clinical_review"
  | "health_record"
  | "medication_interaction"
  | "source"
  | "symptom"
  | "uncertainty";

export type MedicalGlossaryText = {
  label: string;
  description: string;
};

export type MedicalGlossaryEntry = {
  id: MedicalConceptId;
  aliases: readonly string[];
  do_not_simplify_to: readonly string[];
  text: Record<UILanguage, Record<MedicalGlossaryAudience, MedicalGlossaryText>>;
};

/**
 * These descriptions intentionally describe communication concepts, not a
 * person's clinical state. "do_not_simplify_to" is display guidance for a
 * renderer/reviewer, never a rewrite rule for free text.
 */
export const MEDICAL_GLOSSARY: Readonly<Record<MedicalConceptId, MedicalGlossaryEntry>> = {
  adverse_effect: {
    id: "adverse_effect",
    aliases: ["adverse effect", "side effect", "tác dụng phụ", "phản ứng có hại"],
    do_not_simplify_to: ["không hợp thuốc", "thuốc độc"],
    text: {
      vi: {
        lay: {
          label: "Tác dụng phụ",
          description: "Một thay đổi không mong muốn có thể xảy ra khi dùng thuốc.",
        },
        expanded: {
          label: "Tác dụng phụ",
          description:
            "Đây là cách gọi một thay đổi không mong muốn được ghi nhận khi dùng thuốc. Thuật ngữ này không tự xác định nguyên nhân hay mức độ nghiêm trọng.",
        },
        professional: {
          label: "Adverse effect",
          description:
            "Thuật ngữ mô tả một tác động không mong muốn liên quan đến việc dùng thuốc; cần giữ nguyên bối cảnh, thời điểm và nguồn ghi nhận.",
        },
      },
      en: {
        lay: {
          label: "Side effect",
          description: "An unwanted change that may occur while taking a medicine.",
        },
        expanded: {
          label: "Side effect",
          description:
            "This names an unwanted change recorded while a medicine is being used. It does not by itself establish the cause or severity.",
        },
        professional: {
          label: "Adverse effect",
          description:
            "A term for an unwanted effect associated with medicine use; preserve its context, timing and recorded source.",
        },
      },
    },
  },
  allergy: {
    id: "allergy",
    aliases: ["allergy", "drug allergy", "dị ứng", "dị ứng thuốc"],
    do_not_simplify_to: ["không hợp", "tác dụng phụ"],
    text: {
      vi: {
        lay: {
          label: "Dị ứng",
          description: "Thông tin cho biết cơ thể từng có phản ứng dị ứng được ghi nhận.",
        },
        expanded: {
          label: "Dị ứng",
          description:
            "Mục này lưu thông tin về một phản ứng dị ứng đã được ghi nhận hoặc người dùng tự khai. Nó không thay thế việc xác minh của nhân viên y tế.",
        },
        professional: {
          label: "Allergy",
          description:
            "Nhận định hoặc tiền sử phản ứng dị ứng được ghi nhận; không đồng nhất với tác dụng phụ hay không dung nạp.",
        },
      },
      en: {
        lay: {
          label: "Allergy",
          description: "Information that a possible allergic reaction has been recorded.",
        },
        expanded: {
          label: "Allergy",
          description:
            "This records a reported or documented allergic reaction. It does not replace verification by a health professional.",
        },
        professional: {
          label: "Allergy",
          description:
            "A recorded allergic-reaction history or assessment; it is not interchangeable with an adverse effect or intolerance.",
        },
      },
    },
  },
  clinical_review: {
    id: "clinical_review",
    aliases: ["clinical review", "medical review", "khám lại", "đánh giá y tế"],
    do_not_simplify_to: ["chẩn đoán", "đã được bác sĩ xác nhận"],
    text: {
      vi: {
        lay: {
          label: "Trao đổi với nhân viên y tế",
          description: "Một bước để cùng xem lại thông tin và quyết định phù hợp.",
        },
        expanded: {
          label: "Cần được nhân viên y tế xem lại",
          description:
            "CLARA dùng cụm này khi thông tin cần được một bác sĩ hoặc nhân viên y tế có thẩm quyền xem trong bối cảnh đầy đủ. Đây không phải là chẩn đoán.",
        },
        professional: {
          label: "Clinical review",
          description:
            "Đề nghị đánh giá bởi nhân viên y tế; không thể hiện một kết luận chẩn đoán hoặc quyết định điều trị.",
        },
      },
      en: {
        lay: {
          label: "Discuss with a health professional",
          description: "A step to review the information together and decide what is appropriate.",
        },
        expanded: {
          label: "Needs review by a health professional",
          description:
            "CLARA uses this when information needs a clinician or authorised health professional to consider the full context. It is not a diagnosis.",
        },
        professional: {
          label: "Clinical review",
          description:
            "A recommendation for assessment by a health professional; it does not represent a diagnostic conclusion or treatment decision.",
        },
      },
    },
  },
  health_record: {
    id: "health_record",
    aliases: ["health record", "phr", "personal health record", "hồ sơ sức khỏe", "hồ sơ cá nhân"],
    do_not_simplify_to: ["bệnh án chính thức", "hồ sơ bệnh viện"],
    text: {
      vi: {
        lay: {
          label: "Hồ sơ sức khỏe",
          description: "Nơi bạn lưu và xem lại thông tin sức khỏe của mình.",
        },
        expanded: {
          label: "Hồ sơ sức khỏe cá nhân",
          description:
            "Đây là bản ghi do bạn quản lý trong CLARA. Mỗi mục có thể có nguồn và trạng thái riêng; không phải mọi mục đều đã được xác nhận lâm sàng.",
        },
        professional: {
          label: "Personal health record (PHR)",
          description:
            "Bản ghi sức khỏe cá nhân với nguồn gốc và trạng thái xác nhận theo từng mục; không đồng nghĩa với hồ sơ bệnh án của cơ sở y tế.",
        },
      },
      en: {
        lay: {
          label: "Health record",
          description: "A place to save and review your own health information.",
        },
        expanded: {
          label: "Personal health record",
          description:
            "This is a record you manage in CLARA. Each item can have its own source and status; not every item has been clinically confirmed.",
        },
        professional: {
          label: "Personal health record (PHR)",
          description:
            "A person-managed health record with per-item provenance and verification state; it is not the same as an institution's medical record.",
        },
      },
    },
  },
  medication_interaction: {
    id: "medication_interaction",
    aliases: ["drug interaction", "medication interaction", "ddi", "tương tác thuốc"],
    do_not_simplify_to: ["không được dùng", "đổi thuốc ngay"],
    text: {
      vi: {
        lay: {
          label: "Tương tác thuốc",
          description: "Thông tin về cách các thuốc có thể ảnh hưởng lẫn nhau.",
        },
        expanded: {
          label: "Kiểm tra tương tác thuốc",
          description:
            "CLARA đối chiếu tên thuốc đã xác nhận với nguồn dữ liệu thuốc phù hợp. Kết quả cần được đọc cùng bối cảnh và không tự thay đổi thuốc hoặc liều dùng.",
        },
        professional: {
          label: "Drug–drug interaction (DDI)",
          description:
            "Thông tin tương tác chỉ được hiển thị từ nguồn dữ liệu thuốc có thẩm quyền; không phải chỉ định kê đơn hoặc thay đổi liều.",
        },
      },
      en: {
        lay: {
          label: "Medication interaction",
          description: "Information about how medicines may affect one another.",
        },
        expanded: {
          label: "Medication interaction check",
          description:
            "CLARA compares confirmed medicine names with an appropriate medicine data source. Read the result in context; it never changes a medicine or dose on its own.",
        },
        professional: {
          label: "Drug–drug interaction (DDI)",
          description:
            "Interaction information is shown only from an authoritative medicine data source; it is not a prescription or a dose-change instruction.",
        },
      },
    },
  },
  source: {
    id: "source",
    aliases: ["source", "citation", "evidence source", "nguồn", "trích dẫn"],
    do_not_simplify_to: ["đã được chứng minh", "chắc chắn đúng"],
    text: {
      vi: {
        lay: {
          label: "Nguồn",
          description: "Nơi thông tin được lấy hoặc đối chiếu.",
        },
        expanded: {
          label: "Nguồn thông tin",
          description:
            "Nguồn giúp bạn kiểm tra CLARA dựa vào đâu. Có nguồn không tự bảo đảm rằng thông tin phù hợp với hoàn cảnh của bạn.",
        },
        professional: {
          label: "Source / citation",
          description:
            "Thông tin về xuất xứ của một nhận định hoặc dữ liệu; nguồn gốc không thay cho đánh giá về mức độ phù hợp hay chất lượng.",
        },
      },
      en: {
        lay: {
          label: "Source",
          description: "Where information was obtained or checked.",
        },
        expanded: {
          label: "Information source",
          description:
            "A source lets you check what CLARA used. Having a source does not itself mean the information fits your situation.",
        },
        professional: {
          label: "Source / citation",
          description:
            "Provenance for a claim or data item; provenance does not replace an assessment of applicability or quality.",
        },
      },
    },
  },
  symptom: {
    id: "symptom",
    aliases: ["symptom", "triệu chứng", "dấu hiệu"],
    do_not_simplify_to: ["bệnh", "chẩn đoán"],
    text: {
      vi: {
        lay: {
          label: "Triệu chứng",
          description: "Điều bạn cảm nhận hoặc nhận thấy về cơ thể.",
        },
        expanded: {
          label: "Triệu chứng",
          description:
            "Triệu chứng là thông tin mô tả trải nghiệm hoặc thay đổi được nhận thấy. Nó không tự cho biết nguyên nhân hay tên bệnh.",
        },
        professional: {
          label: "Symptom",
          description:
            "Biểu hiện do người dùng báo cáo hoặc được ghi nhận; không đồng nghĩa với chẩn đoán hoặc nguyên nhân.",
        },
      },
      en: {
        lay: {
          label: "Symptom",
          description: "Something you feel or notice about your body.",
        },
        expanded: {
          label: "Symptom",
          description:
            "A symptom describes an experience or noticed change. It does not by itself identify a cause or condition.",
        },
        professional: {
          label: "Symptom",
          description:
            "A reported or recorded manifestation; it is not equivalent to a diagnosis or cause.",
        },
      },
    },
  },
  uncertainty: {
    id: "uncertainty",
    aliases: ["uncertainty", "not confirmed", "chưa chắc chắn", "chưa xác nhận"],
    do_not_simplify_to: ["sai", "không quan trọng"],
    text: {
      vi: {
        lay: {
          label: "Phần chưa chắc chắn",
          description: "Thông tin còn thiếu, chưa rõ hoặc cần được kiểm tra thêm.",
        },
        expanded: {
          label: "Điều CLARA chưa thể khẳng định",
          description:
            "CLARA nêu rõ phần thông tin chưa đủ hoặc chưa được xác nhận thay vì suy đoán. Bạn có thể bổ sung nguồn hoặc trao đổi với nhân viên y tế khi phù hợp.",
        },
        professional: {
          label: "Uncertainty",
          description:
            "Trạng thái thiếu dữ liệu, mơ hồ hoặc chưa xác minh; không được chuyển thành khẳng định hoặc xác nhận tự động.",
        },
      },
      en: {
        lay: {
          label: "What is still uncertain",
          description: "Information that is missing, unclear or needs another check.",
        },
        expanded: {
          label: "What CLARA cannot confirm yet",
          description:
            "CLARA states when information is insufficient or unconfirmed instead of guessing. You can add a source or discuss it with a health professional when appropriate.",
        },
        professional: {
          label: "Uncertainty",
          description:
            "A state of incomplete, ambiguous or unverified information; it must not be turned into an assertion or automatic confirmation.",
        },
      },
    },
  },
};

function normalizedReference(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLocaleLowerCase("en-US")
    .replace(/\s+/g, " ");
}

const GLOSSARY_REFERENCE_INDEX: ReadonlyMap<string, MedicalConceptId> = new Map(
  Object.values(MEDICAL_GLOSSARY).flatMap((entry) =>
    [entry.id, ...entry.aliases].map((reference) => [normalizedReference(reference), entry.id] as const),
  ),
);

export function resolveMedicalConcept(reference: string | null | undefined): MedicalConceptId | null {
  if (!reference) return null;
  return GLOSSARY_REFERENCE_INDEX.get(normalizedReference(reference)) ?? null;
}

export function getMedicalGlossaryEntry(
  reference: MedicalConceptId | string | null | undefined,
): MedicalGlossaryEntry | null {
  const conceptId = resolveMedicalConcept(reference);
  return conceptId ? MEDICAL_GLOSSARY[conceptId] : null;
}

export function getMedicalGlossaryText(
  reference: MedicalConceptId | string | null | undefined,
  locale: UILanguage,
  audience: MedicalGlossaryAudience = "lay",
): MedicalGlossaryText | null {
  return getMedicalGlossaryEntry(reference)?.text[locale][audience] ?? null;
}
