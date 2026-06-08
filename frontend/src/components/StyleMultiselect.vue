<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { STYLE_OPTIONS } from "@/data/formOptions";

const props = defineProps<{
  modelValue: string[];
}>();

const emit = defineEmits<{
  "update:modelValue": [styles: string[]];
}>();

const open = ref(false);
const search = ref("");
const root = ref<HTMLElement | null>(null);

const filteredStyles = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return STYLE_OPTIONS;
  return STYLE_OPTIONS.filter((s) => s.toLowerCase().includes(q));
});

function toggleOpen() {
  open.value = !open.value;
  if (open.value) search.value = "";
}

function removeStyle(style: string) {
  emit(
    "update:modelValue",
    props.modelValue.filter((s) => s !== style),
  );
}

function toggleStyle(style: string) {
  const set = new Set(props.modelValue);
  if (set.has(style)) {
    set.delete(style);
    emit("update:modelValue", [...set]);
  } else {
    set.add(style);
    emit("update:modelValue", [...set]);
  }
}

function onDocClick(e: MouseEvent) {
  if (!open.value || !root.value) return;
  if (!root.value.contains(e.target as Node)) open.value = false;
}

onMounted(() => document.addEventListener("click", onDocClick));
onUnmounted(() => document.removeEventListener("click", onDocClick));
</script>

<template>
  <div ref="root" class="style-section" :class="{ 'dropdown-open': open }">
    <label class="field-label">风格标签</label>
    <p class="spots-hint">可多选 · 影响 AI 穿搭推荐方向</p>

    <div v-if="modelValue.length" class="spot-chips-selected">
      <span v-for="s in modelValue" :key="s" class="spot-chip style-chip">
        {{ s }}
        <button
          type="button"
          class="chip-x"
          aria-label="移除"
          @click.stop="removeStyle(s)"
        >
          ×
        </button>
      </span>
    </div>

    <div class="multiselect" :class="{ open }">
      <button type="button" class="multiselect-trigger" @click.stop="toggleOpen">
        <span>+ 选择 / 管理风格</span>
        <span class="multiselect-chevron">▾</span>
      </button>
      <div class="multiselect-panel" @click.stop>
        <div class="multiselect-search-wrap">
          <span class="search-ico">🔍</span>
          <input
            v-model="search"
            type="search"
            class="multiselect-search"
            placeholder="搜索风格…"
            @click.stop
          />
        </div>
        <div class="multiselect-options style-options">
          <label
            v-for="s in filteredStyles"
            :key="s"
            class="multiselect-option style-option"
            @click.stop
          >
            <input
              type="checkbox"
              :checked="modelValue.includes(s)"
              @change="toggleStyle(s)"
            />
            <span class="opt-main">
              <span class="opt-name">{{ s }}</span>
            </span>
          </label>
          <p v-if="!filteredStyles.length" class="multiselect-empty">无匹配风格</p>
        </div>
      </div>
    </div>
    <div class="selected-count">已选 {{ modelValue.length }} 个风格</div>
  </div>
</template>
