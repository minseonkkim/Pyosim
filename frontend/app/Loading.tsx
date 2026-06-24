// 공용 로딩 표시 — 앱 곳곳에 복붙돼 있던 '불러오는 중…' 마크업을 한 곳에서 관리한다.
// 기본은 화면 전체용(<main> 래퍼). inline=true면 피드 안에 끼우는 한 줄로 쓴다.

export default function Loading({
  text = "불러오는 중…",
  inline = false,
}: {
  text?: string;
  inline?: boolean;
}) {
  const line = <p className="muted">{text}</p>;
  return inline ? line : <main>{line}</main>;
}
