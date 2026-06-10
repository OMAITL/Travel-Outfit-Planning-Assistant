import type { InputMode, PlanningState } from "@/api/types";
import type { TripDay } from "@/stores/planning";

const STORAGE_KEY = "travel-outfit-session-history";
const MAX_RECORDS = 30;

export type HistoryFilter = "all" | "form" | "chat";

export interface FormDraftSnapshot {
  startDate: string;
  endDate: string;
  styleTags: string[];
  avoidItems: string[];
  categoryBudgets: { top: number; bottom: number; shoes: number; acc: number };
  gender: string;
  heightCm: number;
  weightKg: number;
  bodyType: string;
  skinTone: string;
}

export interface SessionUiSnapshot {
  currentCityKey?: string;
  selectedSpotIds?: string[];
  days?: TripDay[];
  planMode?: "auto" | "manual";
  selectedDayIndex?: number;
  demoReportActive?: boolean;
  formDraft?: FormDraftSnapshot;
}

export interface SessionRecord {
  id: string;
  mode: InputMode;
  title: string;
  subtitle: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  state: PlanningState | null;
  ui?: SessionUiSnapshot;
}

function readAll(): SessionRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SessionRecord[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(records: SessionRecord[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(records.slice(0, MAX_RECORDS)));
}

export function listSessionHistory(): SessionRecord[] {
  return readAll().sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getSessionRecord(id: string): SessionRecord | undefined {
  return readAll().find((r) => r.id === id);
}

export function deleteSessionRecord(id: string) {
  writeAll(readAll().filter((r) => r.id !== id));
}

export function upsertSessionRecord(record: SessionRecord) {
  const records = readAll().filter((r) => r.id !== record.id);
  records.unshift(record);
  writeAll(records);
}

export function newSessionId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function tripDestination(state: PlanningState | null): string | undefined {
  const trip = state?.trip as { destination?: string } | null | undefined;
  return trip?.destination;
}

export function buildSessionStatus(mode: InputMode, state: PlanningState | null): string {
  const hasReport = (state?.report?.daily_cards?.length ?? 0) > 0;
  if (mode === "form") {
    return hasReport ? "图文报告 + 商品" : "表单规划中";
  }
  if (hasReport) return "已生成文字报告";
  if ((state?.messages?.length ?? 0) > 0) return "对话收集中";
  return "进行中";
}

export function buildSessionTitle(state: PlanningState | null): { title: string; subtitle: string } {
  const report = state?.report;
  const intent = state?.chat_intent;
  const destination =
    report?.destination || intent?.destination || tripDestination(state) || "未命名行程";
  const days = report?.trip_days;
  const title = days ? `${destination} · ${days}日` : String(destination);

  const parts: string[] = [];
  if (report?.start_date && report?.end_date) {
    parts.push(`${report.start_date} – ${report.end_date}`);
  } else if (intent?.start_date && intent?.end_date) {
    parts.push(`${intent.start_date} – ${intent.end_date}`);
  }
  if (intent?.scene_type) parts.push(intent.scene_type);
  if (intent?.spot_names?.length) parts.push(intent.spot_names.join("、"));
  if (report?.summary && !intent?.spot_names?.length) {
    const short = report.summary.length > 28 ? `${report.summary.slice(0, 28)}…` : report.summary;
    parts.push(short);
  }

  return { title, subtitle: parts.join(" · ") || "—" };
}

export function buildSessionRecord(
  id: string,
  mode: InputMode,
  state: PlanningState | null,
  ui: SessionUiSnapshot,
  existing?: SessionRecord,
): SessionRecord {
  const { title, subtitle } = buildSessionTitle(state);
  const now = new Date().toISOString();
  return {
    id,
    mode,
    title,
    subtitle,
    status: buildSessionStatus(mode, state),
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    state: state ? JSON.parse(JSON.stringify(state)) : null,
    ui: JSON.parse(JSON.stringify(ui)),
  };
}

export function filterSessionHistory(
  records: SessionRecord[],
  filter: HistoryFilter,
): SessionRecord[] {
  if (filter === "all") return records;
  return records.filter((r) => r.mode === filter);
}

export function formatHistoryTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return `今天 ${d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (
    d.getFullYear() === yesterday.getFullYear() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getDate() === yesterday.getDate()
  ) {
    return "昨天";
  }
  return d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

export function reportPreviewText(state: PlanningState | null): string {
  const report = state?.report;
  const card = report?.daily_cards?.[0];
  if (!report || !card) return "暂无报告内容";

  const dest = report.destination;
  const days = report.trip_days;
  const spot = card.spot_names?.[0] || card.morning || "";
  const outfit = card.outfit?.outfit_summary || card.outfit_items?.map((i) => i.text).join(" · ");
  const bits = [`${dest} · ${days}日 · 整套穿搭`];
  if (spot) bits.push(spot);
  if (outfit) bits.push(outfit.length > 60 ? `${outfit.slice(0, 60)}…` : outfit);
  return bits.join("\n");
}

export function formPreviewText(state: PlanningState | null): string {
  const report = state?.report;
  if (!report) return "表单行程，报告生成中或未保存";
  const styles = report.summary || "";
  const dates =
    report.start_date && report.end_date
      ? `${report.start_date} – ${report.end_date}`
      : "";
  const parts = [`${report.destination} · ${report.trip_days}日`];
  if (dates) parts.push(dates);
  if (styles) parts.push(styles.length > 40 ? `${styles.slice(0, 40)}…` : styles);
  parts.push("含图文报告与商品推荐");
  return parts.join("\n");
}
