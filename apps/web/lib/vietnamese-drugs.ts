/**
 * Vietnamese Drug Catalog & Interaction Knowledge Base.
 *
 * Provides autocomplete search for common Vietnamese drug trade names
 * (Panadol, Glucophage, Coversyl, Augmentin, Lipitor, etc.) along with their
 * active pharmaceutical ingredients, therapeutic classes, dosage forms,
 * and deterministic interaction rules with clear Traffic-Light indicators:
 *   - Green (Xanh: An toàn)
 *   - Yellow (Vàng: Cần lưu ý)
 *   - Red (Đỏ: Tương tác nguy hiểm)
 */

export type TrafficLightLevel = "safe" | "caution" | "danger";

export type VietnameseDrug = {
  id: string;
  tradeName: string;
  genericName: string;
  activeIngredients: string;
  category: string;
  categoryEn: string;
  defaultDosage: string;
  dosageForm: string;
  manufacturer?: string;
  description: string;
  searchTokens: string[];
  drugbankId?: string;
};

export type DrugInteractionAlert = {
  drugA: string;
  drugB: string;
  level: TrafficLightLevel;
  title: string;
  mechanism: string;
  clinicalEffect: string;
  recommendation: string;
  symptomsToWatch: string[];
  sourceAuthority: string;
};

export type InteractionCheckResult = {
  level: TrafficLightLevel;
  summary: string;
  alerts: DrugInteractionAlert[];
  checkedCount: number;
  medications: string[];
};

export const VIETNAMESE_DRUGS_CATALOG: VietnameseDrug[] = [
  {
    id: "panadol-extra",
    tradeName: "Panadol Extra",
    genericName: "Paracetamol + Caffeine",
    activeIngredients: "Paracetamol 500mg, Caffeine 65mg",
    category: "Giảm đau, hạ sốt",
    categoryEn: "Analgesic / Antipyretic",
    defaultDosage: "500mg / 65mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "GSK (GlaxoSmithKline)",
    description: "Giảm đau nhanh các cơn đau đầu, đau nửa đầu, đau cơ, sốt do cảm cúm.",
    searchTokens: ["panadol", "panadol extra", "paracetamol", "caffeine", "giam dau", "ha sot", "dau dau"],
    drugbankId: "DB00316",
  },
  {
    id: "panadol-regular",
    tradeName: "Panadol",
    genericName: "Paracetamol",
    activeIngredients: "Paracetamol 500mg",
    category: "Giảm đau, hạ sốt",
    categoryEn: "Analgesic / Antipyretic",
    defaultDosage: "500mg",
    dosageForm: "Viên nén",
    manufacturer: "GSK",
    description: "Hạ sốt, giảm các triệu chứng đau nhẹ đến vừa như đau răng, đau họng, đau nhức cơ.",
    searchTokens: ["panadol", "paracetamol", "ha sot", "giam dau", "efferalgan", "hapacol"],
    drugbankId: "DB00316",
  },
  {
    id: "glucophage-xr",
    tradeName: "Glucophage XR",
    genericName: "Metformin HCl",
    activeIngredients: "Metformin Hydrochloride 500mg / 750mg / 1000mg",
    category: "Trị đái tháo đường type 2 (Biguanide)",
    categoryEn: "Antidiabetic (Biguanide)",
    defaultDosage: "500mg (hoặc 750mg / 1000mg)",
    dosageForm: "Viên nén phóng thích kéo dài",
    manufacturer: "Merck KGaA",
    description: "Kiểm soát đường huyết ở bệnh nhân đái tháo đường type 2, giảm đề kháng insulin.",
    searchTokens: ["glucophage", "glucophage xr", "metformin", "tieu duong", "dai thao duong", "ha duong huyet"],
    drugbankId: "DB00331",
  },
  {
    id: "coversyl",
    tradeName: "Coversyl",
    genericName: "Perindopril Arginine",
    activeIngredients: "Perindopril Arginine 5mg / 10mg",
    category: "Thuốc tim mạch / Huyết áp (Ức chế men chuyển ACEi)",
    categoryEn: "Antihypertensive (ACE Inhibitor)",
    defaultDosage: "5mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Servier",
    description: "Điều trị tăng huyết áp vô căn, suy tim sung huyết và giảm nguy cơ biến cố tim mạch.",
    searchTokens: ["coversyl", "coversyl plus", "perindopril", "huyet ap", "tang huyet ap", "tim mach", "acei"],
    drugbankId: "DB00790",
  },
  {
    id: "augmentin",
    tradeName: "Augmentin",
    genericName: "Amoxicillin + Clavulanic Acid",
    activeIngredients: "Amoxicillin 500mg/875mg + Acid Clavulanic 125mg",
    category: "Kháng sinh phổ rộng (Penicillin + Ức chế Beta-lactamase)",
    categoryEn: "Antibacterial (Penicillin combination)",
    defaultDosage: "625mg (hoặc 1g)",
    dosageForm: "Viên nén bao phim",
    manufacturer: "GSK",
    description: "Kháng sinh điều trị nhiễm khuẩn đường hô hấp trên/dưới, viêm tai giữa, nhiễm khuẩn tiết niệu, da.",
    searchTokens: ["augmentin", "amoxicillin", "clavulanate", "khang sinh", "viem hong", "nhiem khuan"],
    drugbankId: "DB01060",
  },
  {
    id: "lipitor",
    tradeName: "Lipitor",
    genericName: "Atorvastatin Calcium",
    activeIngredients: "Atorvastatin 10mg / 20mg / 40mg",
    category: "Hạ lipid máu (Statin)",
    categoryEn: "Lipid-lowering agent (Statin)",
    defaultDosage: "20mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Pfizer / Viatris",
    description: "Hạ cholesterol toàn phần, LDL-C và triglycerid; phòng ngừa đột quỵ và nhồi máu cơ tim.",
    searchTokens: ["lipitor", "atorvastatin", "mo mau", "cholesterol", "statin", "tim mach"],
    drugbankId: "DB01076",
  },
  {
    id: "crestor",
    tradeName: "Crestor",
    genericName: "Rosuvastatin Calcium",
    activeIngredients: "Rosuvastatin 10mg / 20mg",
    category: "Hạ lipid máu (Statin thế hệ mới)",
    categoryEn: "Lipid-lowering agent (Statin)",
    defaultDosage: "10mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "AstraZeneca",
    description: "Điều trị tăng cholesterol máu nguyên phát, rối loạn lipid máu hỗn hợp và phòng xơ vữa động mạch.",
    searchTokens: ["crestor", "rosuvastatin", "mo mau", "statin", "cholesterol"],
    drugbankId: "DB01039",
  },
  {
    id: "nexium",
    tradeName: "Nexium Mups",
    genericName: "Esomeprazole",
    activeIngredients: "Esomeprazole Magnesium 20mg / 40mg",
    category: "Kháng tiết acid dạ dày (Ức chế bơm Proton - PPI)",
    categoryEn: "Proton Pump Inhibitor (PPI)",
    defaultDosage: "20mg (hoặc 40mg)",
    dosageForm: "Viên nén kháng dịch dạ dày",
    manufacturer: "AstraZeneca",
    description: "Điều trị bệnh trào ngược dạ dày thực quản (GERD), viêm loét dạ dày - tá tràng, diệt trừ H. pylori.",
    searchTokens: ["nexium", "nexium mups", "esomeprazole", "da day", "trao nguoc", "loet da day", "ppi"],
    drugbankId: "DB00736",
  },
  {
    id: "plavix",
    tradeName: "Plavix",
    genericName: "Clopidogrel",
    activeIngredients: "Clopidogrel Bisulfate 75mg",
    category: "Chống kết tập tiểu cầu (Antiplatelet)",
    categoryEn: "Antiplatelet agent",
    defaultDosage: "75mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Sanofi",
    description: "Phòng ngừa biến cố huyết khối do xơ vữa ở bệnh nhân nhồi máu cơ tim, đột quỵ thiếu máu cục bộ.",
    searchTokens: ["plavix", "clopidogrel", "chong ket tap tieu cau", "dong mau", "huyet khoi", "tim mach"],
    drugbankId: "DB00758",
  },
  {
    id: "concor",
    tradeName: "Concor",
    genericName: "Bisoprolol Fumarate",
    activeIngredients: "Bisoprolol Fumarate 2.5mg / 5mg / 10mg",
    category: "Chẹn chọn lọc Beta-1 giao cảm",
    categoryEn: "Beta-blocker",
    defaultDosage: "5mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Merck Healthcare",
    description: "Điều trị tăng huyết áp, bệnh mạch vành (đau thắt ngực) và suy tim mạn tính ổn định.",
    searchTokens: ["concor", "concor cor", "bisoprolol", "huyet ap", "nhip tim", "tim mach", "beta blocker"],
    drugbankId: "DB00612",
  },
  {
    id: "voltaren",
    tradeName: "Voltaren",
    genericName: "Diclofenac Sodium",
    activeIngredients: "Diclofenac Sodium 50mg / 75mg",
    category: "Kháng viêm không steroid (NSAID)",
    categoryEn: "NSAID (Non-steroidal anti-inflammatory)",
    defaultDosage: "50mg (hoặc 75mg)",
    dosageForm: "Viên bao tan trong ruột",
    manufacturer: "Novartis",
    description: "Kháng viêm, giảm đau trong thoái hóa khớp, viêm khớp dạng thấp, đau cột sống, chấn thương.",
    searchTokens: ["voltaren", "diclofenac", "cataflam", "giam dau", "khang viem", "dau khop", "nsaid"],
    drugbankId: "DB00586",
  },
  {
    id: "aspirin-protect",
    tradeName: "Aspirin Protect",
    genericName: "Acetylsalicylic Acid (Aspirin)",
    activeIngredients: "Acid Acetylsalicylic 100mg (hoặc 81mg)",
    category: "Chống kết tập tiểu cầu / Kháng viêm",
    categoryEn: "Antiplatelet / Salicylate",
    defaultDosage: "100mg",
    dosageForm: "Viên bao tan trong ruột",
    manufacturer: "Bayer",
    description: "Ức chế kết tập tiểu cầu, dự phòng thứ phát nhồi máu cơ tim và đột quỵ do thiếu máu cục bộ.",
    searchTokens: ["aspirin", "aspirin protect", "aspirin 81", "chong dong mau", "tim mach"],
    drugbankId: "DB00945",
  },
  {
    id: "efferalgan",
    tradeName: "Efferalgan",
    genericName: "Paracetamol",
    activeIngredients: "Paracetamol 500mg",
    category: "Giảm đau, hạ sốt dạng sủi",
    categoryEn: "Analgesic / Antipyretic",
    defaultDosage: "500mg",
    dosageForm: "Viên sủi bọt",
    manufacturer: "UPSA",
    description: "Hạ sốt nhanh, giảm đau răng, đau đầu, đau cơ bằng viên sủi hòa tan trong nước.",
    searchTokens: ["efferalgan", "paracetamol", "vien sui", "ha sot", "giam dau"],
    drugbankId: "DB00316",
  },
  {
    id: "hapacol",
    tradeName: "Hapacol 650",
    genericName: "Paracetamol",
    activeIngredients: "Paracetamol 650mg",
    category: "Giảm đau, hạ sốt",
    categoryEn: "Analgesic / Antipyretic",
    defaultDosage: "650mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Dược Hậu Giang (DHG Pharma)",
    description: "Điều trị các triệu chứng đau như đau đầu, đau nửa đầu, đau răng, đau nhức xương khớp và sốt.",
    searchTokens: ["hapacol", "hapacol 650", "paracetamol", "dhg", "ha sot", "giam dau"],
    drugbankId: "DB00316",
  },
  {
    id: "xarelto",
    tradeName: "Xarelto",
    genericName: "Rivaroxaban",
    activeIngredients: "Rivaroxaban 10mg / 15mg / 20mg",
    category: "Thuốc chống đông đường uống thế hệ mới (DOAC / Ức chế yếu tố Xa)",
    categoryEn: "Direct Oral Anticoagulant (DOAC)",
    defaultDosage: "15mg / 20mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Bayer",
    description: "Phòng ngừa đột quỵ và thuyên tắc mạch toàn thân ở bệnh nhân rung nhĩ không do van tim.",
    searchTokens: ["xarelto", "rivaroxaban", "chong dong mau", "doac", "rung nhi", "thuyen tac mach"],
    drugbankId: "DB06228",
  },
  {
    id: "eliquis",
    tradeName: "Eliquis",
    genericName: "Apixaban",
    activeIngredients: "Apixaban 2.5mg / 5mg",
    category: "Thuốc chống đông thế hệ mới (DOAC / Ức chế yếu tố Xa)",
    categoryEn: "Direct Oral Anticoagulant (DOAC)",
    defaultDosage: "5mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Pfizer / BMS",
    description: "Dự phòng đột quỵ ở bệnh nhân rung nhĩ và điều trị huyết khối tĩnh mạch sâu (DVT).",
    searchTokens: ["eliquis", "apixaban", "chong dong mau", "doac", "rung nhi"],
    drugbankId: "DB06605",
  },
  {
    id: "amlor",
    tradeName: "Amlor (Norvasc)",
    genericName: "Amlodipine Besylate",
    activeIngredients: "Amlodipine 5mg / 10mg",
    category: "Thuốc tim mạch / Huyết áp (Chẹn kênh Calci DHP)",
    categoryEn: "Calcium Channel Blocker (CCB)",
    defaultDosage: "5mg",
    dosageForm: "Viên nang / Viên nén",
    manufacturer: "Pfizer",
    description: "Điều trị tăng huyết áp, đau thắt ngực ổn định mạn tính và đau thắt ngực do co thắt mạch (Prinzmetal).",
    searchTokens: ["amlor", "norvasc", "amlodipine", "huyet ap", "tang huyet ap", "chen calci"],
    drugbankId: "DB00381",
  },
  {
    id: "zinnat",
    tradeName: "Zinnat",
    genericName: "Cefuroxime Axetil",
    activeIngredients: "Cefuroxime Axetil 250mg / 500mg",
    category: "Kháng sinh Cephalosporin thế hệ 2",
    categoryEn: "Cephalosporin Antibiotic",
    defaultDosage: "500mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "GSK",
    description: "Điều trị nhiễm khuẩn tai mũi họng, viêm xoang, viêm phế quản, nhiễm khuẩn đường tiết niệu.",
    searchTokens: ["zinnat", "cefuroxime", "khang sinh", "viem phoi", "viem xoang"],
    drugbankId: "DB01112",
  },
  {
    id: "klacid",
    tradeName: "Klacid MR",
    genericName: "Clarithromycin",
    activeIngredients: "Clarithromycin 500mg",
    category: "Kháng sinh nhóm Macrolid",
    categoryEn: "Macrolide Antibiotic",
    defaultDosage: "500mg",
    dosageForm: "Viên nén phóng thích có biến đổi",
    manufacturer: "Abbott",
    description: "Điều trị viêm amidan, viêm phổi cộng đồng, nhiễm khuẩn mô mềm và phối hợp diệt H. pylori.",
    searchTokens: ["klacid", "clarithromycin", "khang sinh", "macrolide", "viem hong"],
    drugbankId: "DB01211",
  },
  {
    id: "medrol",
    tradeName: "Medrol",
    genericName: "Methylprednisolone",
    activeIngredients: "Methylprednisolone 4mg / 16mg",
    category: "Kháng viêm Corticosteroid",
    categoryEn: "Glucocorticoid",
    defaultDosage: "4mg (hoặc 16mg)",
    dosageForm: "Viên nén",
    manufacturer: "Pfizer",
    description: "Kháng viêm mạnh, chống dị ứng và ức chế miễn dịch trong viêm khớp, lupus, hen phế quản.",
    searchTokens: ["medrol", "methylprednisolone", "corticoid", "khang viem", "di ung", "hen"],
    drugbankId: "DB00959",
  },
  {
    id: "diamicron",
    tradeName: "Diamicron MR",
    genericName: "Gliclazide",
    activeIngredients: "Gliclazide 30mg / 60mg",
    category: "Thuốc đái tháo đường nhóm Sulfonylurea",
    categoryEn: "Antidiabetic (Sulfonylurea)",
    defaultDosage: "60mg",
    dosageForm: "Viên nén phóng thích biến đổi",
    manufacturer: "Servier",
    description: "Kích thích tế bào beta tụy tiết insulin, điều trị đái tháo đường type 2 khi chế độ ăn không đủ kiểm soát.",
    searchTokens: ["diamicron", "gliclazide", "sulfonylurea", "tieu duong", "ha duong huyet"],
    drugbankId: "DB01120",
  },
  {
    id: "telfast",
    tradeName: "Telfast HD",
    genericName: "Fexofenadine Hydrochloride",
    activeIngredients: "Fexofenadine HCl 180mg (hoặc 60mg / 120mg)",
    category: "Kháng Histamin H1 thế hệ 2 (Không gây buồn ngủ)",
    categoryEn: "Antihistamine",
    defaultDosage: "180mg",
    dosageForm: "Viên nén bao phim",
    manufacturer: "Sanofi",
    description: "Điều trị triệu chứng viêm mũi dị ứng theo mùa và mề đay tự phát mạn tính.",
    searchTokens: ["telfast", "fexofenadine", "di ung", "me day", "ngua", "khang histamin"],
    drugbankId: "DB00950",
  },
  {
    id: "berberin",
    tradeName: "Berberin",
    genericName: "Berberin Clorid",
    activeIngredients: "Berberin Clorid 50mg / 100mg",
    category: "Thuốc kháng khuẩn đường ruột nguồn gốc thảo dược",
    categoryEn: "Antidiarrheal / Herbal antimicrobial",
    defaultDosage: "100mg",
    dosageForm: "Viên nang / Viên bao đường",
    manufacturer: "OPC / Dược Phẩm TW",
    description: "Điều trị kiết lỵ, tiêu chảy, viêm ruột và rối loạn tiêu hóa do nhiễm khuẩn đường ruột.",
    searchTokens: ["berberin", "tieu chay", "dau bung", "roi loan tieu hoa", "duoc lieu"],
    drugbankId: "DB02338",
  },
  {
    id: "brufen",
    tradeName: "Brufen",
    genericName: "Ibuprofen",
    activeIngredients: "Ibuprofen 400mg (hoặc 200mg / Siro 100mg/5ml)",
    category: "Kháng viêm không steroid (NSAID)",
    categoryEn: "NSAID",
    defaultDosage: "400mg",
    dosageForm: "Viên nén bao phim / Siro",
    manufacturer: "Abbott",
    description: "Giảm đau, kháng viêm, hạ sốt trong đau bụng kinh, nhức đầu, đau răng, viêm khớp.",
    searchTokens: ["brufen", "ibuprofen", "giam dau", "khang viem", "ha sot", "nsaid"],
    drugbankId: "DB01050",
  },
  {
    id: "losec",
    tradeName: "Losec",
    genericName: "Omeprazole",
    activeIngredients: "Omeprazole Magnesium 20mg / 40mg",
    category: "Kháng tiết acid dạ dày (PPI)",
    categoryEn: "Proton Pump Inhibitor (PPI)",
    defaultDosage: "20mg",
    dosageForm: "Viên nang / Viên nén Mups",
    manufacturer: "AstraZeneca",
    description: "Điều trị viêm loét dạ dày tá tràng, hội chứng Zollinger-Ellison và trào ngược thực quản.",
    searchTokens: ["losec", "omeprazole", "da day", "trao nguoc", "ppi"],
    drugbankId: "DB00338",
  },
  {
    id: "ventolin",
    tradeName: "Ventolin Inhaler",
    genericName: "Salbutamol (Albuterol)",
    activeIngredients: "Salbutamol 100mcg/nhát xịt (hoặc Viên 2mg/4mg)",
    category: "Chủ vận thụ thể Beta-2 giao cảm (Giãn phế quản tác dụng ngắn - SABA)",
    categoryEn: "Short-acting beta2-agonist (SABA)",
    defaultDosage: "100mcg / nhát xịt",
    dosageForm: "Bình xịt định liều (MDI) / Viên nén",
    manufacturer: "GSK",
    description: "Cắt cơn co thắt phế quản cấp trong hen phế quản, viêm phế quản mạn tính và bệnh phổi tắc nghẽn mạn tính (COPD).",
    searchTokens: ["ventolin", "salbutamol", "albuterol", "xit hen", "kho tho", "hen suyễn", "copd"],
    drugbankId: "DB01001",
  },
];

/**
 * Remove Vietnamese diacritics and convert to lower case for fast fuzzy search.
 */
export function removeVietnameseAccents(str: string): string {
  return str
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

/**
 * Search Vietnamese drugs by trade name, generic name, active ingredients, or symptom tokens.
 */
export function searchVietnameseDrugs(query: string, limit = 8): VietnameseDrug[] {
  const normalizedQuery = removeVietnameseAccents(query.trim());
  if (!normalizedQuery) {
    return VIETNAMESE_DRUGS_CATALOG.slice(0, limit);
  }

  const queryTerms = normalizedQuery.split(/\s+/).filter(Boolean);

  const scored = VIETNAMESE_DRUGS_CATALOG.map((drug) => {
    let score = 0;
    const tradeNorm = removeVietnameseAccents(drug.tradeName);
    const genericNorm = removeVietnameseAccents(drug.genericName);
    const activeNorm = removeVietnameseAccents(drug.activeIngredients);
    const descNorm = removeVietnameseAccents(drug.description);
    const catNorm = removeVietnameseAccents(drug.category);

    // Exact trade name match
    if (tradeNorm === normalizedQuery) score += 100;
    else if (tradeNorm.startsWith(normalizedQuery)) score += 60;
    else if (tradeNorm.includes(normalizedQuery)) score += 40;

    // Generic name match
    if (genericNorm === normalizedQuery) score += 80;
    else if (genericNorm.includes(normalizedQuery)) score += 35;

    // Active ingredient match
    if (activeNorm.includes(normalizedQuery)) score += 30;

    // Tokens match
    for (const term of queryTerms) {
      if (drug.searchTokens.some((tok) => removeVietnameseAccents(tok).includes(term))) {
        score += 15;
      }
      if (catNorm.includes(term)) score += 10;
      if (descNorm.includes(term)) score += 5;
    }

    return { drug, score };
  });

  return scored
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((item) => item.drug);
}

/**
 * Deterministic Clinical Drug-Drug Interaction Matrix for instant Vietnamese checks.
 */
const KNOWN_INTERACTION_RULES: Array<{
  keywordsA: string[];
  keywordsB: string[];
  level: TrafficLightLevel;
  title: string;
  mechanism: string;
  clinicalEffect: string;
  recommendation: string;
  symptomsToWatch: string[];
  sourceAuthority: string;
}> = [
  // 1. Clopidogrel (Plavix) + NSAID/Aspirin -> Severe Bleeding Risk
  {
    keywordsA: ["clopidogrel", "plavix"],
    keywordsB: ["aspirin", "voltaren", "diclofenac", "brufen", "ibuprofen", "cataflam"],
    level: "danger",
    title: "Tăng nguy cơ xuất huyết tiêu hóa và chảy máu nghiêm trọng",
    mechanism: "Phối hợp thuốc chống kết tập tiểu cầu (Clopidogrel) và thuốc kháng viêm NSAID ức chế mạnh quá trình đông máu và gây tổn thương niêm mạc dạ dày.",
    clinicalEffect: "Nguy cơ loét dạ dày tiến triển, nôn ra máu, đi ngoài phân đen và chảy máu khó cầm.",
    recommendation: "Không tự ý dùng chung khi chưa có chỉ định của bác sĩ tim mạch/tiêu hóa. Có thể cần bổ sung thuốc bảo vệ dạ dày (PPI) hoặc đổi giảm đau thay thế (Paracetamol).",
    symptomsToWatch: ["Phân đen hoặc lẫn máu", "Nôn ra dịch màu bã cà phê", "Chảy máu chân răng/bầm tím bất thường", "Chóng mặt hoặc hoa mắt"],
    sourceAuthority: "DrugBank v5.1 / FDA DDI Database",
  },
  // 2. Clopidogrel (Plavix) + Omeprazole / Esomeprazole (Nexium / Losec) -> Loss of Antiplatelet Efficacy
  {
    keywordsA: ["clopidogrel", "plavix"],
    keywordsB: ["nexium", "esomeprazole", "losec", "omeprazole"],
    level: "danger",
    title: "Làm giảm hiệu quả chống huyết khối của Clopidogrel (Tăng nguy cơ tái tắc mạch)",
    mechanism: "Omeprazole / Esomeprazole ức chế mạnh enzym gan CYP2C19 - enzym cần thiết để chuyển hóa Clopidogrel thành dạng có hoạt tính sinh học.",
    clinicalEffect: "Nồng độ hoạt chất Clopidogrel trong máu bị giảm rõ rệt, làm mất khả năng chống đông và tăng nguy cơ nhồi máu cơ tim hoặc tái tắc stent.",
    recommendation: "Nên thay thế PPI bằng Pantoprazole, Rabeprazole hoặc thuốc kháng H2 ít ức chế enzym CYP2C19 theo hướng dẫn của bác sĩ.",
    symptomsToWatch: ["Đau tức ngực tái phát", "Khó thở", "Hồi hộp đánh trống ngực"],
    sourceAuthority: "DrugBank v5.1 / Bộ Y Tế Việt Nam Dược Thư",
  },
  // 3. Statin (Lipitor / Crestor / Atorvastatin) + Macrolide (Klacid / Clarithromycin) -> Rhabdomyolysis Risk
  {
    keywordsA: ["lipitor", "atorvastatin", "crestor", "rosuvastatin"],
    keywordsB: ["klacid", "clarithromycin"],
    level: "danger",
    title: "Tăng độc tính Statin, nguy cơ đau cơ nặng và tiêu cơ vân cấp (Rhabdomyolysis)",
    mechanism: "Clarithromycin ức chế mạnh enzym CYP3A4, làm giảm thải trừ và tăng nồng độ Statin trong máu lên gấp nhiều lần.",
    clinicalEffect: "Tổn thương tế bào cơ vân, phóng thích myoglobin gây tắc nghẽn ống thận và suy thận cấp.",
    recommendation: "Tạm dừng Statin trong đợt điều trị kháng sinh Clarithromycin hoặc chuyển sang kháng sinh nhóm khác (như Augmentin, Cefuroxime) theo chỉ định y tế.",
    symptomsToWatch: ["Đau cơ dữ dội, yếu cơ bắp chân/đùi", "Nước tiểu có màu nâu đỏ hoặc sẫm như xì dầu", "Mệt mỏi toàn thân đột ngột"],
    sourceAuthority: "DrugBank v5.1 / FIDES Verification",
  },
  // 4. ACEi (Coversyl / Perindopril) + NSAID (Voltaren / Brufen) -> Renal Impairment & Reduced BP control
  {
    keywordsA: ["coversyl", "perindopril"],
    keywordsB: ["voltaren", "diclofenac", "brufen", "ibuprofen", "cataflam"],
    level: "caution",
    title: "Giảm tác dụng hạ huyết áp và tăng nguy cơ suy giảm chức năng thận",
    mechanism: "NSAID ức chế prostaglandin tại thận, gây co tiểu động mạch đến, làm giảm lưu lượng máu lọc qua cầu thận và đối kháng tác dụng giãn mạch của ACEi.",
    clinicalEffect: "Huyết áp có thể tăng trở lại, giữ nước, phù nhẹ và suy giảm độ lọc cầu thận ở người cao tuổi.",
    recommendation: "Hạn chế dùng NSAID kéo dài. Theo dõi huyết áp hàng ngày và kiểm tra chức năng thận nếu phải dùng phối hợp trên 5 ngày.",
    symptomsToWatch: ["Huyết áp tăng vọt", "Phù mắt cá chân", "Tiểu ít hơn bình thường"],
    sourceAuthority: "DrugBank v5.1 / ESC Guidelines",
  },
  // 5. Duplicate Paracetamol (Panadol + Efferalgan / Hapacol) -> Overdose Hepatotoxicity
  {
    keywordsA: ["panadol", "panadol extra"],
    keywordsB: ["efferalgan", "hapacol", "paracetamol"],
    level: "danger",
    title: "Trùng lặp hoạt chất Paracetamol (Nguy cơ ngộ độc và hoại tử tế bào gan)",
    mechanism: "Cả hai thuốc đều chứa Paracetamol. Dùng đồng thời dễ vượt quá liều tối đa 4g/ngày (hoặc 60mg/kg/ngày).",
    clinicalEffect: "Tích lũy chất chuyển hóa độc hại NAPQI làm cạn kiệt Glutathione gan, dẫn đến suy gan cấp.",
    recommendation: "Chỉ chọn duy nhất 1 loại thuốc chứa Paracetamol tại một thời điểm. Khoảng cách giữa các lần uống tối thiểu 4 - 6 giờ.",
    symptomsToWatch: ["Buồn nôn, nôn mửa", "Đau tức hạ sườn phải", "Vàng da, vàng mắt", "Mệt lả"],
    sourceAuthority: "Dược Thư Quốc Gia Việt Nam / FDA Warning",
  },
  // 6. Metformin (Glucophage) + ACEi / ARB (Coversyl) -> Beneficial / Safe Combination
  {
    keywordsA: ["glucophage", "metformin"],
    keywordsB: ["coversyl", "perindopril", "amlor", "amlodipine"],
    level: "safe",
    title: "Phối hợp an toàn & chuẩn trong điều trị đái tháo đường kèm tăng huyết áp",
    mechanism: "Không có tương tác dược lực học hoặc dược động học bất lợi. ACEi giúp bảo vệ vi mạch thận ở bệnh nhân đái tháo đường.",
    clinicalEffect: "Kiểm soát đường huyết ổn định kết hợp ổn định huyết áp, bảo tồn chức năng thận lâu dài.",
    recommendation: "Duy trì uống đúng giờ theo đơn thuốc. Uống Metformin sau bữa ăn để hạn chế đầy bụng.",
    symptomsToWatch: [],
    sourceAuthority: "ADA / KDIGO Clinical Practice Guidelines",
  },
  // 7. Statin (Lipitor) + Coversyl (Perindopril) -> Safe Combination
  {
    keywordsA: ["lipitor", "atorvastatin", "crestor", "rosuvastatin"],
    keywordsB: ["coversyl", "perindopril", "concor", "bisoprolol"],
    level: "safe",
    title: "Phối hợp an toàn & chuẩn trong dự phòng biến cố tim mạch",
    mechanism: "Không gây tương tác bất lợi. Phối hợp hiệp đồng giảm xơ vữa mạch máu và ổn định mảng bám.",
    clinicalEffect: "Tối ưu hóa bảo vệ tim mạch, giảm nguy cơ nhồi máu cơ tim và đột quỵ.",
    recommendation: "Uống thuốc đều đặn mỗi ngày. Uống Statin vào buổi tối trước khi đi ngủ để đạt hiệu quả chuyển hóa cao nhất.",
    symptomsToWatch: [],
    sourceAuthority: "AHA / ACC Cardiovascular Guidelines",
  },
  // 8. Augmentin + Panadol -> Safe Combination
  {
    keywordsA: ["augmentin", "amoxicillin"],
    keywordsB: ["panadol", "panadol extra", "hapacol", "efferalgan"],
    level: "safe",
    title: "Phối hợp an toàn khi điều trị nhiễm khuẩn kèm sốt / đau",
    mechanism: "Không có cạnh tranh chuyển hóa hoặc đối kháng tác dụng sinh học.",
    clinicalEffect: "Augmentin diệt vi khuẩn gây bệnh trong khi Paracetamol giúp hạ sốt và giảm đau khó chịu cho người bệnh.",
    recommendation: "Uống đủ đợt kháng sinh (thường 5-7 ngày), không tự ý ngắt quãng khi thấy hết sốt.",
    symptomsToWatch: [],
    sourceAuthority: "Hướng dẫn điều trị Bộ Y Tế",
  },
];

/**
 * Check drug interactions instantly between a list of Vietnamese drug names.
 */
export function checkInstantDrugInteractions(drugNames: string[]): InteractionCheckResult {
  const cleanNames = drugNames
    .map((n) => n.trim())
    .filter((n, idx, arr) => n.length > 0 && arr.findIndex((x) => x.toLowerCase() === n.toLowerCase()) === idx);

  if (cleanNames.length < 2) {
    return {
      level: "safe",
      summary: "Cần chọn ít nhất 2 thuốc để kiểm tra tương tác.",
      alerts: [],
      checkedCount: cleanNames.length,
      medications: cleanNames,
    };
  }

  const foundAlerts: DrugInteractionAlert[] = [];
  const normalizedList = cleanNames.map((n) => removeVietnameseAccents(n));

  for (let i = 0; i < cleanNames.length; i++) {
    for (let j = i + 1; j < cleanNames.length; j++) {
      const nameA = normalizedList[i];
      const nameB = normalizedList[j];
      const origA = cleanNames[i];
      const origB = cleanNames[j];

      for (const rule of KNOWN_INTERACTION_RULES) {
        const matchesAtoA = rule.keywordsA.some((k) => nameA.includes(k));
        const matchesBtoB = rule.keywordsB.some((k) => nameB.includes(k));
        const matchesAtoB = rule.keywordsA.some((k) => nameB.includes(k));
        const matchesBtoA = rule.keywordsB.some((k) => nameA.includes(k));

        if ((matchesAtoA && matchesBtoB) || (matchesAtoB && matchesBtoA)) {
          // Avoid duplicate alerts for the same pair
          const already = foundAlerts.some(
            (al) =>
              (al.drugA === origA && al.drugB === origB && al.title === rule.title) ||
              (al.drugA === origB && al.drugB === origA && al.title === rule.title),
          );
          if (!already) {
            foundAlerts.push({
              drugA: origA,
              drugB: origB,
              level: rule.level,
              title: rule.title,
              mechanism: rule.mechanism,
              clinicalEffect: rule.clinicalEffect,
              recommendation: rule.recommendation,
              symptomsToWatch: rule.symptomsToWatch,
              sourceAuthority: rule.sourceAuthority,
            });
          }
        }
      }
    }
  }

  // Determine overall Traffic-Light Level
  let overallLevel: TrafficLightLevel = "safe";
  if (foundAlerts.some((a) => a.level === "danger")) {
    overallLevel = "danger";
  } else if (foundAlerts.some((a) => a.level === "caution")) {
    overallLevel = "caution";
  }

  let summary = "";
  if (overallLevel === "danger") {
    summary = `Phát hiện ${foundAlerts.filter((a) => a.level === "danger").length} tương tác nguy hiểm cần can thiệp y tế.`;
  } else if (overallLevel === "caution") {
    summary = `Phát hiện ${foundAlerts.filter((a) => a.level === "caution").length} tương tác cần lưu ý theo dõi.`;
  } else if (foundAlerts.length > 0) {
    summary = "Phối hợp thuốc tương thích an toàn theo hướng dẫn điều trị chuẩn.";
  } else {
    summary = "Chưa phát hiện tương tác đối kháng rõ ràng giữa các hoạt chất đã chọn trong cơ sở dữ liệu.";
  }

  return {
    level: overallLevel,
    summary,
    alerts: foundAlerts,
    checkedCount: cleanNames.length,
    medications: cleanNames,
  };
}
