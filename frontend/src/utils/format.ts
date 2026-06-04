const WEEKDAY_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatMd(iso: string): string {
  const dt = parseDate(iso);
  return `${dt.getMonth() + 1}/${dt.getDate()}`;
}

export function weekdayLabel(iso: string): string {
  const day = parseDate(iso).getDay();
  const index = day === 0 ? 6 : day - 1;
  return WEEKDAY_ZH[index] ?? "";
}

export function weatherIcon(condition: string): string {
  if (condition.includes("雨")) return "🌧";
  if (condition.includes("雪")) return "❄";
  if (condition.includes("晴")) return "☀";
  if (condition.includes("云")) return "⛅";
  return "🌤";
}

export function weatherLine(w: { condition: string; temp_min: number; temp_max: number; rain_prob?: number | null }): string {
  const icon = weatherIcon(String(w.condition));
  let line = `${icon} ${w.condition} ${w.temp_min}–${w.temp_max}°C`;
  if (w.rain_prob != null) line += ` · 降水 ${w.rain_prob}%`;
  return line;
}

export function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(base: Date, days: number): Date {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

/** Split outfit summary into labeled items (pipe-separated format). */
export function parseOutfitItems(summary: string): { label: string; text: string }[] {
  const segments = summary
    .split(/[|｜]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const labelPattern = /^(上装|下装|鞋|外套|配饰|内搭|包)[：:]\s*(.+)$/;
  const items: { label: string; text: string }[] = [];

  for (const segment of segments) {
    const m = segment.match(labelPattern);
    if (m) {
      items.push({ label: m[1], text: m[2].trim() });
    }
  }

  if (!items.length && summary) {
    items.push({ label: "穿搭", text: summary.slice(0, 120) });
  }
  return items;
}
