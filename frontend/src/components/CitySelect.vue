<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import type { City } from "@/api/types";
import { groupCitiesByInitial } from "@/data/cities";

const props = defineProps<{
  cities: City[];
  modelValue: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [key: string];
}>();

const open = ref(false);
const search = ref("");
const root = ref<HTMLElement | null>(null);

const selectedCity = computed(() => props.cities.find((c) => c.key === props.modelValue));

const groups = computed(() => {
  const q = search.value.trim().toLowerCase();
  const filtered = q
    ? props.cities.filter(
        (c) => c.name.toLowerCase().includes(q) || c.key.toLowerCase().includes(q),
      )
    : props.cities;
  return groupCitiesByInitial(filtered);
});

function toggleOpen() {
  open.value = !open.value;
  if (open.value) search.value = "";
}

function pickCity(key: string) {
  emit("update:modelValue", key);
  open.value = false;
}

function onDocClick(e: MouseEvent) {
  if (!open.value || !root.value) return;
  if (!root.value.contains(e.target as Node)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocClick));
onUnmounted(() => document.removeEventListener("click", onDocClick));
</script>

<template>
  <div ref="root" class="city-select-wrap" :class="{ 'dropdown-open': open }">
    <label class="field-label">目的地（城市）</label>
    <div class="multiselect city-multiselect" :class="{ open }">
      <button type="button" class="multiselect-trigger city-trigger" @click.stop="toggleOpen">
        <span class="trigger-text">{{ selectedCity?.name ?? "请选择城市…" }}</span>
        <span class="multiselect-chevron">▾</span>
      </button>
      <div class="multiselect-panel city-panel">
        <div class="multiselect-search-wrap">
          <span class="search-ico">🔍</span>
          <input
            v-model="search"
            type="search"
            class="multiselect-search"
            placeholder="搜索热门城市…"
            @click.stop
          />
        </div>
        <div class="city-options-scroll">
          <template v-for="g in groups" :key="g.letter">
            <div class="city-letter">{{ g.letter }}</div>
            <button
              v-for="c in g.items"
              :key="c.key"
              type="button"
              class="city-option"
              :class="{ active: modelValue === c.key }"
              @click.stop="pickCity(c.key)"
            >
              <span class="city-option-name">{{ c.name }}</span>
              <span v-if="modelValue === c.key" class="city-check">✓</span>
            </button>
          </template>
          <p v-if="!groups.length" class="multiselect-empty">无匹配城市</p>
        </div>
      </div>
    </div>
  </div>
</template>
