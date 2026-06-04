<script setup lang="ts">
import { computed } from "vue";
import MagazineCardInteractive from "./MagazineCardInteractive.vue";
import { USE_API } from "@/config";
import { usePlanningStore } from "@/stores/planning";

const store = usePlanningStore();

const report = computed(() => store.state?.report ?? null);
const cards = computed(() => report.value?.daily_cards ?? []);
const selectedCard = computed(() => cards.value[store.selectedDayIndex] ?? null);
const showDemo = computed(
  () => store.demoReportActive || !report.value?.daily_cards?.length,
);

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
      <div class="report-actions">
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

    <p class="itinerary-edit-hint" :class="{ visible: store.editItinerary && showDemo }">
      编辑模式：点击各日卡片上的 × 删除景点，或点 + 添加
    </p>

    <div v-if="store.error" class="error-banner">{{ store.error }}</div>

    <p class="report-mode-note">{{ store.reportModeNote }}</p>

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
            <div class="temp">{{ d.temp }}</div>
            <div class="day-spot-row">
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
              <button
                v-if="store.editItinerary && showDemo"
                type="button"
                class="day-add-spot"
                @click.stop="store.addDaySpot(i)"
              >
                + 添加
              </button>
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
    <p v-else-if="store.demoReportActive && !store.state?.report" class="footer-note demo-footer">
      填写左侧表单并点击「开始规划穿搭」连接后端生成报告
    </p>
    <p v-else-if="report?.disclaimer" class="footer-note">{{ report.disclaimer }}</p>
  </section>
</template>
