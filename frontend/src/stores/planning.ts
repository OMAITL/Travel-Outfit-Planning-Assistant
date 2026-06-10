import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { postPlan } from "@/api/client";
import type { City, InputMode, PlanningState, Spot, TripFormPayload } from "@/api/types";
import { STATIC_CITIES } from "@/data/cities";
import { addDays, parseDate, weatherIcon } from "@/utils/format";
import { planAutoItineraryIds } from "@/utils/itinerary";
import {
  buildSessionRecord,
  deleteSessionRecord,
  getSessionRecord,
  listSessionHistory,
  newSessionId,
  upsertSessionRecord,
  type SessionRecord,
  type SessionUiSnapshot,
  type FormDraftSnapshot,
} from "@/utils/sessionHistory";

const WEEKDAY_ZH = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

export interface TripDay {
  dateShort: string;
  weekday: string;
  title: string;
  weather: string;
  temp: string;
  reason: string;
  spotIds: string[];
  sceneSpots: string[];
  morningId?: string;
  afternoonId?: string;
  eveningId?: string;
}

function createEmptyDay(d: Date): TripDay {
  const m = d.getMonth() + 1;
  const dayNum = d.getDate();
  const wd = WEEKDAY_ZH[d.getDay()];
  return {
    dateShort: `${m}/${dayNum}`,
    weekday: wd,
    title: `${m}月${dayNum}日 · ${wd}`,
    weather: "",
    temp: "",
    reason: "",
    spotIds: [],
    sceneSpots: [],
  };
}

function createDefaultEmptyDays(): TripDay[] {
  const start = addDays(new Date(), 1);
  const end = addDays(new Date(), 3);
  const days: TripDay[] = [];
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    days.push(createEmptyDay(new Date(d)));
  }
  return days;
}

export function shortSpotLabel(name: string): string {
  return name
    .replace("洱海生态廊道", "洱海")
    .replace("大理古城", "古城")
    .replace("崇圣寺三塔", "三塔");
}

export const usePlanningStore = defineStore("planning", () => {
  const state = ref<PlanningState | null>(null);
  const cities = ref<City[]>([...STATIC_CITIES]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const selectedDayIndex = ref(0);
  const manualActiveDay = ref(0);
  const inputTab = ref<"form" | "chat">("form");
  const reportHighlight = ref(false);
  const demoReportActive = ref(false);
  const editItinerary = ref(false);
  const toast = ref<string | null>(null);
  const planMode = ref<"auto" | "manual">("auto");
  const currentCityKey = ref("dali");
  const selectedSpotIds = ref<string[]>([]);
  const days = ref<TripDay[]>(createDefaultEmptyDays());
  const historyOpen = ref(false);
  const sessionHistory = ref<SessionRecord[]>(listSessionHistory());
  const activeSessionByMode = ref<{ form?: string; chat?: string }>({});
  const lastFormDraft = ref<FormDraftSnapshot | null>(null);
  const formDraftRestoreTick = ref(0);

  const activeSessionId = computed(() => activeSessionByMode.value[inputTab.value]);

  function setFormDraft(draft: FormDraftSnapshot) {
    lastFormDraft.value = JSON.parse(JSON.stringify(draft));
  }

  function uiSnapshot(): SessionUiSnapshot {
    return {
      currentCityKey: currentCityKey.value,
      selectedSpotIds: [...selectedSpotIds.value],
      days: JSON.parse(JSON.stringify(days.value)) as TripDay[],
      planMode: planMode.value,
      selectedDayIndex: selectedDayIndex.value,
      demoReportActive: demoReportActive.value,
      formDraft: lastFormDraft.value
        ? (JSON.parse(JSON.stringify(lastFormDraft.value)) as FormDraftSnapshot)
        : undefined,
    };
  }

  function ensureActiveSession(mode: InputMode): string {
    let id = activeSessionByMode.value[mode];
    if (!id) {
      id = newSessionId();
      activeSessionByMode.value = { ...activeSessionByMode.value, [mode]: id };
    }
    return id;
  }

  function persistCurrentSession(mode?: InputMode) {
    const currentMode = mode ?? inputTab.value;
    const hasContent =
      (state.value?.report?.daily_cards?.length ?? 0) > 0 ||
      (state.value?.messages?.length ?? 0) > 0 ||
      !!state.value?.chat_intent;
    if (!hasContent) return;

    const id = ensureActiveSession(currentMode);
    const existing = getSessionRecord(id);
    const record = buildSessionRecord(id, currentMode, state.value, uiSnapshot(), existing);
    upsertSessionRecord(record);
    sessionHistory.value = listSessionHistory();
  }

  function openHistoryDrawer() {
    historyOpen.value = true;
  }

  function closeHistoryDrawer() {
    historyOpen.value = false;
  }

  function loadSession(id: string) {
    const rec = getSessionRecord(id);
    if (!rec) return;

    activeSessionByMode.value = { ...activeSessionByMode.value, [rec.mode]: rec.id };
    inputTab.value = rec.mode;
    state.value = rec.state ? JSON.parse(JSON.stringify(rec.state)) : null;
    error.value = null;
    demoReportActive.value = rec.ui?.demoReportActive ?? false;

    if (rec.ui?.currentCityKey) currentCityKey.value = rec.ui.currentCityKey;
    if (rec.ui?.selectedSpotIds) selectedSpotIds.value = [...rec.ui.selectedSpotIds];
    if (rec.ui?.planMode) planMode.value = rec.ui.planMode;
    if (rec.ui?.selectedDayIndex != null) selectedDayIndex.value = rec.ui.selectedDayIndex;

    if (rec.ui?.days?.length) {
      days.value = JSON.parse(JSON.stringify(rec.ui.days)) as TripDay[];
    } else if (state.value?.report?.daily_cards?.length) {
      syncDaysFromReport(state.value);
    } else {
      days.value = createDefaultEmptyDays();
      syncAllDays();
    }

    if (rec.ui?.formDraft) {
      lastFormDraft.value = JSON.parse(JSON.stringify(rec.ui.formDraft)) as FormDraftSnapshot;
      formDraftRestoreTick.value += 1;
    }

    showToast(`已恢复：${rec.title}`);
  }

  function deleteSession(id: string) {
    deleteSessionRecord(id);
    sessionHistory.value = listSessionHistory();
    const next = { ...activeSessionByMode.value };
    if (next.form === id) delete next.form;
    if (next.chat === id) delete next.chat;
    activeSessionByMode.value = next;
    showToast("已删除历史记录");
  }

  const hasReport = computed(
    () => (state.value?.report?.daily_cards?.length ?? 0) > 0 || demoReportActive.value,
  );

  const hasLiveReport = computed(
    () => (state.value?.report?.daily_cards?.length ?? 0) > 0,
  );

  const isChatMode = computed(() => inputTab.value === "chat");

  const chatCollecting = computed(
    () =>
      isChatMode.value &&
      !loading.value &&
      !hasLiveReport.value &&
      (state.value?.messages?.length ?? 0) > 0,
  );

  const chatGenerating = computed(() => isChatMode.value && loading.value);

  const showChatEmpty = computed(
    () =>
      isChatMode.value &&
      !loading.value &&
      !hasLiveReport.value &&
      (state.value?.messages?.length ?? 0) === 0,
  );

  function highlightReportPanel() {
    reportHighlight.value = true;
    window.setTimeout(() => {
      reportHighlight.value = false;
    }, 2000);
  }

  const currentCity = computed(() => cities.value.find((c) => c.key === currentCityKey.value));

  const activeDay = computed(() => days.value[selectedDayIndex.value]);

  function getSpotById(id: string): Spot | undefined {
    for (const city of cities.value) {
      const s = city.spots.find((x) => x.id === id);
      if (s) return s;
    }
    return undefined;
  }

  function syncDaySceneSpots(dayIdx: number) {
    const d = days.value[dayIdx];
    if (!d) return;
    d.sceneSpots = d.spotIds.map((id) => {
      const n = getSpotById(id)?.name ?? id;
      if (n.includes("洱海")) return "洱海廊道";
      if (n.includes("古城")) return "大理古城";
      if (n.includes("三塔")) return "崇圣寺三塔";
      return n.slice(0, 6);
    });
  }

  function syncAllDays() {
    days.value.forEach((_, i) => syncDaySceneSpots(i));
  }

  function rebuildDaysFromDates(startIso: string, endIso: string) {
    const start = parseDate(startIso);
    const end = parseDate(endIso);
    if (end < start) return;
    const prev = days.value;
    const next: TripDay[] = [];
    let i = 0;
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const m = d.getMonth() + 1;
      const dayNum = d.getDate();
      const wd = WEEKDAY_ZH[d.getDay()];
      const old = prev[i];
      next.push({
        dateShort: `${m}/${dayNum}`,
        weekday: wd,
        title: `${m}月${dayNum}日 · ${wd}`,
        weather: old?.weather ?? "",
        temp: old?.temp ?? "",
        reason: old?.reason ?? "",
        spotIds: old?.spotIds ? [...old.spotIds] : [],
        sceneSpots: old?.sceneSpots ? [...old.sceneSpots] : [],
      });
      i++;
    }
    days.value = next;
    if (selectedDayIndex.value >= days.value.length) {
      selectedDayIndex.value = Math.max(0, days.value.length - 1);
    }
    if (manualActiveDay.value >= days.value.length) {
      manualActiveDay.value = Math.max(0, days.value.length - 1);
    }
    if (planMode.value === "auto") autoAssignDays();
    else syncAllDays();
  }

  function autoAssignDays() {
    const city = currentCity.value;
    if (!city) return;
    const ids = city.spots
      .filter((s) => selectedSpotIds.value.includes(s.id))
      .map((s) => s.id);
    if (!ids.length) {
      days.value.forEach((d) => {
        d.spotIds = [];
        d.morningId = undefined;
        d.afternoonId = undefined;
        d.eveningId = undefined;
      });
      syncAllDays();
      return;
    }
    const plans = planAutoItineraryIds(ids, city, days.value.length);
    days.value.forEach((day, i) => {
      const plan = plans[i];
      if (!plan) {
        day.spotIds = [];
        day.morningId = undefined;
        day.afternoonId = undefined;
        day.eveningId = undefined;
        return;
      }
      day.spotIds = [...plan.spotIds];
      day.morningId = plan.morningId;
      day.afternoonId = plan.afternoonId;
      day.eveningId = plan.eveningId;
    });
    syncAllDays();
  }

  function setCityKey(key: string) {
    const city = cities.value.find((c) => c.key === key);
    if (!city) return;
    currentCityKey.value = key;
    selectedSpotIds.value = [];
    if (planMode.value === "auto") autoAssignDays();
    else syncAllDays();
  }

  function setPlanMode(mode: "auto" | "manual") {
    planMode.value = mode;
    if (editItinerary.value && mode === "manual") {
      editItinerary.value = false;
    }
    if (mode === "manual") {
      manualActiveDay.value = selectedDayIndex.value;
      syncAllDays();
    } else {
      autoAssignDays();
    }
  }

  function reset() {
    persistCurrentSession();
    activeSessionByMode.value = {
      ...activeSessionByMode.value,
      [inputTab.value]: newSessionId(),
    };
    state.value = null;
    error.value = null;
    selectedDayIndex.value = 0;
    manualActiveDay.value = 0;
    demoReportActive.value = false;
    editItinerary.value = false;
    toast.value = null;
    reportHighlight.value = false;
    planMode.value = "auto";
    currentCityKey.value = "dali";
    selectedSpotIds.value = [];
    days.value = createDefaultEmptyDays();
    syncAllDays();
  }

  function setCities(list: City[]) {
    if (list.length) cities.value = list;
  }

  function showToast(message: string) {
    toast.value = message;
    window.setTimeout(() => {
      if (toast.value === message) toast.value = null;
    }, 2200);
  }

  function applyPreviewReport() {
    demoReportActive.value = true;
    state.value = null;
    if (planMode.value === "auto") autoAssignDays();
    showToast("已更新行程预览（演示模式）");
  }

  function regenItinerary() {
    if (planMode.value !== "auto") return;
    autoAssignDays();
    selectedDayIndex.value = 0;
    showToast("已重新智能分配行程");
  }

  function toggleEditItinerary() {
    if (planMode.value !== "auto") return;
    editItinerary.value = !editItinerary.value;
  }

  const editItineraryLabel = computed(() =>
    editItinerary.value ? "✓ 完成编辑" : "✏️ 编辑行程",
  );

  const reportModeNote = computed(() => {
    if (!hasReport.value) return "";
    return planMode.value === "manual"
      ? "✋ 你在左侧指定每日景点 · 下方卡片同步展示你的安排"
      : "✨ AI 规划师已按区域/天气/游玩时长智能排期 · 可「编辑行程」微调";
  });

  const resultBadge = computed(() =>
    planMode.value === "manual"
      ? { text: "手动安排", bg: "#fef3c7", color: "#b45309" }
      : { text: "AI 推荐", bg: "#e0f2fe", color: "#0369a1" },
  );

  function removeDaySpot(dayIdx: number, spotId: string) {
    const d = days.value[dayIdx];
    if (!d) return;
    d.spotIds = d.spotIds.filter((id) => id !== spotId);
    syncDaySceneSpots(dayIdx);
  }

  function addDaySpot(dayIdx: number) {
    if (!editItinerary.value || planMode.value !== "auto") return;
    const city = currentCity.value;
    const d = days.value[dayIdx];
    if (!city || !d) return;
    const available = city.spots.filter(
      (s) => selectedSpotIds.value.includes(s.id) && !d.spotIds.includes(s.id),
    );
    if (!available.length) {
      showToast("请先在左侧多选更多景点");
      return;
    }
    d.spotIds.push(available[0].id);
    syncDaySceneSpots(dayIdx);
  }

  function setManualDaySpots(dayIdx: number, ids: string[]) {
    const d = days.value[dayIdx];
    if (!d) return;
    d.spotIds = [...ids];
    d.morningId = ids[0];
    d.afternoonId = ids[1];
    d.eveningId = ids[2];
    syncDaySceneSpots(dayIdx);
    if (dayIdx === selectedDayIndex.value) syncAllDays();
  }

  async function submitTrip(trip: TripFormPayload, { useApi = true } = {}) {
    if (!useApi) {
      applyPreviewReport();
      return;
    }
    loading.value = true;
    error.value = null;
    try {
      const res = await postPlan({ trip, state: state.value ?? undefined });
      state.value = res.state;
      demoReportActive.value = !res.state.report?.daily_cards?.length;
      selectedDayIndex.value = 0;
      if (res.state.report?.daily_cards?.length) {
        syncDaysFromReport(res.state);
        persistCurrentSession("form");
        showToast(`规划完成：${res.state.report.destination}`);
      } else if (res.state.phase === "collecting") {
        persistCurrentSession("form");
        const last = res.state.messages.at(-1);
        showToast(last?.content ?? "请补充行程信息");
      } else {
        showToast("规划已提交，报告生成中…");
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
      showToast(`请求失败：${error.value}`);
    } finally {
      loading.value = false;
    }
  }

  function resolveSpotIdsFromNames(names: string[]): string[] {
    const ids: string[] = [];
    for (const name of names) {
      for (const city of cities.value) {
        const spot = city.spots.find((s) => s.name === name);
        if (spot && !ids.includes(spot.id)) {
          ids.push(spot.id);
          break;
        }
      }
    }
    return ids;
  }

  function sceneLabelsFromSpotNames(names: string[]): string[] {
    return names.map((name) => {
      if (name.includes("洱海")) return "洱海廊道";
      if (name.includes("古城")) return "大理古城";
      if (name.includes("三塔")) return "崇圣寺三塔";
      return name.length > 6 ? name.slice(0, 6) : name;
    });
  }

  function syncDaysFromReport(apiState: PlanningState) {
    const cards = apiState.report?.daily_cards;
    if (!cards?.length) return;
    days.value = cards.map((card) => {
      const d = parseDate(card.date);
      const m = d.getMonth() + 1;
      const dayNum = d.getDate();
      const wd = WEEKDAY_ZH[d.getDay()];
      const w = card.weather;
      const temp = w
        ? `${weatherIcon(String(w.condition))} ${w.temp_min}–${w.temp_max}°C`
        : "—";
      const rain = w?.rain_prob != null ? ` · 降水 ${Math.round(w.rain_prob)}%` : "";
      const weatherStr = w
        ? `${weatherIcon(String(w.condition))} ${w.condition} ${w.temp_min}–${w.temp_max}°C${rain}`
        : "";
      const spotNames = card.spot_names ?? [];
      const spotIds = resolveSpotIdsFromNames(spotNames);
      const resolveId = (name?: string | null) =>
        name ? resolveSpotIdsFromNames([name])[0] : undefined;
      return {
        dateShort: `${m}/${dayNum}`,
        weekday: wd,
        title: `${m}月${dayNum}日 · ${wd}`,
        weather: weatherStr,
        temp,
        reason:
          card.outfit?.recommendation_reason ||
          card.outfit?.outfit_summary ||
          "根据当日天气与景点推荐穿搭。",
        spotIds,
        sceneSpots: sceneLabelsFromSpotNames(spotNames),
        morningId: resolveId(card.morning),
        afternoonId: resolveId(card.afternoon),
        eveningId: resolveId(card.evening),
      };
    });
  }

  async function sendChat(message: string, { useApi = true } = {}) {
    const text = message.trim();
    if (!text) return;
    if (!useApi) {
      showToast("对话已记录（演示模式）");
      return;
    }
    loading.value = true;
    error.value = null;
    try {
      const res = await postPlan({ message: text, state: state.value ?? undefined });
      state.value = res.state;
      demoReportActive.value = !res.state.report?.daily_cards?.length;
      if (res.state.report?.daily_cards?.length) {
        syncDaysFromReport(res.state);
        selectedDayIndex.value = 0;
        persistCurrentSession("chat");
        showToast("行程报告已生成");
      } else {
        persistCurrentSession("chat");
        const last = res.state.messages.at(-1);
        showToast(last?.content ?? "已收到，请继续补充信息");
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
      showToast(`请求失败：${error.value}`);
    } finally {
      loading.value = false;
    }
  }

  syncAllDays();

  return {
    state,
    cities,
    loading,
    error,
    selectedDayIndex,
    manualActiveDay,
    inputTab,
    reportHighlight,
    isChatMode,
    chatCollecting,
    chatGenerating,
    showChatEmpty,
    hasLiveReport,
    demoReportActive,
    hasReport,
    editItinerary,
    toast,
    planMode,
    currentCityKey,
    selectedSpotIds,
    days,
    currentCity,
    activeDay,
    editItineraryLabel,
    reportModeNote,
    resultBadge,
    reset,
    setCities,
    setCityKey,
    setPlanMode,
    rebuildDaysFromDates,
    autoAssignDays,
    syncAllDays,
    getSpotById,
    shortSpotLabel,
    removeDaySpot,
    addDaySpot,
    setManualDaySpots,
    applyPreviewReport,
    regenItinerary,
    toggleEditItinerary,
    submitTrip,
    sendChat,
    highlightReportPanel,
    showToast,
    historyOpen,
    sessionHistory,
    activeSessionId,
    openHistoryDrawer,
    closeHistoryDrawer,
    loadSession,
    deleteSession,
    persistCurrentSession,
    setFormDraft,
    formDraftRestoreTick,
    lastFormDraft,
  };
});
