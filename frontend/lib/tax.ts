// 세금 계산기 (진입 장치 1단계) — 기획서 4.6 "세금 쓰임 vs 우선순위"의 개인화 훅.
// 핵심: "내 월급 → 내 소득세 → 그 돈이 어느 분야로" 를 사실만으로 보여준다(판정 금지).
//
// ⚠️ 모두 추정치다. 정밀 세무계산이 아니라 무관심층을 멈춰 세우는 '체감용 근사'다.
//   - 소득세는 2024년 세율·공제 기준의 단순화 모델(본인 1인 기본공제만 가정).
//   - 부양가족·각종 세액공제(연금저축·의료비 등)는 반영하지 않는다 → 실제보다 다소 높게 나올 수 있다.
//   - 4대보험은 국가 일반예산이 아니라 별도 사회보험기금으로 가므로 분야 배분에서 분리한다.

const 만 = 10_000;

// ── 분야별 재원배분 — 열린재정 OPFI165(16대 분야, 결산=실제 집행)에서 받아온 공식 데이터.
//   데이터 파일은 ETL 잡이 생성: `python -m jobs.run --job budget` → lib/budget-data.json
//   분야 '비율' 산정에 쓴다(절대액은 조원 단위 결산값).
import budgetData from "./budget-data.json";

export interface BudgetField {
  code: string; // FLD_CD (열린재정 분야코드)
  name: string;
  trillion: number; // 조원 (결산)
  note: string; // 한 줄 예시 (사실 서술, 판정 X)
}

export interface BudgetMeta {
  year: number;
  basis: string; // '결산'(실제 집행) 등
  source: string;
  sourceUrl: string;
  totalTrillion: number;
}

export const BUDGET_META: BudgetMeta = {
  year: budgetData.year,
  basis: budgetData.basis,
  source: budgetData.source,
  sourceUrl: budgetData.source_url,
  totalTrillion: budgetData.total_trillion,
};

// 분야별 한 줄 예시(사실 서술). FLD_CD 기준 — 데이터가 바뀌어도 코드로 안정 매칭.
const NOTES_BY_CODE: Record<string, string> = {
  "010": "지방교부세·정부 운영 등",
  "020": "경찰·소방·재난 대응 등",
  "030": "재외국민·ODA·통일 등",
  "040": "병력 운영·전력 유지·방위력 개선",
  "050": "지방교육재정교부금·국립대 등",
  "060": "문화예술·체육·관광 등",
  "070": "물·대기·탄소중립 등",
  "080": "기초연금·복지·고용서비스 등",
  "090": "건강보험 지원·의료 등",
  "100": "농가 지원·식량·수산 등",
  "110": "중소기업 지원·에너지 등",
  "120": "도로·철도·물류 등",
  "130": "방송·통신·우정 등",
  "140": "국토·지역개발·주택 등",
  "150": "기초연구·국가전략기술 등",
  "160": "예비비",
};

export const BUDGET_FIELDS: BudgetField[] = budgetData.fields.map((f) => ({
  code: f.code,
  name: f.name,
  trillion: f.trillion,
  note: NOTES_BY_CODE[f.code] ?? "",
}));

const BUDGET_TOTAL = BUDGET_FIELDS.reduce((s, f) => s + f.trillion, 0);

export interface TaxResult {
  annualGross: number; // 연 세전
  nationalPension: number; // 국민연금(본인부담, 연)
  healthIns: number; // 건강보험(본인부담, 연)
  longTermCare: number; // 장기요양(연)
  employmentIns: number; // 고용보험(연)
  incomeTax: number; // 근로소득세 결정세액(연, 국세)
  localIncomeTax: number; // 지방소득세(연) = 소득세 10% (지방세)
  socialInsTotal: number; // 4대보험 합(연)
  incomeTaxTotal: number; // 소득세 + 지방소득세(연)
  // ── 소비세(추정) ──
  disposableIncome: number; // 연 가처분소득(실수령)
  consumption: number; // 연 소비지출 추정
  vat: number; // 부가가치세 추정(연, 국세)
  // ── 합계 ──
  nationalTax: number; // 국세 합(소득세 + 부가세) — 중앙정부 분야 배분 대상
  totalTax: number; // 내가 내는 세금 총액(소득세+지방소득세+부가세, 4대보험 제외)
  totalDeduction: number; // 급여에서 직접 떼이는 합(4대보험+소득세, 실수령 계산용)
  netMonthly: number; // 월 실수령(근사)
}

// 누진세율(2024 종합소득세 과세표준 기준): [상한, 세율, 누진공제]
const BRACKETS: [number, number, number][] = [
  [14_000_000, 0.06, 0],
  [50_000_000, 0.15, 1_260_000],
  [88_000_000, 0.24, 5_760_000],
  [150_000_000, 0.35, 15_440_000],
  [300_000_000, 0.38, 19_940_000],
  [500_000_000, 0.40, 25_940_000],
  [1_000_000_000, 0.42, 35_940_000],
  [Infinity, 0.45, 65_940_000],
];

function progressiveTax(base: number): number {
  for (const [ceil, rate, deduct] of BRACKETS) {
    if (base <= ceil) return Math.max(0, base * rate - deduct);
  }
  return 0;
}

// 근로소득공제(연 총급여 기준), 한도 2,000만원.
function earnedIncomeDeduction(gross: number): number {
  let d: number;
  if (gross <= 5_000_000) d = gross * 0.7;
  else if (gross <= 15_000_000) d = 3_500_000 + (gross - 5_000_000) * 0.4;
  else if (gross <= 45_000_000) d = 7_500_000 + (gross - 15_000_000) * 0.15;
  else if (gross <= 100_000_000) d = 12_000_000 + (gross - 45_000_000) * 0.05;
  else d = 14_750_000 + (gross - 100_000_000) * 0.02;
  return Math.min(d, 20_000_000);
}

// 근로소득세액공제 + 총급여 구간별 한도.
function earnedIncomeTaxCredit(computedTax: number, gross: number): number {
  const credit =
    computedTax <= 1_300_000
      ? computedTax * 0.55
      : 715_000 + (computedTax - 1_300_000) * 0.3;

  let cap: number;
  if (gross <= 33_000_000) cap = 740_000;
  else if (gross <= 70_000_000) cap = Math.max(660_000, 740_000 - (gross - 33_000_000) * 0.008);
  else if (gross <= 120_000_000) cap = Math.max(500_000, 660_000 - (gross - 70_000_000) * 0.5);
  else cap = Math.max(200_000, 500_000 - (gross - 120_000_000) * 0.5);

  return Math.min(credit, cap);
}

// 4대보험 본인부담률(2024). 국민연금은 기준소득월액 상·하한 적용.
const PENSION_RATE = 0.045;
const PENSION_BASE_MIN = 390_000;
const PENSION_BASE_MAX = 6_170_000;
const HEALTH_RATE = 0.03545;
const LTC_RATE = 0.1295; // 건강보험료 대비
const EMPLOYMENT_RATE = 0.009;

// 같은 급여라도 세금이 갈리는 '큰 변수'만 받는다(나머지는 추정으로 둠).
// 중소기업 취업자 소득세 감면(조특법 §30): 청년 90% / 그 외 70%, 연 200만원 한도.
export type SmeReduction = "none" | "youth" | "general";

export interface TaxOptions {
  dependents?: number; // 본인 외 부양가족 수(배우자·부모·자녀 등) → 인적공제 150만/명
  children?: number; // 그중 8~20세 자녀 수 → 자녀세액공제(세액에서 직접 차감)
  sme?: SmeReduction; // 중소기업 취업자 소득세 감면 대상 여부
}

const SME_RATE: Record<SmeReduction, number> = { none: 0, youth: 0.9, general: 0.7 };
const SME_CAP = 2_000_000; // 감면 한도(연)

// 자녀세액공제(2024): 1명 15만, 2명 35만, 3명 이상 35만 + (n-2)×30만.
function childTaxCredit(n: number): number {
  if (n <= 0) return 0;
  if (n === 1) return 150_000;
  if (n === 2) return 350_000;
  return 350_000 + (n - 2) * 300_000;
}

// 부가세 추정용 가정(모두 근사):
//  - 평균소비성향: 소득이 낮을수록 가처분소득 중 소비 비중이 높다(통계청 가계동향 근사).
//  - 부가세 과세 소비 비중: 월세·교육·의료·금융 등 면세를 빼면 소비의 약 70%가 과세 대상.
//  - 부가세는 가격에 포함(10%)되어 있으므로 과세소비 중 세금은 10/110.
const VAT_TAXABLE_SHARE = 0.7;
function avgPropensityToConsume(disposableAnnual: number): number {
  if (disposableAnnual <= 24_000_000) return 0.8;
  if (disposableAnnual <= 48_000_000) return 0.68;
  if (disposableAnnual <= 72_000_000) return 0.58;
  return 0.5;
}

/** 월 세전 급여(원)로부터 4대보험·소득세를 추정한다. */
export function estimateTax(monthlyGross: number, opts: TaxOptions = {}): TaxResult {
  const m = Math.max(0, Math.round(monthlyGross));
  const annualGross = m * 12;
  const dependents = Math.max(0, Math.floor(opts.dependents ?? 0));
  const children = Math.max(0, Math.min(dependents, Math.floor(opts.children ?? 0)));
  const smeRate = SME_RATE[opts.sme ?? "none"];

  const pensionBase = Math.min(Math.max(m, PENSION_BASE_MIN), PENSION_BASE_MAX);
  const nationalPension = Math.round(pensionBase * PENSION_RATE) * 12;
  const monthlyHealth = Math.round(m * HEALTH_RATE);
  const healthIns = monthlyHealth * 12;
  const longTermCare = Math.round(monthlyHealth * LTC_RATE) * 12;
  const employmentIns = Math.round(m * EMPLOYMENT_RATE) * 12;
  const socialInsTotal = nationalPension + healthIns + longTermCare + employmentIns;

  // 과세표준 = 총급여 - 근로소득공제 - 인적공제(본인+부양가족, 150만/명) - 보험료 공제(4대보험 본인부담)
  const personalDeduction = 1_500_000 * (1 + dependents);
  const taxBase = Math.max(
    0,
    annualGross - earnedIncomeDeduction(annualGross) - personalDeduction - socialInsTotal,
  );
  const computed = progressiveTax(taxBase);
  // 중소기업 감면은 산출세액 기준으로 먼저 적용(한도 200만/년). 근사이므로 전액 중소기업 근로 가정.
  const smeReduction = Math.round(Math.min(computed * smeRate, SME_CAP));
  // 결정세액 = 산출세액 - 중소기업감면 - 근로소득세액공제 - 자녀세액공제
  const incomeTax = Math.max(
    0,
    Math.round(
      computed - smeReduction - earnedIncomeTaxCredit(computed, annualGross) - childTaxCredit(children),
    ),
  );
  const localIncomeTax = Math.round(incomeTax * 0.1);
  const incomeTaxTotal = incomeTax + localIncomeTax;

  const totalDeduction = socialInsTotal + incomeTaxTotal;
  const netMonthly = Math.round((annualGross - totalDeduction) / 12);

  // 소비세(부가세) 추정 — 가처분소득 × 소비성향 × 과세비중 × 10/110.
  const disposableIncome = Math.max(0, annualGross - totalDeduction);
  const consumption = Math.round(disposableIncome * avgPropensityToConsume(disposableIncome));
  const vat = Math.round((consumption * VAT_TAXABLE_SHARE * 10) / 110);

  const nationalTax = incomeTax + vat; // 국세(분야 배분 대상)
  const totalTax = incomeTaxTotal + vat; // 내가 내는 세금 총액(4대보험 제외)

  return {
    annualGross,
    nationalPension,
    healthIns,
    longTermCare,
    employmentIns,
    incomeTax,
    localIncomeTax,
    socialInsTotal,
    incomeTaxTotal,
    disposableIncome,
    consumption,
    vat,
    nationalTax,
    totalTax,
    totalDeduction,
    netMonthly,
  };
}

export interface FieldShare extends BudgetField {
  ratio: number; // 0..1
  amount: number; // 내 국세 중 이 분야 몫(원)
}

/** 연 국세 총액(소득세+부가세)을 분야 비율대로 나눈다. */
export function distributeByBudget(nationalTax: number): FieldShare[] {
  return BUDGET_FIELDS.map((f) => {
    const ratio = f.trillion / BUDGET_TOTAL;
    return { ...f, ratio, amount: Math.round(nationalTax * ratio) };
  });
}

/** 원 단위를 "약 OO만원 / OO억" 으로 사람이 읽기 좋게. */
export function won(n: number): string {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}억원`;
  if (n >= 만) {
    const m = Math.round(n / 만);
    return `${m.toLocaleString("ko-KR")}만원`;
  }
  return `${n.toLocaleString("ko-KR")}원`;
}
