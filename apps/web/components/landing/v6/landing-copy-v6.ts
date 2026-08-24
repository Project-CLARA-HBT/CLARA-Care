import type { UILanguage } from "@/lib/ui-language";

export type LandingV6Copy = {
  languageLabel: string;
  languageNames: { vi: string; en: string };
  nav: {
    brand: string;
    brandTag: string;
    howItWorks: string;
    features: string;
    safety: string;
    clinical: string;
    login: string;
    askClara: string;
    openMenu: string;
    closeMenu: string;
    skipToContent: string;
  };
  hero: {
    badge: string;
    titleStart: string;
    titleAccent: string;
    titleEnd: string;
    description: string;
    primaryCta: string;
    secondaryCta: string;
    floatingContext1: {
      label: string;
      value: string;
      tag: string;
    };
    floatingContext2: {
      label: string;
      value: string;
      tag: string;
    };
    preview: {
      question: string;
      answerSummary: string;
      safetyBadge: string;
      sourceCitation: string;
      nextAction: string;
    };
  };
  trust: {
    eyebrow: string;
    title: string;
    description: string;
    sources: { name: string; type: string; authority: string }[];
  };
  manifesto: {
    eyebrow: string;
    headline: string;
    subheadline: string;
    nodes: {
      medications: string;
      recentChanges: string;
      healthRecord: string;
      pastQuestions: string;
      sources: string;
    };
    centerTitle: string;
    centerSubtitle: string;
    resolveStatement: string;
  };
  how: {
    eyebrow: string;
    title: string;
    description: string;
    steps: {
      number: string;
      title: string;
      description: string;
      stateBadge: string;
    }[];
  };
  chat: {
    eyebrow: string;
    title: string;
    description: string;
    directAnswerTitle: string;
    directAnswerBody: string;
    nextActionTitle: string;
    nextActionBody: string;
    uncertaintyTitle: string;
    uncertaintyBody: string;
    sourcesTitle: string;
    sourcesDisclaimer: string;
    advancedDetailTitle: string;
    advancedDetailBody: string;
    inspectorTitle: string;
    inspectorClose: string;
  };
  lifemap: {
    eyebrow: string;
    title: string;
    description: string;
    timeline: {
      period: string;
      title: string;
      detail: string;
      category: string;
      emphasis: "past" | "recent" | "today";
    }[];
    insightCallout: {
      tag: string;
      title: string;
      body: string;
      action: string;
    };
  };
  medicines: {
    eyebrow: string;
    title: string;
    description: string;
    tabs: {
      current: string;
      needsConfirmation: string;
      safetyCheck: string;
      cabinet: string;
    };
    truthNote: string;
    safetyTag: string;
    fidesVerified: string;
  };
  phr: {
    eyebrow: string;
    title: string;
    description: string;
    statement: string;
    patientName: string;
    patientMrn: string;
    sharingTitle: string;
    allowedSection: string;
    blockedSection: string;
    expiryLabel: string;
    expiryValue: string;
    revokeAction: string;
  };
  adaptive: {
    eyebrow: string;
    title: string;
    description: string;
    modes: {
      personal: {
        id: "personal";
        label: string;
        tagline: string;
        navItems: string[];
        headline: string;
        actionItem: string;
      };
      clinical: {
        id: "clinical";
        label: string;
        tagline: string;
        navItems: string[];
        headline: string;
        actionItem: string;
      };
      research: {
        id: "research";
        label: string;
        tagline: string;
        navItems: string[];
        headline: string;
        actionItem: string;
      };
    };
  };
  clinicalTransition: {
    eyebrow: string;
    headline: string;
    subheadline: string;
  };
  council: {
    eyebrow: string;
    title: string;
    description: string;
    disclaimer: string;
    caseContext: {
      patient: string;
      ageGender: string;
      chiefComplaint: string;
      vitals: string;
      activeMeds: string;
    };
    recommendationTitle: string;
    recommendationBody: string;
    disagreementsTitle: string;
    disagreementsBody: string;
    uncertaintyTitle: string;
    uncertaintyBody: string;
    nextStepsTitle: string;
    nextStepsBody: string;
    evidenceTitle: string;
    evidenceBody: string;
  };
  scribe: {
    eyebrow: string;
    title: string;
    description: string;
    states: {
      consent: { step: string; title: string; desc: string };
      recording: { step: string; title: string; desc: string; timer: string };
      transcript: { step: string; title: string; desc: string; text: string };
      soap: { step: string; title: string; desc: string; s: string; o: string; a: string; p: string };
      review: { step: string; title: string; desc: string; status: string };
    };
  };
  evidence: {
    eyebrow: string;
    title: string;
    editorial: string;
    description: string;
    selectHint: string;
    inspector: {
      relevance: string;
      applicability: string;
      limitations: string;
      authorityLevel: string;
      updated: string;
    };
  };
  safety: {
    eyebrow: string;
    title: string;
    description: string;
    principles: {
      number: string;
      title: string;
      description: string;
    }[];
  };
  privacy: {
    eyebrow: string;
    title: string;
    description: string;
    diagram: {
      source: string;
      gate: string;
      destination: string;
      allowedNote: string;
      blockedNote: string;
      revokeNote: string;
    };
  };
  scenarios: {
    eyebrow: string;
    title: string;
    description: string;
    items: {
      quote: string;
      context: string;
      resolution: string;
    }[];
  };
  comparison: {
    eyebrow: string;
    title: string;
    description: string;
    genericAi: {
      title: string;
      flow: string[];
      drawback: string;
    };
    claraCare: {
      title: string;
      flow: string[];
      benefit: string;
    };
  };
  faq: {
    eyebrow: string;
    title: string;
    description: string;
    items: {
      question: string;
      answer: string;
    }[];
  };
  finalCta: {
    eyebrow: string;
    title: string;
    description: string;
    primaryCta: string;
    secondaryCta: string;
    securityBadge: string;
  };
  footer: {
    tagline: string;
    disclaimer: string;
    columns: {
      product: { title: string; links: { label: string; href: string }[] };
      clinical: { title: string; links: { label: string; href: string }[] };
      trust: { title: string; links: { label: string; href: string }[] };
      company: { title: string; links: { label: string; href: string }[] };
    };
    copyright: string;
    terms: string;
    privacy: string;
    consent: string;
  };
};

export const LANDING_COPY_V6: Record<UILanguage, LandingV6Copy> = {
  vi: {
    languageLabel: "Ngôn ngữ",
    languageNames: { vi: "Tiếng Việt", en: "English" },
    nav: {
      brand: "CLARA Care",
      brandTag: "Trợ lý Y tế An toàn",
      howItWorks: "Cách hoạt động",
      features: "Tính năng",
      safety: "An toàn",
      clinical: "Chuyên gia",
      login: "Đăng nhập",
      askClara: "Hỏi CLARA",
      openMenu: "Mở menu điều hướng",
      closeMenu: "Đóng menu điều hướng",
      skipToContent: "Chuyển đến nội dung chính",
    },
    hero: {
      badge: "KIỂM CHỨNG FIDES • ZERO-COT SECURITY",
      titleStart: "Hiểu rõ điều đang xảy ra.",
      titleAccent: "Biết bước tiếp theo",
      titleEnd: "cần làm.",
      description:
        "Trợ lý AI y tế kết nối câu hỏi sức khỏe với bối cảnh thuốc, hồ sơ cá nhân, dòng thời gian và nguồn y văn chính thống. Minh bạch, an toàn và đồng hành cùng bác sĩ.",
      primaryCta: "Bắt đầu hỏi CLARA",
      secondaryCta: "Xem cách hoạt động",
      floatingContext1: {
        label: "Bối cảnh thuốc",
        value: "Metformin 500mg • Amlodipine 5mg",
        tag: "Đang theo dõi",
      },
      floatingContext2: {
        label: "Kiểm tra FIDES",
        value: "0 tương tác bất lợi nguy hiểm",
        tag: "Xác thực y văn",
      },
      preview: {
        question: "Tôi uống Metformin cùng Amlodipine thì có cần lưu ý gì khi đổi giờ ăn không?",
        answerSummary:
          "Hai thuốc này không có tương tác đối kháng trực tiếp, nhưng việc đổi giờ ăn có thể ảnh hưởng đến khả năng hấp thu Metformin và kiểm soát đường huyết sau ăn.",
        safetyBadge: "FIDES Safe",
        sourceCitation: "Dược thư Quốc gia VN 2022 • FDA Drug Safety",
        nextAction: "Duy trì uống Metformin ngay sau bữa chính để giảm kích ứng dạ dày.",
      },
    },
    trust: {
      eyebrow: "NGUỒN MINH BẠCH",
      title: "Nguồn rõ ràng. Giới hạn rõ ràng.",
      description:
        "CLARA chỉ trích xuất và đối chiếu từ cơ sở dữ liệu y khoa chính thống. Mọi phản hồi đều trích dẫn xuất xứ và nêu rõ phạm vi chưa chắc chắn.",
      sources: [
        { name: "WHO", type: "Tổ chức Y tế Thế giới", authority: "Hướng dẫn Điều trị Chuẩn" },
        { name: "PubMed / MEDLINE", type: "Y văn Quốc tế", authority: "Bằng chứng Thử nghiệm Lâm sàng" },
        { name: "FDA", type: "Cơ quan Quản lý Dược Hoa Kỳ", authority: "Cảnh báo Tương tác Dược phẩm" },
        { name: "DrugBank 5.1", type: "Dữ liệu Dược lý", authority: "Cơ chế Tác dụng & Chuyển hóa" },
        { name: "EMA", type: "Cơ quan Dược phẩm Châu Âu", authority: "An toàn Dược chất & Liều dùng" },
        { name: "DAV", type: "Cục Quản lý Dược VN", authority: "Dược thư Quốc gia Việt Nam" },
        { name: "PubChem", type: "Cơ sở Dữ liệu Hóa sinh", authority: "Cấu trúc & Động học Phân tử" },
      ],
    },
    manifesto: {
      eyebrow: "BỐI CẢNH TOÀN DIỆN",
      headline: "Một câu hỏi sức khỏe\nhiếm khi chỉ là một câu hỏi.",
      subheadline:
        "Đằng sau một triệu chứng là cả quá trình dùng thuốc, tiền sử dị ứng, hồ sơ bệnh án và những biến chuyển theo thời gian.",
      nodes: {
        medications: "Thuốc đang dùng",
        recentChanges: "Thay đổi gần đây",
        healthRecord: "Hồ sơ sức khỏe",
        pastQuestions: "Câu hỏi trước đây",
        sources: "Nguồn y văn đối chiếu",
      },
      centerTitle: "CLARA Core",
      centerSubtitle: "Hội tụ dữ liệu an toàn",
      resolveStatement: "Điều gì thực sự đáng chú ý lúc này?",
    },
    how: {
      eyebrow: "QUY TRÌNH 4 BƯỚC",
      title: "Cách CLARA xử lý một câu hỏi",
      description:
        "Không suy đoán tùy tiện. Mỗi câu trả lời được xây dựng qua chuỗi xử lý nghiêm ngặt từ bối cảnh đến an toàn dược lý.",
      steps: [
        {
          number: "01",
          title: "Bạn đặt câu hỏi",
          description: "Mô tả triệu chứng, thắc mắc về đơn thuốc hoặc cần chuẩn bị cho buổi khám sắp tới.",
          stateBadge: "Tiếp nhận câu hỏi",
        },
        {
          number: "02",
          title: "CLARA tìm bối cảnh liên quan",
          description: "Tự động rà soát danh mục thuốc đang dùng, tiền sử dị ứng và các sự kiện sức khỏe gần nhất.",
          stateBadge: "Khớp bối cảnh",
        },
        {
          number: "03",
          title: "Kiểm tra nguồn & an toàn FIDES",
          description: "Đối chiếu Dược thư, tài liệu chuyên môn và chạy thuật toán phát hiện tương tác thuốc đa tầng.",
          stateBadge: "Thẩm định an toàn",
        },
        {
          number: "04",
          title: "Trả lời rõ ràng & gợi ý bước tiếp",
          description: "Cung cấp câu trả lời trực diện, nêu rõ điểm chưa chắc chắn và hành động thực tế cần thực hiện.",
          stateBadge: "Phản hồi có cấu trúc",
        },
      ],
    },
    chat: {
      eyebrow: "TRẢI NGHIỆM TRÒ CHUYỆN",
      title: "Câu trả lời trước. Chi tiết khi bạn cần.",
      description:
        "Giao diện phản hồi có phân tầng rõ rệt: phần kết luận chính hiển thị ngay, chi tiết y văn và cơ chế chuyên sâu có thể mở rộng bất cứ lúc nào.",
      directAnswerTitle: "Câu trả lời trực tiếp",
      directAnswerBody:
        "Cảm giác mệt nhẹ và chóng mặt khi đứng dậy sau 3 ngày bắt đầu uống thuốc hạ áp có thể là hiện tượng hạ huyết áp tư thế tạm thời trong giai đoạn thích nghi.",
      nextActionTitle: "Bước tiếp theo cần làm",
      nextActionBody:
        "1. Đứng dậy chậm rãi từ tư thế ngồi hoặc nằm.\n2. Đo và ghi nhận huyết áp sáng - tối trong 3 ngày tới.\n3. Nếu huyết áp tâm thu < 90 mmHg hoặc chóng mặt kéo dài, liên hệ ngay bác sĩ điều trị.",
      uncertaintyTitle: "Điểm chưa đủ dữ liệu",
      uncertaintyBody:
        "Chưa có số đo huyết áp thực tế gần nhất tại nhà để đánh giá mức độ giảm áp cụ thể.",
      sourcesTitle: "Nguồn y văn đã đối chiếu",
      sourcesDisclaimer: "Nhấp vào nguồn để xem trích dẫn và phân tích chi tiết",
      advancedDetailTitle: "Chi tiết chuyên sâu & Cơ chế dược lý",
      advancedDetailBody:
        "Amlodipine là thuốc chẹn kênh canxi nhóm dihydropyridine, gây giãn mạch ngoại biên. Quá trình tái lập trương lực mạch thường mất 3–7 ngày.",
      inspectorTitle: "Chi tiết nguồn trích dẫn",
      inspectorClose: "Đóng cửa sổ tra cứu",
    },
    lifemap: {
      eyebrow: "DÒNG THỜI GIAN SỨC KHỎE",
      title: "Sức khỏe không phải một bức ảnh tĩnh.",
      description:
        "LifeMap liên kết các triệu chứng, lần đổi thuốc và kết quả xét nghiệm thành dòng thời gian liên tục giúp nhận ra mối liên hệ nhân quả.",
      timeline: [
        {
          period: "Tháng 4",
          title: "Khởi phát triệu chứng",
          detail: "Xuất hiện cơn đau đầu âm ỉ vùng chẩm vào buổi sáng sớm.",
          category: "Triệu chứng",
          emphasis: "past",
        },
        {
          period: "Tháng 5",
          title: "Bắt đầu phác đồ thuốc",
          detail: "Bác sĩ chỉ định Amlodipine 5mg/ngày sau khi đo HA 145/90 mmHg.",
          category: "Kê đơn",
          emphasis: "past",
        },
        {
          period: "Tháng 6",
          title: "Khám tái khám định kỳ",
          detail: "Huyết áp ổn định 125/80 mmHg, bổ sung xét nghiệm chức năng thận bình thường.",
          category: "Tái khám",
          emphasis: "recent",
        },
        {
          period: "Hôm nay",
          title: "Câu hỏi về điều chỉnh giờ uống",
          detail: "Cần tham vấn khi đổi lịch làm việc ban đêm và thay đổi thời điểm dùng thuốc.",
          category: "Tương tác mới",
          emphasis: "today",
        },
      ],
      insightCallout: {
        tag: "PHÁT HIỆN TỪ LIFEMAP",
        title: "Có một thay đổi đáng chú ý kể từ lần trước",
        body: "Huyết áp của bạn đã duy trì ở mức mục tiêu 60 ngày liên tục. Việc đổi giờ uống thuốc huyết áp nên được thực hiện cố định và tránh ngắt quãng quá 24 giờ.",
        action: "Xem toàn bộ dòng thời gian",
      },
    },
    medicines: {
      eyebrow: "QUẢN LÝ THUỐC AN TOÀN",
      title: "Không gian quản lý thuốc thống nhất",
      description:
        "Phân biệt rõ ràng giữa thuốc đang dùng thực tế, thuốc cần xác nhận và thuốc trong tủ gia đình. Hệ thống cảnh báo tự động kiểm tra tương tác chéo.",
      tabs: {
        current: "Đang dùng (2)",
        needsConfirmation: "Cần xác nhận (1)",
        safetyCheck: "Kiểm tra an toàn FIDES",
        cabinet: "Tủ thuốc gia đình (5)",
      },
      truthNote: "Tủ thuốc lưu trữ ≠ Thuốc đang uống hàng ngày. Không có cảnh báo không đồng nghĩa với tự ý phối hợp.",
      safetyTag: "FIDES Vetted",
      fidesVerified: "Đã kiểm chứng Dược thư Quốc gia & DrugBank",
    },
    phr: {
      eyebrow: "BẢO VỆ DỮ LIỆU & PHÂN QUYỀN",
      title: "Chia sẻ có ranh giới rõ ràng",
      description:
        "Bạn quyết định chính xác dữ liệu nào được chia sẻ, chia sẻ cho ai và trong bao lâu. Quyền truy cập có thể thu hồi tức thì chỉ với một thao tác.",
      statement: "Chia sẻ một phần không có nghĩa là chia sẻ toàn bộ hồ sơ.",
      patientName: "Nguyễn Văn An",
      patientMrn: "MRN-8842-VN",
      sharingTitle: "Gói chia sẻ cho Bác sĩ Tim mạch",
      allowedSection: "Dữ liệu được phép truyền (Được chia sẻ)",
      blockedSection: "Dữ liệu được giữ riêng tư (Bị chặn)",
      expiryLabel: "Thời hạn hiệu lực",
      expiryValue: "30 ngày (Hết hạn 24/09/2026)",
      revokeAction: "Thu hồi quyền ngay lập tức",
    },
    adaptive: {
      eyebrow: "MỘT KHUNG HỆ THỐNG DUY NHẤT",
      title: "Một CLARA. Thích nghi theo vai trò của bạn.",
      description:
        "Không phải ba ứng dụng rời rạc. Cùng một kiến trúc an toàn biến đổi mượt mà theo nhu cầu: Cá nhân, Bác sĩ lâm sàng, hay Nhà nghiên cứu y khoa.",
      modes: {
        personal: {
          id: "personal",
          label: "Chế độ Cá nhân",
          tagline: "Đồng hành sức khỏe hàng ngày",
          navItems: ["Hôm nay", "LifeMap", "CLARA", "Thuốc", "Hồ sơ"],
          headline: "Kế hoạch theo dõi hôm nay",
          actionItem: "Uống thuốc huyết áp đúng 08:00 • Đo huyết áp sau 30 phút",
        },
        clinical: {
          id: "clinical",
          label: "Chế độ Lâm sàng",
          tagline: "Trợ lý hỗ trợ quyết định bác sĩ",
          navItems: ["Tổng quan", "Council", "CLARA", "Scribe", "Thêm"],
          headline: "Hàng đợi hội chẩn lâm sàng",
          actionItem: "Ca #3102: Kháng đông + Suy thận mạn độ 3b (Cần đối chiếu tương tác)",
        },
        research: {
          id: "research",
          label: "Chế độ Nghiên cứu",
          tagline: "Khai phá y văn & bằng chứng sống",
          navItems: ["Nghiên cứu", "Evidence", "CLARA", "Nguồn", "Thêm"],
          headline: "Trung tâm đối chiếu y văn",
          actionItem: "Tổng hợp 14 thử nghiệm RCT về SGLT2i trên bệnh nhân suy tim bảo tồn",
        },
      },
    },
    clinicalTransition: {
      eyebrow: "CLARA CLINICAL",
      headline: "Công cụ chuyên sâu,\nkhi bạn cần chiều sâu chuyên môn.",
      subheadline: "Thiết kế chuẩn mực cho quy trình khám bệnh, hội chẩn đa chuyên khoa và trích xuất y văn.",
    },
    council: {
      eyebrow: "HỘI CHẨN ĐA CHUYÊN KHOA",
      title: "Từ phức tạp đa chiều đến kết luận có cấu trúc",
      description:
        "Council tổng hợp góc nhìn từ các chuyên khoa (Tim mạch, Thận học, Dược lâm sàng), làm nổi bật điểm đồng thuận, xung đột và chỉ ra ranh giới chuyên môn.",
      disclaimer: "CLARA không tự quyết định điều trị. Bác sĩ điều trị luôn là người đưa ra phán quyết cuối cùng.",
      caseContext: {
        patient: "Bệnh nhân Nam, 68 tuổi",
        ageGender: "Tiền sử Tăng huyết áp 10 năm, Đái tháo đường type 2, eGFR 38 mL/min",
        chiefComplaint: "Cần tối ưu hóa thuốc kiểm soát huyết áp và đường huyết sau khi xuất hiện phù nhẹ mắt cá chân.",
        vitals: "HA: 152/88 mmHg • HR: 74 bpm • Creatinine: 142 umol/L",
        activeMeds: "Metformin 1000mg/ngày, Amlodipine 5mg/ngày, Gliclazide 60mg/ngày",
      },
      recommendationTitle: "Khuyến nghị tổng hợp",
      recommendationBody:
        "1. Cân nhắc giảm liều hoặc tạm ngừng Metformin do eGFR < 45 mL/min để giảm nguy cơ nhiễm toan acid lactic.\n2. Xem xét chuyển đổi sang thuốc ức chế SGLT2 hoặc DPP-4 phù hợp với mức lọc cầu thận.\n3. Theo dõi sát điện giải đồ và chức năng thận sau 2 tuần.",
      disagreementsTitle: "Điểm bất đồng chuyên khoa cần lưu ý",
      disagreementsBody:
        "Dược lâm sàng đề xuất ngừng hẳn Metformin ngay; Tim mạch khuyến nghị giảm còn 500mg/ngày kèm theo dõi sát eGFR định kỳ hàng tháng.",
      uncertaintyTitle: "Dữ liệu còn thiếu cần bổ sung",
      uncertaintyBody: "Chưa có tỷ lệ Albumin/Creatinine niệu (uACR) gần nhất để đánh giá tổn thương thận màng lọc.",
      nextStepsTitle: "Hành động khuyến nghị cho Bác sĩ",
      nextStepsBody: "Chỉ định xét nghiệm uACR, điện giải đồ (K+, Na+) và hẹn tái khám sau 14 ngày.",
      evidenceTitle: "Nguồn y văn tham chiếu",
      evidenceBody: "KDIGO 2023 Clinical Practice Guideline • ADA Standards of Care 2024",
    },
    scribe: {
      eyebrow: "TRỢ LÝ GHI CHÉP Y KHOA",
      title: "Chuyển hóa dữ liệu cuộc khám theo thời gian thực",
      description:
        "Từ đồng thuận của bệnh nhân đến ghi âm, biên dịch thuật ngữ y khoa Việt Nam và tạo bệnh án cấu trúc SOAP sẵn sàng cho bác sĩ duyệt.",
      states: {
        consent: {
          step: "01",
          title: "Xác nhận đồng thuận",
          desc: "Bệnh nhân đồng ý ghi âm bảo mật với mã hóa đầu cuối.",
        },
        recording: {
          step: "02",
          title: "Ghi âm hội thoại",
          desc: "Thu âm giọng nói trực tiếp tại phòng khám với bộ lọc giảm ồn y tế.",
          timer: "02:45 • Đang thu âm",
        },
        transcript: {
          step: "03",
          title: "Biên phiên âm y khoa",
          desc: "Tự động chuẩn hóa thuật ngữ lâm sàng tiếng Việt và tiếng Anh.",
          text: "Bác sĩ: Bác thấy đau ngực lúc nào? — Bệnh nhân: Dạ lúc leo cầu thang tầng 2, đau thắt khoảng 3 phút rồi đỡ...",
        },
        soap: {
          step: "04",
          title: "Dự thảo bệnh án SOAP",
          desc: "Tự động trích xuất các mục Subjective, Objective, Assessment, Plan.",
          s: "Đau thắt ngực khi gắng sức nhẹ, kéo dài ~3 phút.",
          o: "HA: 135/85 mmHg, Tim đều, không tiếng thổi bệnh lý.",
          a: "Theo dõi Cơn đau thắt ngực ổn định (CCS II).",
          p: "Chỉ định Điện tâm đồ gắng sức, Siêu âm tim Doppler màu.",
        },
        review: {
          step: "05",
          title: "Bác sĩ xem xét & Ký duyệt",
          desc: "Bác sĩ chỉnh sửa, xác nhận và ký duyệt bệnh án trước khi lưu vào EMR.",
          status: "Sẵn sàng duyệt ký bởi BS",
        },
      },
    },
    evidence: {
      eyebrow: "TRUNG TÂM BẰNG CHỨNG Y VĂN",
      title: "Xem chính xác CLARA dựa vào đâu",
      editorial: "Không phải mọi nguồn đều có trọng lượng như nhau.",
      description:
        "Tra cứu nguồn dữ liệu theo cấp bậc chứng cứ: từ Hướng dẫn điều trị quốc gia, Thử nghiệm ngẫu nhiên có đối chứng (RCT), đến Cảnh báo dược phẩm khẩn cấp.",
      selectHint: "Chọn một nguồn trong danh sách để xem chi tiết mức độ tin cậy và giới hạn ứng dụng.",
      inspector: {
        relevance: "Lý do phù hợp",
        applicability: "Phạm vi áp dụng",
        limitations: "Giới hạn & Điểm lưu ý",
        authorityLevel: "Cấp bậc thẩm quyền",
        updated: "Cập nhật lần cuối",
      },
    },
    safety: {
      eyebrow: "NGUYÊN TẮC BẤT BIẾN",
      title: "An toàn là cốt lõi. Không phải tính năng phụ.",
      description: "Các nguyên tắc an toàn được mã hóa thành bất biến kỹ thuật, không thể bị ghi đè bởi câu lệnh.",
      principles: [
        {
          number: "01",
          title: "Nguồn trích dẫn rõ ràng",
          description: "Mọi thông tin y khoa đều gắn liền với tài liệu tham chiếu có thẩm quyền xác định.",
        },
        {
          number: "02",
          title: "Không che giấu điều chưa chắc chắn",
          description: "Nếu dữ liệu không đủ để kết luận, hệ thống lập tức thông báo thay vì đưa ra dự đoán mơ hồ.",
        },
        {
          number: "03",
          title: "Không gọi 'chưa kiểm tra' là 'an toàn'",
          description: "Dữ liệu chưa qua thẩm định FIDES sẽ được gắn nhãn Chưa xác minh một cách minh bạch.",
        },
        {
          number: "04",
          title: "Biết rõ khi nào cần chuyển giao chuyên gia",
          description: "Nhận diện dấu hiệu cấp cứu tức thì và hướng dẫn bệnh nhân tiếp cận cơ sở y tế gần nhất.",
        },
      ],
    },
    privacy: {
      eyebrow: "RANH GIỚI BẢO MẬT DỮ LIỆU",
      title: "Quyền kiểm soát dữ liệu hoàn toàn thuộc về bạn",
      description:
        "Kiến trúc Zero-CoT đảm bảo không tiết lộ suy luận thô, không dùng dữ liệu người dùng để huấn luyện mô hình khi chưa được phép và mã hóa ở mức ngân hàng.",
      diagram: {
        source: "Hồ sơ cá nhân",
        gate: "Cổng kiểm soát quyền",
        destination: "Người nhận được chỉ định",
        allowedNote: "Chỉ các trường được cấp phép mới được truyền qua",
        blockedNote: "Các trường nhạy cảm khác bị chặn hoàn toàn tại cổng",
        revokeNote: "Quyền truy cập có thể thu hồi bất kỳ lúc nào",
      },
    },
    scenarios: {
      eyebrow: "TÌNH HUỐNG THỰC TẾ",
      title: "CLARA đồng hành cùng bạn trong từng hoàn cảnh",
      description: "Những câu hỏi đời thường được giải đáp với sự chuẩn xác y khoa và thấu hiểu ngữ cảnh.",
      items: [
        {
          quote: "Tôi vừa được bác sĩ kê một loại thuốc mới.",
          context: "Cần kiểm tra xem thuốc mới có tương tác với các thuốc đang uống hằng ngày hay không.",
          resolution: "CLARA quét toàn bộ đơn thuốc hiện tại, cảnh báo nguy cơ tương tác và đưa ra lịch uống an toàn.",
        },
        {
          quote: "Tôi muốn chuẩn bị cho buổi khám bệnh tuần tới.",
          context: "Có nhiều triệu chứng rời rạc nhưng không biết tóm tắt thế nào cho bác sĩ dễ hiểu.",
          resolution: "CLARA gom các triệu chứng theo dòng thời gian LifeMap và tạo danh sách câu hỏi trọng tâm cho buổi khám.",
        },
        {
          quote: "Tôi vừa xuất hiện một triệu chứng lạ.",
          context: "Cảm thấy đau nhói ngực khi thở sâu nhưng chưa rõ có phải trường hợp khẩn cấp.",
          resolution: "CLARA sàng lọc nhanh dấu hiệu nguy hiểm, hướng dẫn kiểm tra nhịp thở và khuyến nghị cấp cứu nếu có dấu hiệu đỏ.",
        },
        {
          quote: "Tôi muốn nhìn lại diễn biến sức khỏe vài tháng qua.",
          context: "Muốn biết chỉ số đường huyết và huyết áp thay đổi ra sao sau khi đổi chế độ ăn.",
          resolution: "LifeMap hiển thị trực quan biểu đồ tiến triển cùng các mốc can thiệp điều trị để đánh giá hiệu quả.",
        },
      ],
    },
    comparison: {
      eyebrow: "SỰ KHÁC BIỆT",
      title: "Tại sao CLARA không phải là chatbot thông thường?",
      description: "Mô hình ngôn ngữ thông thường chỉ tạo văn bản. CLARA là một hệ thống suy luận an toàn đa tầng.",
      genericAi: {
        title: "Chatbot AI Thông thường",
        flow: ["Câu hỏi người dùng", "Dự đoán từ ngữ tiếp theo", "Câu trả lời không kiểm chứng"],
        drawback: "Dễ bị ảo giác (hallucination), không trích dẫn nguồn thực và không có cơ chế chặn tương tác thuốc.",
      },
      claraCare: {
        title: "CLARA Care System",
        flow: [
          "Câu hỏi người dùng",
          "Nạp Bối cảnh Sức khỏe",
          "Truy xuất Y văn Đa nguồn",
          "Kiểm định An toàn FIDES",
          "Xác định Giới hạn & Điểm chưa chắc",
          "Gợi ý Hành động Thực tế",
          "Lưu vết Dòng thời gian LifeMap",
        ],
        benefit: "Mỗi khuyến nghị đều có căn cứ y văn, có kiểm tra tương tác thuốc và bảo vệ an toàn tối đa.",
      },
    },
    faq: {
      eyebrow: "CÂU HỎI THƯỜNG GẶP",
      title: "Giải đáp thắc mắc về CLARA",
      description: "Những câu hỏi phổ biến nhất về cách thức hoạt động, độ an toàn và quyền riêng tư của bạn.",
      items: [
        {
          question: "CLARA có thể thay thế bác sĩ khám bệnh không?",
          answer:
            "Không. CLARA là trợ lý hỗ trợ thông tin và quyết định y tế an toàn, không thay thế việc chẩn đoán hoặc kê đơn của bác sĩ chuyên môn. Trong các tình huống nguy cấp, bạn cần đến ngay cơ sở y tế.",
        },
        {
          question: "CLARA sử dụng những nguồn dữ liệu y khoa nào?",
          answer:
            "CLARA đối chiếu trực tiếp với Dược thư Quốc gia Việt Nam, Cục Quản lý Dược (DAV), Dữ liệu Dược lý DrugBank 5.1, Hướng dẫn của WHO, FDA, và các nghiên cứu y khoa được bình duyệt trên PubMed/MEDLINE.",
        },
        {
          question: "Dữ liệu sức khỏe của tôi có bị dùng để huấn luyện AI không?",
          answer:
            "Không. CLARA tuân thủ nguyên tắc Zero-CoT và quy định bảo vệ dữ liệu cá nhân (Nghị định 13/2023/NĐ-CP). Dữ liệu y tế của bạn được mã hóa và không bao giờ được sử dụng cho việc huấn luyện mô hình khi chưa có sự đồng thuận tường minh.",
        },
        {
          question: "FIDES là gì và hoạt động như thế nào?",
          answer:
            "FIDES là hệ thống kiểm chứng an toàn y tế độc lập của CLARA. Trước khi gửi câu trả lời về thuốc, FIDES đối chiếu các tuyên bố về liều dùng và tương tác thuốc với cơ sở dữ liệu quy chuẩn; nếu phát hiện sai lệch nghiêm trọng, phản hồi sẽ bị chặn và hiệu chỉnh ngay.",
        },
        {
          question: "Bác sĩ có thể sử dụng CLARA như thế nào trong phòng khám?",
          answer:
            "Bác sĩ có thể sử dụng CLARA Clinical để ghi chép cuộc khám bằng giọng nói (Scribe), dự thảo bệnh án SOAP, tra cứu nhanh tương tác dược lý và khởi chạy hội chẩn Council đa chuyên khoa cho các ca bệnh phức tạp.",
        },
      ],
    },
    finalCta: {
      eyebrow: "BẮT ĐẦU NGAY",
      title: "Bắt đầu bằng điều bạn đang muốn hiểu.",
      description:
        "Đặt câu hỏi đầu tiên của bạn để trải nghiệm cách CLARA kết nối bối cảnh, y văn và sự an toàn cho sức khỏe của bạn.",
      primaryCta: "Hỏi CLARA ngay bây giờ",
      secondaryCta: "Tìm hiểu thêm về an toàn",
      securityBadge: "Bảo mật y tế Zero-CoT • Tuân thủ Nghị định 13/2023/NĐ-CP",
    },
    footer: {
      tagline: "Trợ lý AI Lâm sàng & Y tế An toàn cho Người Việt",
      disclaimer:
        "CLARA Care là công cụ hỗ trợ thông tin y tế và hỗ trợ quyết định lâm sàng, không thay thế chẩn đoán, điều trị hay lời khuyên của bác sĩ chuyên khoa.",
      columns: {
        product: {
          title: "Sản phẩm",
          links: [
            { label: "Trò chuyện CLARA", href: "/chat" },
            { label: "Dòng thời gian LifeMap", href: "/lifemap" },
            { label: "Tủ thuốc & Tương tác", href: "/medicines" },
            { label: "Hồ sơ Sức khỏe Cá nhân", href: "/phr" },
          ],
        },
        clinical: {
          title: "Chuyên gia & Lâm sàng",
          links: [
            { label: "Tổng quan Lâm sàng", href: "/clinical" },
            { label: "Hội đồng Council", href: "/council" },
            { label: "Trợ lý Ghi chép Scribe", href: "/scribe" },
            { label: "Trung tâm Bằng chứng", href: "/research" },
          ],
        },
        trust: {
          title: "Tin cậy & An toàn",
          links: [
            { label: "Kiểm chứng FIDES", href: "/safety" },
            { label: "Bảo mật Dữ liệu", href: "/privacy" },
            { label: "Nguồn Y văn Chuẩn", href: "/sources" },
            { label: "Tiêu chuẩn Lâm sàng", href: "/clinical-standards" },
          ],
        },
        company: {
          title: "Hỗ trợ & Pháp lý",
          links: [
            { label: "Hướng dẫn Sử dụng", href: "/huong-dan" },
            { label: "Điều khoản Dịch vụ", href: "/terms" },
            { label: "Chính sách Bảo mật", href: "/privacy" },
            { label: "Liên hệ Đội ngũ", href: "/contact" },
          ],
        },
      },
      copyright: "© 2026 CLARA Care System. All rights reserved.",
      terms: "Điều khoản",
      privacy: "Bảo mật",
      consent: "Đồng thuận Y tế",
    },
  },
  en: {
    languageLabel: "Language",
    languageNames: { vi: "Tiếng Việt", en: "English" },
    nav: {
      brand: "CLARA Care",
      brandTag: "Safety-First Medical AI",
      howItWorks: "How It Works",
      features: "Features",
      safety: "Safety",
      clinical: "Clinical",
      login: "Sign In",
      askClara: "Ask CLARA",
      openMenu: "Open navigation menu",
      closeMenu: "Close navigation menu",
      skipToContent: "Skip to main content",
    },
    hero: {
      badge: "FIDES VETTED • ZERO-COT SECURITY",
      titleStart: "Understand what is happening.",
      titleAccent: "Know what matters next",
      titleEnd: "to do.",
      description:
        "A safety-first medical AI assistant connecting health queries with medication context, health records, timelines, and verified clinical literature. Transparent, safe, and clinician-partnered.",
      primaryCta: "Start Asking CLARA",
      secondaryCta: "See How It Works",
      floatingContext1: {
        label: "Medication Context",
        value: "Metformin 500mg • Amlodipine 5mg",
        tag: "Tracked Active",
      },
      floatingContext2: {
        label: "FIDES Verification",
        value: "0 critical interactions detected",
        tag: "Literature Verified",
      },
      preview: {
        question: "Can I take Metformin with Amlodipine when shifting my meal schedule?",
        answerSummary:
          "There is no direct adverse drug-drug interaction between these medications, but meal timing changes can affect Metformin gastrointestinal tolerance and postprandial glycemic control.",
        safetyBadge: "FIDES Safe",
        sourceCitation: "National Pharmacopoeia • FDA Drug Safety Data",
        nextAction: "Continue taking Metformin immediately after major meals to reduce GI upset.",
      },
    },
    trust: {
      eyebrow: "TRANSPARENT SOURCES",
      title: "Clear Sources. Clear Boundaries.",
      description:
        "CLARA extracts and cross-references only from authoritative clinical repositories. Every response cites its origins and explicitly declares uncertainty bounds.",
      sources: [
        { name: "WHO", type: "World Health Organization", authority: "Standard Clinical Guidelines" },
        { name: "PubMed / MEDLINE", type: "International Literature", authority: "Clinical Trial Evidence" },
        { name: "FDA", type: "Food & Drug Administration", authority: "Adverse Interaction Alerts" },
        { name: "DrugBank 5.1", type: "Pharmacological Database", authority: "Mechanisms & Metabolism" },
        { name: "EMA", type: "European Medicines Agency", authority: "Safety Standards & Dosages" },
        { name: "DAV", type: "Drug Administration of Vietnam", authority: "National Pharmacopoeia" },
        { name: "PubChem", type: "Biochemical Database", authority: "Molecular Structures" },
      ],
    },
    manifesto: {
      eyebrow: "LONGITUDINAL CONTEXT",
      headline: "A single health question\nis rarely only one question.",
      subheadline:
        "Behind every symptom lies a history of medications, allergies, clinical records, and physiological changes over time.",
      nodes: {
        medications: "Active Medications",
        recentChanges: "Recent Changes",
        healthRecord: "Health Record",
        pastQuestions: "Prior Inquiries",
        sources: "Evidence Sources",
      },
      centerTitle: "CLARA Core",
      centerSubtitle: "Safety Convergence Engine",
      resolveStatement: "What is truly important right now?",
    },
    how: {
      eyebrow: "4-STEP WORKFLOW",
      title: "How CLARA Processes a Query",
      description:
        "No wild speculation. Every answer is structured through an uncompromising pipeline from context gathering to pharmacological verification.",
      steps: [
        {
          number: "01",
          title: "You ask a question",
          description: "Describe symptoms, inquire about prescriptions, or prepare for an upcoming appointment.",
          stateBadge: "Intake Captured",
        },
        {
          number: "02",
          title: "CLARA retrieves context",
          description: "Automatically inspects active medications, allergy history, and recent health milestones.",
          stateBadge: "Context Matched",
        },
        {
          number: "03",
          title: "FIDES safety & source validation",
          description: "Cross-checks clinical literature and runs multi-layer drug-drug interaction verifiers.",
          stateBadge: "Safety Vetted",
        },
        {
          number: "04",
          title: "Clear answer & next actions",
          description: "Delivers direct conclusions, clarifies uncertainties, and prescribes practical next steps.",
          stateBadge: "Structured Response",
        },
      ],
    },
    chat: {
      eyebrow: "CONVERSATION EXPERIENCE",
      title: "Direct Answer First. Depth on Demand.",
      description:
        "A cleanly tiered response surface: concise clinical takeaways up front, with full pharmacological mechanisms and citations expandable at will.",
      directAnswerTitle: "Direct Answer",
      directAnswerBody:
        "Mild fatigue and lightheadedness upon standing 3 days after initiating antihypertensive therapy can represent transient orthostatic adjustment.",
      nextActionTitle: "Recommended Next Steps",
      nextActionBody:
        "1. Stand up slowly from sitting or supine positions.\n2. Log morning and evening blood pressure for the next 3 days.\n3. If systolic BP drops below 90 mmHg or dizziness persists, consult your physician promptly.",
      uncertaintyTitle: "Missing Context / Data Gaps",
      uncertaintyBody: "Recent home blood pressure readings are not yet recorded in your profile.",
      sourcesTitle: "Referenced Clinical Sources",
      sourcesDisclaimer: "Click any source to inspect citations and detailed applicability",
      advancedDetailTitle: "Pharmacological Mechanism & Advanced Notes",
      advancedDetailBody:
        "Amlodipine is a dihydropyridine calcium channel blocker inducing peripheral vasodilation. Vascular tone recalibration typically takes 3–7 days.",
      inspectorTitle: "Source Citation Details",
      inspectorClose: "Close source inspector",
    },
    lifemap: {
      eyebrow: "HEALTH TIMELINE",
      title: "Health is not a static snapshot.",
      description:
        "LifeMap links symptoms, prescription alterations, and lab investigations into a continuous timeline revealing causal patterns.",
      timeline: [
        {
          period: "April",
          title: "Symptom Onset",
          detail: "Early morning occipital headaches noted.",
          category: "Symptom",
          emphasis: "past",
        },
        {
          period: "May",
          title: "Therapy Initiated",
          detail: "Amlodipine 5mg daily prescribed following BP reading 145/90 mmHg.",
          category: "Prescription",
          emphasis: "past",
        },
        {
          period: "June",
          title: "Follow-up Visit",
          detail: "BP stabilized at 125/80 mmHg with normal renal function panels.",
          category: "Encounter",
          emphasis: "recent",
        },
        {
          period: "Today",
          title: "Schedule Adjustment Query",
          detail: "Consultation regarding shift work transition and dosing intervals.",
          category: "New Turn",
          emphasis: "today",
        },
      ],
      insightCallout: {
        tag: "LIFEMAP INSIGHT",
        title: "Notable change observed since your last review",
        body: "Your blood pressure has remained at target range for 60 consecutive days. When adjusting dosing times, maintain a consistent 24-hour interval.",
        action: "Explore Full Health Timeline",
      },
    },
    medicines: {
      eyebrow: "MEDICATION SAFETY",
      title: "Unified Medication Workspace",
      description:
        "Strict distinction between actively taken medications, pending confirmations, and home medicine cabinet inventory. Automated multi-drug interaction checking.",
      tabs: {
        current: "Active (2)",
        needsConfirmation: "Needs Review (1)",
        safetyCheck: "FIDES Safety Check",
        cabinet: "Cabinet Storage (5)",
      },
      truthNote: "Cabinet inventory ≠ Active daily intake. Lack of alert does not imply unguided combinations are safe.",
      safetyTag: "FIDES Vetted",
      fidesVerified: "Verified against National Pharmacopoeia & DrugBank",
    },
    phr: {
      eyebrow: "DATA BOUNDARIES & ACCESS",
      title: "Bounded Sharing with Complete Control",
      description:
        "Define exactly what data is shared, with whom, and for how long. Granular permissions can be revoked instantly with a single tap.",
      statement: "Sharing a portion of your health data never means exposing your entire record.",
      patientName: "Nguyen Van An",
      patientMrn: "MRN-8842-VN",
      sharingTitle: "Cardiology Consultation Share Packet",
      allowedSection: "Permitted Data Fields (Shared)",
      blockedSection: "Protected Data Fields (Blocked at Gate)",
      expiryLabel: "Validity Window",
      expiryValue: "30 Days (Expires Sep 24, 2026)",
      revokeAction: "Revoke Access Immediately",
    },
    adaptive: {
      eyebrow: "ONE SYSTEM SHELL",
      title: "One CLARA. Adapting to how you work.",
      description:
        "Not three separate apps. The same safety-first engine fluidly morphs its interface across Personal, Clinical, and Research workflows.",
      modes: {
        personal: {
          id: "personal",
          label: "Personal Mode",
          tagline: "Daily personal health companion",
          navItems: ["Today", "LifeMap", "CLARA", "Meds", "Records"],
          headline: "Today's Care Protocol",
          actionItem: "Take morning antihypertensive at 08:00 • Check BP after 30 mins",
        },
        clinical: {
          id: "clinical",
          label: "Clinical Mode",
          tagline: "Physician decision support copilot",
          navItems: ["Overview", "Council", "CLARA", "Scribe", "More"],
          headline: "Clinical Consult Triage Queue",
          actionItem: "Case #3102: Anticoagulation + CKD Stage 3b (DDI cross-check required)",
        },
        research: {
          id: "research",
          label: "Research Mode",
          tagline: "Living evidence & literature synthesis",
          navItems: ["Research", "Evidence", "CLARA", "Sources", "More"],
          headline: "Evidence Synthesis Center",
          actionItem: "Synthesize 14 RCT trials on SGLT2 inhibitors in preserved ejection fraction",
        },
      },
    },
    clinicalTransition: {
      eyebrow: "CLARA CLINICAL",
      headline: "Specialized tools,\nwhen you require clinical depth.",
      subheadline: "Engineered for diagnostic workflows, multidisciplinary consensus, and evidence extraction.",
    },
    council: {
      eyebrow: "MULTIDISCIPLINARY COUNCIL",
      title: "From Multilateral Complexity to Structured Decisions",
      description:
        "Council synthesizes perspectives across Cardiology, Nephrology, and Clinical Pharmacology, highlighting consensus, conflicts, and decision boundaries.",
      disclaimer: "CLARA never makes autonomous treatment decisions. The treating physician retains ultimate clinical authority.",
      caseContext: {
        patient: "Male Patient, 68 years old",
        ageGender: "History of Hypertension 10yr, T2D, baseline eGFR 38 mL/min",
        chiefComplaint: "Optimize antihypertensive and antidiabetic regimen following mild ankle edema.",
        vitals: "BP: 152/88 mmHg • HR: 74 bpm • Creatinine: 142 umol/L",
        activeMeds: "Metformin 1000mg/day, Amlodipine 5mg/day, Gliclazide 60mg/day",
      },
      recommendationTitle: "Synthesized Clinical Recommendations",
      recommendationBody:
        "1. Consider dose reduction or discontinuation of Metformin given eGFR < 45 mL/min to prevent lactic acidosis risk.\n2. Evaluate transition to renal-adjusted SGLT2i or DPP-4i.\n3. Recheck serum electrolytes and renal function at 2 weeks.",
      disagreementsTitle: "Specialty Disagreements & Risk Flags",
      disagreementsBody:
        "Pharmacology recommends immediate Metformin cessation; Cardiology suggests retaining 500mg daily under monthly eGFR surveillance.",
      uncertaintyTitle: "Missing Clinical Context",
      uncertaintyBody: "Recent urine albumin-to-creatinine ratio (uACR) is pending.",
      nextStepsTitle: "Recommended Action Plan for Clinician",
      nextStepsBody: "Order spot uACR, serum K+/Na+, and schedule review encounter in 14 days.",
      evidenceTitle: "Referenced Clinical Guidelines",
      evidenceBody: "KDIGO 2023 Clinical Practice Guideline • ADA Standards of Care 2024",
    },
    scribe: {
      eyebrow: "CLINICAL AMBIENT SCRIBE",
      title: "Real-Time Encounter Transformation",
      description:
        "From patient consent to recording, bilingual Vietnamese-English clinical term extraction, and automated SOAP documentation ready for physician sign-off.",
      states: {
        consent: {
          step: "01",
          title: "Patient Consent",
          desc: "Patient confirms secure end-to-end encrypted audio capture.",
        },
        recording: {
          step: "02",
          title: "Ambient Encounter Recording",
          desc: "Captures natural conversation with medical noise reduction filtering.",
          timer: "02:45 • Recording Active",
        },
        transcript: {
          step: "03",
          title: "Clinical Transcription",
          desc: "Normalizes Vietnamese colloquial expressions into structured medical terms.",
          text: "Doctor: When do you notice the chest tightness? — Patient: While walking up stairs to the 2nd floor, lasts about 3 minutes...",
        },
        soap: {
          step: "04",
          title: "Structured SOAP Draft",
          desc: "Extracts Subjective, Objective, Assessment, and Plan components.",
          s: "Exertional retrosternal chest tightness lasting ~3 mins relieved by rest.",
          o: "BP: 135/85 mmHg, Regular heart sounds, no audible murmurs.",
          a: "Stable Angina Pectoris (CCS Class II) - rule out ischemic heart disease.",
          p: "Order Exercise Stress ECG and Transthoracic Doppler Echocardiogram.",
        },
        review: {
          step: "05",
          title: "Physician Review & Sign-Off",
          desc: "Clinician inspects, refines, and signs the note before EMR commitment.",
          status: "Ready for Attending Physician Signature",
        },
      },
    },
    evidence: {
      eyebrow: "LIVING EVIDENCE HUB",
      title: "Inspect Exactly What CLARA Relies On",
      editorial: "Not all evidence carries equal clinical weight.",
      description:
        "Query clinical evidence across strict hierarchical tiers: from National Practice Guidelines and Randomized Controlled Trials (RCTs) to Urgent Pharmacovigilance Alerts.",
      selectHint: "Select any source in the registry to inspect confidence weightings and applicability bounds.",
      inspector: {
        relevance: "Relevance Rationale",
        applicability: "Clinical Applicability",
        limitations: "Identified Limitations",
        authorityLevel: "Authority Tier",
        updated: "Last Verified",
      },
    },
    safety: {
      eyebrow: "NON-NEGOTIABLE SAFETY",
      title: "Safety is our core invariant. Not an afterthought.",
      description: "Our safety principles are hard-locked into the code and cannot be bypassed by prompt engineering.",
      principles: [
        {
          number: "01",
          title: "Unambiguous Source Attribution",
          description: "Every clinical assertion is explicitly linked to authoritative medical literature.",
        },
        {
          number: "02",
          title: "Never Conceal Uncertainty",
          description: "When clinical evidence is incomplete, the system communicates data gaps immediately.",
        },
        {
          number: "03",
          title: "Never Label 'Unchecked' as 'Safe'",
          description: "Claims awaiting FIDES verification are transparently tagged as Unverified.",
        },
        {
          number: "04",
          title: "Know When to Escalate to Humans",
          description: "Instantly flags emergency red-flags and directs patients to immediate emergency care.",
        },
      ],
    },
    privacy: {
      eyebrow: "DATA PRIVACY BOUNDARY",
      title: "Complete Sovereignty Over Your Health Data",
      description:
        "Zero-CoT architecture guarantees that raw reasoning traces are never exposed, user health records are never used for model training without consent, and all traffic is encrypted with banking-grade protocols.",
      diagram: {
        source: "Personal Health Record",
        gate: "Permission Boundary Gate",
        destination: "Designated Recipient",
        allowedNote: "Only explicitly permitted fields pass through the gate",
        blockedNote: "Protected and sensitive fields are halted at the boundary",
        revokeNote: "Permissions can be revoked instantly at any time",
      },
    },
    scenarios: {
      eyebrow: "REAL-WORLD SCENARIOS",
      title: "CLARA with You in Everyday Moments",
      description: "Everyday health questions resolved with clinical rigor and human context.",
      items: [
        {
          quote: "I was just prescribed a new medication.",
          context: "Need to verify if the new prescription interacts with daily medications.",
          resolution: "CLARA cross-checks your complete medication regimen, flags risks, and provides a safe dosing schedule.",
        },
        {
          quote: "I want to prepare for my doctor's visit next week.",
          context: "Multiple scattered symptoms that are difficult to explain concisely.",
          resolution: "CLARA structures your symptoms into a LifeMap timeline and generates a focused question list for your doctor.",
        },
        {
          quote: "I am experiencing an unexpected new symptom.",
          context: "Sharp chest pain on deep inspiration, unsure if urgent.",
          resolution: "CLARA runs an immediate red-flag check, guides basic checks, and provides emergency routing if indicated.",
        },
        {
          quote: "I want to review my health progress over the past months.",
          context: "Curious how blood pressure and glucose readings responded after dietary modifications.",
          resolution: "LifeMap visually charts physiological milestones alongside clinical interventions to evaluate real progress.",
        },
      ],
    },
    comparison: {
      eyebrow: "THE DIFFERENCE",
      title: "Why CLARA is not just another chatbot",
      description: "Generic AI chatbots guess next tokens. CLARA is a multi-tier clinical safety reasoning engine.",
      genericAi: {
        title: "Generic AI Chatbot",
        flow: ["User Question", "Next Token Prediction", "Unverified Output"],
        drawback: "Susceptible to hallucinations, lacks genuine medical citations, and provides no interaction safeguards.",
      },
      claraCare: {
        title: "CLARA Care System",
        flow: [
          "User Question",
          "Health Context Injection",
          "Multi-Source Evidence Retrieval",
          "FIDES Safety Verification",
          "Uncertainty & Boundary Flagging",
          "Actionable Next Steps",
          "LifeMap Timeline Provenance",
        ],
        benefit: "Every recommendation is grounded in literature, verified for drug interactions, and built for safety.",
      },
    },
    faq: {
      eyebrow: "FREQUENTLY ASKED QUESTIONS",
      title: "Everything you need to know about CLARA",
      description: "Common questions regarding system mechanics, clinical safety, and data governance.",
      items: [
        {
          question: "Can CLARA replace a doctor's examination?",
          answer:
            "No. CLARA is a safety-first medical assistant and clinical decision support system. It does not replace the diagnosis, prescription, or clinical judgment of licensed physicians.",
        },
        {
          question: "What medical data sources does CLARA rely on?",
          answer:
            "CLARA references the National Pharmacopoeia of Vietnam, the Drug Administration of Vietnam (DAV), DrugBank 5.1, WHO guidelines, FDA alerts, and peer-reviewed studies indexed in PubMed/MEDLINE.",
        },
        {
          question: "Is my personal health data used to train AI models?",
          answer:
            "No. CLARA enforces strict Zero-CoT standards and data protection compliance (Vietnam Decree 13/2023/ND-CP). Your medical data is encrypted and never used for model training without explicit consent.",
        },
        {
          question: "What is FIDES and how does it safeguard users?",
          answer:
            "FIDES is CLARA's deterministic medical safety verification engine. Before any medication advice is rendered, FIDES cross-validates dosage and interaction assertions against canonical databases, blocking any critical discrepancies.",
        },
        {
          question: "How can physicians use CLARA in outpatient practice?",
          answer:
            "Clinicians can leverage CLARA Clinical for ambient audio transcription (Scribe), automated SOAP drafting, instant drug-drug interaction lookups, and launching multidisciplinary Council reviews for complex cases.",
        },
      ],
    },
    finalCta: {
      eyebrow: "GET STARTED TODAY",
      title: "Begin with what you want to understand.",
      description:
        "Ask your first question to discover how CLARA bridges context, clinical literature, and safety for your health.",
      primaryCta: "Ask CLARA Now",
      secondaryCta: "Learn About Safety",
      securityBadge: "Zero-CoT Medical Privacy • Compliant with Decree 13/2023/ND-CP",
    },
    footer: {
      tagline: "Safety-First Clinical & Health AI Assistant for Vietnam",
      disclaimer:
        "CLARA Care provides clinical information and decision support. It does not replace professional diagnosis, treatment, or advice from licensed healthcare providers.",
      columns: {
        product: {
          title: "Product",
          links: [
            { label: "CLARA Chat", href: "/chat" },
            { label: "LifeMap Timeline", href: "/lifemap" },
            { label: "Medications & DDI", href: "/medicines" },
            { label: "Personal Health Records", href: "/phr" },
          ],
        },
        clinical: {
          title: "Clinical & Pro",
          links: [
            { label: "Clinical Overview", href: "/clinical" },
            { label: "Medical Council", href: "/council" },
            { label: "Ambient Scribe", href: "/scribe" },
            { label: "Living Evidence Hub", href: "/research" },
          ],
        },
        trust: {
          title: "Trust & Safety",
          links: [
            { label: "FIDES Verification", href: "/safety" },
            { label: "Data Privacy", href: "/privacy" },
            { label: "Clinical Sources", href: "/sources" },
            { label: "Medical Standards", href: "/clinical-standards" },
          ],
        },
        company: {
          title: "Support & Legal",
          links: [
            { label: "User Guide", href: "/huong-dan" },
            { label: "Terms of Service", href: "/terms" },
            { label: "Privacy Policy", href: "/privacy" },
            { label: "Contact Team", href: "/contact" },
          ],
        },
      },
      copyright: "© 2026 CLARA Care System. All rights reserved.",
      terms: "Terms",
      privacy: "Privacy",
      consent: "Medical Consent",
    },
  },
};
