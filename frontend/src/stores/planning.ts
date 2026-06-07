import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { postPlan } from "@/api/client";
import type { City, PlanningState, Spot, TripFormPayload } from "@/api/types";
import { STATIC_CITIES } from "@/data/cities";
import { parseDate, weatherIcon } from "@/utils/format";
import { planAutoItineraryIds } from "@/utils/itinerary";

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

const DEFAULT_DAYS: TripDay[] = [
  {
    dateShort: "6/5",
    weekday: "周五",
    title: "6月5日 · 周五",
    weather: "🌧 雨 16–27°C · 降水 60%",
    temp: "🌧 16–27°C",
    reason:
      "洱海骑行需要防风防泼水的薄外套，内搭白色 T 恤 + 牛仔裤经典耐看；卡其色系与湖光山色呼应，拍照出片。",
    spotIds: ["erhai", "gucheng"],
    sceneSpots: ["洱海廊道", "大理古城"],
  },
  {
    dateShort: "6/6",
    weekday: "周六",
    title: "6月6日 · 周六",
    weather: "☀ 晴 18–28°C · 降水 10%",
    temp: "☀ 18–28°C",
    reason: "三塔观光以轻便透气为主，亚麻衬衫 + 阔腿裤舒适又上镜。",
    spotIds: ["santa", "gucheng"],
    sceneSpots: ["崇圣寺三塔", "大理古城"],
  },
  {
    dateShort: "6/7",
    weekday: "周日",
    title: "6月7日 · 周日",
    weather: "⛅ 多云 17–26°C · 降水 20%",
    temp: "⛅ 17–26°C",
    reason: "返程日选易打理的速干材质，一件可收纳的风衣应对早晚温差。",
    spotIds: ["erhai"],
    sceneSpots: ["洱海廊道"],
  },
];

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
  const demoReportActive = ref(true);
  const editItinerary = ref(false);
  const toast = ref<string | null>(null);
  const planMode = ref<"auto" | "manual">("auto");
  const currentCityKey = ref("dali");
  const selectedSpotIds = ref<string[]>([...STATIC_CITIES[0].default_spot_ids]);
  const days = ref<TripDay[]>([...DEFAULT_DAYS]);

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
        weather: old?.weather ?? "⛅ 多云 18–26°C · 降水 20%",
        temp: old?.temp ?? "⛅ 18–26°C",
        reason: old?.reason ?? "根据当日天气与景点活动，建议舒适分层穿搭。",
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
    selectedSpotIds.value = [...city.default_spot_ids];
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
    state.value = null;
    error.value = null;
    selectedDayIndex.value = 0;
    manualActiveDay.value = 0;
    demoReportActive.value = true;
    editItinerary.value = false;
    toast.value = null;
    planMode.value = "auto";
    currentCityKey.value = "dali";
    selectedSpotIds.value = [...STATIC_CITIES[0].default_spot_ids];
    days.value = [...DEFAULT_DAYS];
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

  const reportModeNote = computed(() =>
    planMode.value === "manual"
      ? "✋ 你在左侧指定每日景点 · 下方卡片同步展示你的安排"
      : "✨ 系统已按所选景点分配每日上午/下午 · 同一景点可跨多天 · 可「编辑行程」微调",
  );

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
        showToast(`规划完成：${res.state.report.destination}`);
      } else if (res.state.phase === "collecting") {
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
        showToast("已更新行程报告");
      } else {
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
    demoReportActive,
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
    showToast,
  };
});
