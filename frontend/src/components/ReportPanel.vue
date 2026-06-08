<script setup lang="ts">
import { computed, ref } from "vue";
import MagazineCardInteractive from "./MagazineCardInteractive.vue";
import { USE_API } from "@/config";
import { usePlanningStore } from "@/stores/planning";

const store = usePlanningStore();
const debugOpen = ref(false);
const xhsDebugOpen = ref(false);

const report = computed(() => store.state?.report ?? null);
const cards = computed(() => report.value?.daily_cards ?? []);
const selectedCard = computed(() => cards.value[store.selectedDayIndex] ?? null);
const showDemo = computed(() => store.demoReportActive && !report.value?.daily_cards?.length);
const showLiveReport = computed(() => (report.value?.daily_cards?.length ?? 0) > 0);

const shoppingTrace = computed(() =>
  (store.state?.trace ?? []).filter((t) => t.agent === "Shopping"),
);

const taobaoKeywords = computed(() => {
  const rows: { keyword: string; detail: string; level: string }[] = [];
  for (const event of shoppingTrace.value) {
    const msg = event.message;
    if (msg.startsWith("Taobao API:")) continue;
    const hitMatch = msg.match(/via「(.+?)」/);
    const missMatch = msg.match(/0 hits for「(.+?)」/);
    const keyword = hitMatch?.[1] ?? missMatch?.[1];
    if (!keyword) continue;
    if (rows.some((r) => r.detail === msg)) continue;
    rows.push({ keyword, detail: msg, level: event.level ?? "info" });
  }
  return rows;
});

const xhsQueryDebug = computed(() => store.state?.xhs_query_debug ?? []);

const badgeStyle = computed(() =>
  showDemo.value
    ? store.resultBadge
    : { text: "AI 推荐", bg: "#e0f2fe", color: "#0369a1" },
);

function onDayClick(index: number, e: MouseEvent) {
  const t = e.target as HTMLElement;
  if (t.closest(".chip-rm") || t.closest(".day-add-spot")) return;
  store.selectedDayIndex = index;
}
</script>

<template>
  <section class="report-panel">
    <div v-if="store.toast" class="toast-banner">{{ store.toast }}</div>

    <div class="report-head">
      <h2>行程报告</h2>
      <div v-if="store.hasReport" class="report-actions">
        <button
          v-show="store.planMode === 'auto' && showDemo"
          type="button"
          class="btn-ghost"
          @click="store.regenItinerary()"
        >
          ↻ 重新智能分配
        </button>
        <button
          v-show="store.planMode === 'auto' && showDemo"
          type="button"
          class="btn-ghost"
          :class="{ active: store.editItinerary }"
          @click="store.toggleEditItinerary()"
        >
          {{ store.editItineraryLabel }}
        </button>
        <button type="button" class="btn-ghost" @click="store.reset()">重新规划</button>
      </div>
    </div>

    <div v-if="store.error && !store.hasReport" class="error-banner">{{ store.error }}</div>

    <div v-if="!store.hasReport" class="report-empty">
      <div class="report-empty-card">
        <div class="report-empty-icon" aria-hidden="true">🗺️</div>
        <h3 class="report-empty-title">尚未生成行程报告</h3>
        <p class="report-empty-desc">
          请在左侧填写目的地、出行日期、景点与风格偏好，点击
          <strong>「开始规划穿搭」</strong>
          后，AI 将为你生成每日行程分配、穿搭推荐与购物清单。
        </p>
        <ul class="report-empty-steps">
          <li><span>1</span>选择目的地与景点</li>
          <li><span>2</span>设置风格与预算</li>
          <li><span>3</span>一键生成专属报告</li>
        </ul>
      </div>
    </div>

    <template v-else>
      <p class="itinerary-edit-hint" :class="{ visible: store.editItinerary && showDemo }">
        编辑模式：点击各日卡片上的 × 删除景点，或点 + 添加
      </p>

      <div v-if="store.error" class="error-banner">{{ store.error }}</div>

      <p v-if="store.reportModeNote" class="report-mode-note">{{ store.reportModeNote }}</p>

      <div class="itinerary-result">
        <div class="itinerary-result-head">
          <span class="title">行程分配</span>
          <span
            class="auto-badge"
            :style="{ background: badgeStyle.bg, color: badgeStyle.color }"
          >
            {{ badgeStyle.text }}
          </span>
        </div>
        <p v-if="store.days.length > 5" class="day-strip-hint">
          ← 在下方区域内滑动查看全部 {{ store.days.length }} 天 →
        </p>
        <div class="day-strip-scroll">
          <div class="weather-strip" :class="{ editing: store.editItinerary && showDemo }">
            <div
              v-for="(d, i) in store.days"
              :key="i"
              class="weather-mini"
              :class="{ active: store.selectedDayIndex === i }"
              @click="onDayClick(i, $event)"
            >
              <div class="date">{{ d.dateShort }}</div>
              <div class="wd">{{ d.weekday }}</div>
              <div v-if="d.temp" class="temp">{{ d.temp }}</div>
              <div class="day-spot-row">
                <template v-if="d.morningId || d.afternoonId || d.eveningId">
                  <span v-if="d.morningId" class="spot-chip-sm slot-am">
                    上午 {{ store.shortSpotLabel(store.getSpotById(d.morningId)?.name ?? d.morningId) }}
                  </span>
                  <span v-if="d.afternoonId" class="spot-chip-sm slot-pm">
                    下午 {{ store.shortSpotLabel(store.getSpotById(d.afternoonId)?.name ?? d.afternoonId) }}
                  </span>
                  <span v-if="d.eveningId" class="spot-chip-sm slot-ev">
                    晚间 {{ store.shortSpotLabel(store.getSpotById(d.eveningId)?.name ?? d.eveningId) }}
                  </span>
                </template>
                <template v-else>
                  <span v-for="sid in d.spotIds" :key="sid" class="spot-chip-sm">
                    {{ store.shortSpotLabel(store.getSpotById(sid)?.name ?? sid) }}
                    <button
                      v-if="store.editItinerary && showDemo"
                      type="button"
                      class="chip-rm"
                      @click.stop="store.removeDaySpot(i, sid)"
                    >
                      ×
                    </button>
                  </span>
                </template>
                <button
                  v-if="store.editItinerary && showDemo"
                  type="button"
                  class="day-add-spot"
                  @click.stop="store.addDaySpot(i)"
                >
                  + 添加
                </button>
                <span
                  v-if="!d.spotIds.length && !d.morningId && !d.afternoonId && !d.eveningId"
                  class="spot-chip-sm spot-chip-placeholder"
                >
                  待分配
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <MagazineCardInteractive
        v-if="showDemo"
        :demo-day-index="store.selectedDayIndex"
      />
      <MagazineCardInteractive
        v-else-if="selectedCard"
        :card="selectedCard"
        :demo-day-index="store.selectedDayIndex"
        :destination="report?.destination"
      />

      <p v-if="!USE_API" class="footer-note demo-footer">
        演示模式（VITE_USE_API=false）· 填写表单仅本地预览
      </p>
      <p v-else-if="showDemo && !store.state?.report" class="footer-note demo-footer">
        填写左侧表单并点击「开始规划穿搭」连接后端生成报告
      </p>
      <p v-else-if="report?.disclaimer" class="footer-note">{{ report.disclaimer }}</p>

      <details
        v-if="USE_API && showLiveReport && xhsQueryDebug.length"
        class="shopping-debug query-debug"
        :open="xhsDebugOpen"
        @toggle="xhsDebugOpen = ($event.target as HTMLDetailsElement).open"
      >
        <summary>小红书搜索 Query Debug（{{ xhsQueryDebug.length }} 条）</summary>
        <ul>
          <li v-for="(row, i) in xhsQueryDebug" :key="i">
            <strong>{{ row.trip_date }} · {{ row.spot }}</strong>
            <span class="shopping-debug-detail">搜索词：{{ row.final_query }}</span>
            <span class="shopping-debug-detail">
              规则：
              <span v-for="(tok, j) in row.base_tokens" :key="j">
                {{ tok.rule }}「{{ tok.token }}」<span v-if="j < row.base_tokens.length - 1"> · </span>
              </span>
            </span>
            <span v-if="row.expanded_queries.length" class="shopping-debug-detail">
              LLM 扩展：{{ row.expanded_queries.join("；") }}
            </span>
            <span class="shopping-debug-detail">
              雷点过滤 {{ row.filtered_avoid }} · 非穿搭 {{ row.filtered_non_outfit }} ·
              低赞 {{ row.filtered_low_likes }} · 保留 {{ row.notes_kept }} 条
            </span>
          </li>
        </ul>
        <p class="shopping-debug-hint">
          由 Outfit Query Compiler 生成：代码规则编译搜索词，结果按穿搭雷点规则过滤。
        </p>
      </details>

      <details
        v-if="USE_API && showLiveReport && taobaoKeywords.length"
        class="shopping-debug"
        :open="debugOpen"
        @toggle="debugOpen = ($event.target as HTMLDetailsElement).open"
      >
        <summary>淘宝搜索关键词（{{ taobaoKeywords.length }} 条）</summary>
        <ul>
          <li v-for="(row, i) in taobaoKeywords" :key="i" :class="row.level">
            <strong>{{ row.keyword }}</strong>
            <span class="shopping-debug-detail">{{ row.detail }}</span>
          </li>
        </ul>
        <p class="shopping-debug-hint">淘宝 API 由后端调用，浏览器 Network 里只能看到一条 <code>plan</code> 请求。</p>
      </details>
    </template>
  </section>
</template>
