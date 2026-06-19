// OG 이미지용 한글 폰트 서브셋 생성 스크립트.
// Google Fonts text= API 는 요청한 글리프만 담은 작은 TTF 를 돌려준다.
// OG 카드에 나타날 수 있는 모든 한글(정당명 5개 + 고정 문구)을 한 번에 받아 번들한다.
// → 런타임 네트워크 의존 제거 + @vercel/og 의 Windows 기본폰트 경로 버그 회피
//   (fonts 배열이 항상 non-empty 가 되어 깨진 기본 폰트를 로드하지 않음).
// 재생성: node scripts/fetch-og-font.mjs
import { writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dir = dirname(fileURLToPath(import.meta.url));
// OG 라우트에 콜로케이트(new URL 로 로드). edge 런타임에서 자산으로 번들됨.
const OUT = join(__dir, "..", "app", "api", "og", "NotoSansKR-og.ttf");

// ⚠️ OG 카드에 등장하는 '모든' 글리프를 빠짐없이 포함해야 한다.
//    하나라도 빠지면 @vercel/og 가 깨진 기본 폰트로 폴백 → Windows 에서 크래시.
const TEXT = [
  "표심 · Pyosim",
  "더불어민주당",
  "국민의힘",
  "조국혁신당",
  "개혁신당",
  "진보당",
  "나와 가장 많이 겹친 곳",
  "문항 응답",
  "실제 국회 표결 일치도",
  "지지",
  "반대",
  "권유 아님",
  "0123456789%",
  "abcdefghijklmnopqrstuvwxyz",
  "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
].join(" ");

const css = await fetch(
  `https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@700&text=${encodeURIComponent(TEXT)}`,
  {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40 Safari/537.36",
    },
  },
).then((r) => r.text());

const url = css.match(/src:\s*url\(([^)]+)\)/)?.[1];
if (!url) {
  console.error("폰트 URL 파싱 실패:\n", css);
  process.exit(1);
}
const buf = Buffer.from(await fetch(url).then((r) => r.arrayBuffer()));
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, buf);
console.log(`저장: ${OUT} (${buf.length} bytes)`);
