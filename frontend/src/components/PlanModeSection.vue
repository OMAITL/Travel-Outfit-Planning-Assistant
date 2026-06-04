<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { usePlanningStore } from "@/stores/planning";

const store = usePlanningStore();
const manualDropdownOpen = ref(false);
const manualRoot = ref<HTMLElement | null>(null);

const manualDay = computed(() => store.days[store.manualActiveDay]);

const manualPool = computed(() => {
  const city = store.currentCity;
  if (!city) return [];
  return city.spots.filter((s) => store.selectedSpotIds.includes(s.id));
});

const manualSummary = computed(() => {
  const d = manualDay.value;
  if (!d) return "";
  const names = d.spotIds.map(
    (id) => store.shortSpotLabel(store.getSpotById(id)?.name ?? id),
  );
  return names.length ? `当天已选：${names.join("、")}` : "当天尚未指定景点";
});

const manualTriggerText = computed(() => {
  const n = manualDay.value?.spotIds.length ?? 0;
  return n ? `已选 ${n} 个景点` : "选择当天景点…";
});

function toggleManualDropdown() {
  manualDropdownOpen.value = !manualDropdownOpen.value;
}

function toggleManualSpot(id: string) {
  const d = manualDay.value;
  if (!d) return;
  const set = new Set(d.spotIds);
  if (set.has(id)) set.delete(id);
  else set.add(id);
  store.setManualDaySpots(store.manualActiveDay, [...set]);
}

watch(
  () => store.planMode,
  () => {
    manualDropdownOpen.value = false;
  },
);

function onDocClick(e: MouseEvent) {
  if (!manualDropdownOpen.value || !manualRoot.value) return;
  if (!manualRoot.value.contains(e.target as Node)) manualDropdownOpen.value = false;
}

onMounted(() => document.addEventListener("click", onDocClick));
onUnmounted(() => document.removeEventListener("click", onDocClick));
</script>

<template>
  <div class="plan-mode-block">
    <label class="field-label">行程安排</label>
    <div class="plan-mode-tabs">
      <button
        type="button"
        :class="{ active: store.planMode === 'manual' }"
        @click="store.setPlanMode('manual')"
      >
        ✋ 我自己安排
      </button>
      <button
        type="button"
        :class="{ active: store.planMode === 'auto' }"
        @click="store.setPlanMode('auto')"
      >
        ✨ 系统智能分配
      </button>
    </div>

    <div v-if="store.planMode === 'manual'" class="plan-block">
      <p v-if="store.days.length > 5" class="day-strip-hint">← 左右滑动切换日期 →</p>
      <div class="manual-day-nav">
        <button
          v-for="(d, i) in store.days"
          :key="i"
          type="button"
          :class="{
            active: store.manualActiveDay === i,
            'has-spots': d.spotIds.length > 0,
          }"
          @click="
            store.manualActiveDay = i;
            store.selectedDayIndex = i;
          "
        >
          {{ d.dateShort }}<span class="nav-wd">{{ d.weekday }}</span>
        </button>
      </div>
      <div ref="manualRoot" class="manual-day-editor">
        <div v-if="manualDay" class="manual-editor-label">
          {{ manualDay.dateShort }} {{ manualDay.weekday }}
        </div>
        <div v-if="!manualPool.length" class="manual-empty">请先在上方选择景点</div>
        <template v-else>
          <div class="multiselect" :class="{ open: manualDropdownOpen }">
            <button
              type="button"
              class="multiselect-trigger"
              :class="{ 'placeholder-style': !manualDay?.spotIds.length }"
              @click="toggleManualDropdown"
            >
              <span class="trigger-text">{{ manualTriggerText }}</span>
              <span class="multiselect-chevron">▾</span>
            </button>
            <div v-show="manualDropdownOpen" class="multiselect-panel manual-panel">
              <div class="multiselect-options">
                <label
                  v-for="s in manualPool"
                  :key="s.id"
                  class="multiselect-option"
                >
                  <input
                    type="checkbox"
                    :checked="manualDay?.spotIds.includes(s.id)"
                    @change="toggleManualSpot(s.id)"
                  />
                  <span class="opt-thumb">{{ s.emoji }}</span>
                  <span class="opt-main">
                    <span class="opt-name">{{ s.name }}</span>
                    <span class="opt-tag">{{ s.tag }}</span>
                  </span>
                </label>
              </div>
            </div>
          </div>
          <div class="manual-day-summary">{{ manualSummary }}</div>
        </template>
      </div>
    </div>

    <div v-else class="plan-block plan-block-auto">
      <p class="plan-hint plan-hint-compact plan-hint-auto">
        系统将根据所选景点自动排期
      </p>
    </div>
  </div>
</template>
