<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { AVOID_OPTIONS } from "@/data/formOptions";

const props = defineProps<{
  modelValue: string[];
}>();

const emit = defineEmits<{
  "update:modelValue": [labels: string[]];
}>();

const open = ref(false);
const search = ref("");
const customText = ref("");
const root = ref<HTMLElement | null>(null);

const presetLabels = new Set(AVOID_OPTIONS.map((o) => o.label));

const filteredOptions = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return AVOID_OPTIONS;
  return AVOID_OPTIONS.filter((o) => o.label.toLowerCase().includes(q));
});

const customSelected = computed(() =>
  props.modelValue.filter((l) => !presetLabels.has(l)),
);

const triggerText = computed(() => {
  const n = props.modelValue.length;
  if (!n) return "选择或输入避雷项…";
  if (n <= 2) return props.modelValue.join("、");
  return `${props.modelValue.slice(0, 2).join("、")} 等 ${n} 项`;
});

function toggleOpen() {
  open.value = !open.value;
  if (open.value) {
    search.value = "";
    customText.value = "";
  }
}

function isSelected(label: string) {
  return props.modelValue.includes(label);
}

function toggleLabel(label: string) {
  const set = new Set(props.modelValue);
  if (set.has(label)) set.delete(label);
  else set.add(label);
  emit("update:modelValue", [...set]);
}

function removeLabel(label: string) {
  emit(
    "update:modelValue",
    props.modelValue.filter((x) => x !== label),
  );
}

function addCustom() {
  const text = customText.value.trim();
  if (!text) return;
  if (!props.modelValue.includes(text)) {
    emit("update:modelValue", [...props.modelValue, text]);
  }
  customText.value = "";
}

function onCustomKeydown(e: KeyboardEvent) {
  if (e.key === "Enter") {
    e.preventDefault();
    addCustom();
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
  <div ref="root" class="avoid-section" :class="{ 'dropdown-open': open }">
    <label class="field-label label-with-help">
      穿搭雷点
      <span class="help-ico" title="不希望推荐的单品或风格">?</span>
    </label>
    <p class="spots-hint">先选常见项；没有合适的可在下拉底部自行输入</p>

    <div v-if="modelValue.length" class="spot-chips-selected">
      <span
        v-for="label in modelValue"
        :key="label"
        class="spot-chip avoid-chip"
        :class="{ custom: !presetLabels.has(label) }"
      >
        {{ label }}
        <button type="button" class="chip-x" aria-label="移除" @click.stop="removeLabel(label)">
          ×
        </button>
      </span>
    </div>

    <div class="multiselect" :class="{ open }">
      <button
        type="button"
        class="multiselect-trigger"
        :class="{ 'placeholder-style': !modelValue.length }"
        @click.stop="toggleOpen"
      >
        <span class="trigger-text">{{ triggerText }}</span>
        <span class="multiselect-chevron">▾</span>
      </button>
      <div class="multiselect-panel" @click.stop>
        <div class="multiselect-search-wrap">
          <span class="search-ico">🔍</span>
          <input
            v-model="search"
            type="search"
            class="multiselect-search"
            placeholder="搜索常见雷点…"
            @click.stop
          />
        </div>
        <div class="multiselect-options">
          <label
            v-for="o in filteredOptions"
            :key="o.id"
            class="multiselect-option avoid-option"
            @click.stop
          >
            <input
              type="checkbox"
              :checked="isSelected(o.label)"
              @change="toggleLabel(o.label)"
            />
            <span class="opt-main">
              <span class="opt-name">{{ o.label }}</span>
            </span>
          </label>
          <p v-if="!filteredOptions.length" class="multiselect-empty">无匹配项，可在下方自定义</p>
        </div>
        <div class="avoid-custom-row" @click.stop>
          <input
            v-model="customText"
            type="text"
            class="avoid-custom-input"
            placeholder="自定义雷点，回车添加"
            @keydown="onCustomKeydown"
          />
          <button type="button" class="avoid-custom-add" @click="addCustom">添加</button>
        </div>
      </div>
    </div>

    <div v-if="customSelected.length" class="selected-count">
      含 {{ customSelected.length }} 项自定义
    </div>
  </div>
</template>
