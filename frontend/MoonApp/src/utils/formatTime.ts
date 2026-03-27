export function formatTime(seconds: number): string {
  const min = Math.round(seconds / 60);
  if (min >= 60) return `${Math.floor(min / 60)}시간${min % 60}분`;
  return `${min}분`;
}
