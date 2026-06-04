<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import type { Spot } from "@/api/types";

const props = defineProps<{
  spots: Spot[];
  modelValue: string[];
  cityName: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [ids: string[]];
}>();

const open = ref(false);
const search = ref("");
const root = ref<HTMLElement | null>(null);

const selectedSpots = computed(() => {
  const set = new Set(props.modelValue);
  return props.spots.filter((s) => set.has(s.id));
});

const filteredSpots = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return props.spots;
  return props.spots.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.tag.toLowerCase().includes(q) ||
      s.emoji.includes(q),
  );
});

function toggleOpen() {
  open.value = !open.value;
  if (open.value) search.value = "";
}

function removeSpot(id: string) {
  emit(
    "update:modelValue",
    props.modelValue.filter((x) => x !== id),
  );
}

function toggleSpot(id: string) {
  const set = new Set(props.modelValue);
  if (set.has(id)) set.delete(id);
  else set.add(id);
  emit("update:modelValue", [...set]);
}

function onDocClick(e: MouseEvent) {
  if (!open.value || !root.value) return;
  if (!root.value.contains(e.target as Node)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocClick));
onUnmounted(() => document.removeEventListener("click", onDocClick));
</script>

<template>
  <div ref="root" class="spots-section" :class="{ 'dropdown-open': open }">
    <label class="field-label spot-label">选择景点</label>
    <p class="spots-hint">已选「{{ cityName }}」· 下拉多选 · 影响 AI 背景</p>
    <div class="spot-chips-selected">
      <span v-for="s in selectedSpots" :key="s.id" class="spot-chip">
        {{ s.emoji }} {{ s.name }}
        <button type="button" class="chip-x" aria-label="移除" @click.stop="removeSpot(s.id)">×</button>
      </span>
    </div>
    <div class="multiselect" :class="{ open }">
      <button type="button" class="multiselect-trigger" @click.stop="toggleOpen">
        <span>+ 选择 / 管理景点</span>
        <span class="multiselect-chevron">▾</span>
      </button>
      <div class="multiselect-panel">
        <div class="multiselect-search-wrap">
          <span class="search-ico">🔍</span>
          <input
            v-model="search"
            type="search"
            class="multiselect-search"
            placeholder="搜索景点…"
            @click.stop
          />
        </div>
        <div class="multiselect-options">
          <label
            v-for="s in filteredSpots"
            :key="s.id"
            class="multiselect-option"
            @click.stop
          >
            <input
              type="checkbox"
              :checked="modelValue.includes(s.id)"
              @change="toggleSpot(s.id)"
            />
            <span class="opt-thumb" aria-hidden="true">{{ s.emoji }}</span>
            <span class="opt-main">
              <span class="opt-name">{{ s.name }}</span>
              <span class="opt-tag">{{ s.tag }}</span>
            </span>
          </label>
          <p v-if="!filteredSpots.length" class="multiselect-empty">无匹配景点</p>
        </div>
      </div>
    </div>
    <div class="selected-count">已选 {{ modelValue.length }} 个景点</div>
  </div>
</template>
