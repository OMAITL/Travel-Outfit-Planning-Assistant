<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { usePlanningStore } from "@/stores/planning";
import "@/assets/tryon.css";

type SourceMode = "virtual" | "photo";
type PoolCat = "all" | "top" | "bottom" | "shoes" | "acc";

interface PoolItem {
  id: number;
  cat: Exclude<PoolCat, "all">;
  icon: string;
  name: string;
  price: string;
  inTryon: boolean;
}

const CAT_LABELS: Record<PoolCat, string> = {
  all: "全部",
  top: "上装",
  bottom: "下装",
  shoes: "鞋",
  acc: "配饰",
};

const store = usePlanningStore();

const sourceMode = ref<SourceMode>("virtual");
const modelAvatar = ref("👩");
const bodyHeight = ref(169);
const bodyWeight = ref(63);
const footShoe = ref("38");
const selectedDayIndex = ref(0);
const selectedSpotId = ref("");
const poolFilter = ref<PoolCat>("all");
const srcPopoverOpen = ref(false);
const genStatus = ref("待生成");
const generating = ref(false);
const progressWidth = ref(0);
const showDone = ref(false);

const pool = ref<PoolItem[]>([
  { id: 1, cat: "top", icon: "👕", name: "防晒衬衫", price: "¥59.90", inTryon: true },
  { id: 2, cat: "top", icon: "🧥", name: "防水风衣", price: "¥168", inTryon: true },
  { id: 3, cat: "bottom", icon: "👖", name: "直筒牛仔裤", price: "¥129", inTryon: true },
  { id: 4, cat: "shoes", icon: "👟", name: "帆布鞋", price: "¥89", inTryon: true },
  { id: 5, cat: "acc", icon: "🧢", name: "棒球帽", price: "¥35", inTryon: false },
]);

const cityName = computed(() => store.currentCity?.name ?? "大理");
const dateRange = computed(() => {
  const days = store.days;
  if (!days.length) return "";
  if (days.length === 1) return days[0].dateShort;
  return `${days[0].dateShort}–${days[days.length - 1].dateShort}`;
});

const daySpots = computed(() => {
  const day = store.days[selectedDayIndex.value];
  if (!day) return [];
  return day.spotIds
    .map((id) => store.getSpotById(id))
    .filter(Boolean)
    .map((s) => ({ id: s!.id, emoji: s!.emoji, name: s!.name }));
});

const filteredPool = computed(() =>
  poolFilter.value === "all"
    ? pool.value
    : pool.value.filter((p) => p.cat === poolFilter.value),
);

const selectedItems = computed(() => pool.value.filter((p) => p.inTryon));

const selBarSlots = computed(() => {
  const slots = selectedItems.value.map((p) => `${p.icon} ${p.name}`);
  while (slots.length < 4) slots.push("");
  return slots.slice(0, 4);
});

const bodyHint = computed(() => {
  const line = `${bodyHeight.value}cm · ${bodyWeight.value}kg · 鞋 ${footShoe.value}`;
  return sourceMode.value === "virtual"
    ? `虚拟模特 · ${line}`
    : `真人试穿 · ${line}`;
});

const btnSrcLabel = computed(() =>
  sourceMode.value === "virtual" ? "查看虚拟模特" : "查看原图",
);

const avDisplay = computed(() => (sourceMode.value === "virtual" ? modelAvatar.value : "📷"));

const activeSpotName = computed(() => {
  const spot = daySpots.value.find((s) => s.id === selectedSpotId.value);
  return spot?.name ?? daySpots.value[0]?.name ?? "洱海生态廊道";
});

watch(
  () => store.days.length,
  () => {
    if (selectedDayIndex.value >= store.days.length) {
      selectedDayIndex.value = Math.max(0, store.days.length - 1);
    }
  },
);

watch(
  [selectedDayIndex, daySpots],
  () => {
    const first = daySpots.value[0];
    if (!first) {
      selectedSpotId.value = "";
      return;
    }
    if (!daySpots.value.some((s) => s.id === selectedSpotId.value)) {
      selectedSpotId.value = first.id;
    }
  },
  { immediate: true },
);

function setSourceMode(mode: SourceMode) {
  sourceMode.value = mode;
}

function setModel(av: string) {
  modelAvatar.value = av;
}

function togglePoolItem(id: number) {
  const item = pool.value.find((p) => p.id === id);
  if (item) item.inTryon = !item.inTryon;
}

function fillTodayRecommendations() {
  pool.value.forEach((p) => {
    p.inTryon = p.id <= 4;
  });
}

function toggleSrcPopover(e: MouseEvent) {
  e.stopPropagation();
  srcPopoverOpen.value = !srcPopoverOpen.value;
}

function closePopover() {
  srcPopoverOpen.value = false;
}

function startGenerate() {
  if (generating.value) return;
  generating.value = true;
  showDone.value = false;
  genStatus.value = "生成中…";
  progressWidth.value = 0;

  let w = 0;
  const timer = window.setInterval(() => {
    w += 10;
    progressWidth.value = w;
    if (w >= 100) {
      window.clearInterval(timer);
      generating.value = false;
      showDone.value = true;
      genStatus.value = "完成";
      progressWidth.value = 0;
    }
  }, 100);
}

onMounted(() => document.addEventListener("click", closePopover));
onUnmounted(() => document.removeEventListener("click", closePopover));
</script>

<template>
  <div class="tryon-page">
    <header class="hero">
      <div>
        <h1>✨ AI 试衣</h1>
        <p>{{ cityName }} · {{ dateRange }} · 用推荐商品虚拟试穿 · 景点背景联动</p>
      </div>
      <RouterLink to="/" class="tryon-back">← 返回行程报告</RouterLink>
    </header>

    <div class="tryon-workspace">
      <div class="tryon-grid">
        <aside class="tryon-panel size-col">
          <div class="tryon-panel-title">① 试穿人物</div>
          <div class="tryon-source-mode">
            <button
              type="button"
              :class="{ active: sourceMode === 'virtual' }"
              @click="setSourceMode('virtual')"
            >
              🧍 虚拟模特
              <span class="sub">无需真人照</span>
            </button>
            <button
              type="button"
              :class="{ active: sourceMode === 'photo' }"
              @click="setSourceMode('photo')"
            >
              📷 上传照片
              <span class="sub">真人试穿</span>
            </button>
          </div>

          <div v-show="sourceMode === 'virtual'">
            <div class="tryon-panel-title" style="margin-top: 4px">模特形象</div>
            <div class="tryon-model-pick">
              <button
                v-for="av in ['👩', '👨', '🧑']"
                :key="av"
                type="button"
                class="tryon-model-opt"
                :class="{ active: modelAvatar === av }"
                @click="setModel(av)"
              >
                {{ av }}
              </button>
            </div>
            <p class="tryon-dim-note">🔒 无需上传真人照片，使用虚拟模特试穿</p>
          </div>

          <div v-show="sourceMode === 'photo'">
            <div class="tryon-upload-zone">
              <div style="font-size: 1.8rem">📷</div>
              <p style="font-size: 0.78rem; color: var(--muted)">点击上传全身照</p>
            </div>
            <p class="tryon-privacy-tip">照片仅用于本次试穿；可随时切回「虚拟模特」</p>
          </div>

          <div class="tryon-panel-title" style="margin-top: 12px">② 身材数据</div>
          <div class="tryon-dim-block">
            <p class="tryon-size-hint">填写量体数据，提高 AI 试穿精度（均可选）</p>
            <div class="tryon-dim-row">
              <div class="tryon-dim-field">
                <label>身高 (cm)</label>
                <input v-model.number="bodyHeight" type="number" />
              </div>
              <div class="tryon-dim-field">
                <label>体重 (kg)</label>
                <input v-model.number="bodyWeight" type="number" />
              </div>
            </div>
            <details class="tryon-dim-details">
              <summary>上身尺码</summary>
              <div class="tryon-dim-details-body">
                <div class="tryon-dim-row">
                  <div class="tryon-dim-field"><label>肩宽 (cm)</label><input type="number" value="39" step="0.5" /></div>
                  <div class="tryon-dim-field"><label>臂长 (cm)</label><input type="number" placeholder="—" step="0.5" /></div>
                </div>
                <div class="tryon-dim-row">
                  <div class="tryon-dim-field"><label>臂围 (cm)</label><input type="number" placeholder="—" step="0.5" /></div>
                  <div class="tryon-dim-field"><label>上胸围 (cm)</label><input type="number" value="90" step="0.5" /></div>
                </div>
              </div>
            </details>
            <details class="tryon-dim-details">
              <summary>下身尺码</summary>
              <div class="tryon-dim-details-body">
                <div class="tryon-dim-row">
                  <div class="tryon-dim-field"><label>腰围 (cm)</label><input type="number" value="72" step="0.5" /></div>
                  <div class="tryon-dim-field"><label>臀围 (cm)</label><input type="number" value="96" step="0.5" /></div>
                </div>
              </div>
            </details>
            <details class="tryon-dim-details">
              <summary>脚部尺码</summary>
              <div class="tryon-dim-details-body">
                <div class="tryon-dim-row">
                  <div class="tryon-dim-field"><label>脚长 (cm)</label><input type="number" value="25.0" step="0.1" /></div>
                  <div class="tryon-dim-field"><label>鞋码</label><input v-model="footShoe" /></div>
                </div>
              </div>
            </details>
          </div>

          <div class="tryon-panel-title" style="margin-top: 12px">③ 日期与景点背景</div>
          <div class="tryon-dim-block">
            <p class="tryon-size-hint">选择试穿日期与 AI 合成背景景点</p>
            <div class="tryon-day-chips">
              <button
                v-for="(d, i) in store.days"
                :key="i"
                type="button"
                :class="{ active: selectedDayIndex === i }"
                @click="selectedDayIndex = i"
              >
                {{ d.dateShort }}
              </button>
            </div>
            <div class="tryon-spot-list">
              <label v-for="s in daySpots" :key="s.id" class="tryon-spot-card">
                <input v-model="selectedSpotId" type="radio" name="tryon-spot" :value="s.id" />
                <span class="tryon-spot-ico">{{ s.emoji }}</span>
                <span class="tryon-spot-name">{{ s.name }}</span>
              </label>
              <p v-if="!daySpots.length" class="tryon-size-hint">请先在规划页选择景点</p>
            </div>
          </div>
        </aside>

        <aside class="tryon-panel">
          <div class="tryon-panel-title">④ 推荐商品池</div>
          <button
            type="button"
            class="tryon-btn-secondary"
            style="width: 100%; margin-bottom: 10px; padding: 9px"
            @click="fillTodayRecommendations"
          >
            ↻ 一键填充今日推荐
          </button>
          <div>
            <button
              v-for="(label, key) in CAT_LABELS"
              :key="key"
              type="button"
              class="tryon-cat-tab"
              :class="{ active: poolFilter === key }"
              @click="poolFilter = key as PoolCat"
            >
              {{ label }}
            </button>
          </div>
          <div class="tryon-pool-scroll">
            <div
              v-for="p in filteredPool"
              :key="p.id"
              class="tryon-pool-item"
              :class="{ 'in-tryon': p.inTryon }"
            >
              <div class="thumb">{{ p.icon }}</div>
              <div class="info">
                <div class="cat">{{ CAT_LABELS[p.cat] }}</div>
                <div class="name">{{ p.name }}</div>
                <div class="price">{{ p.price }}</div>
              </div>
              <button type="button" class="add" @click="togglePoolItem(p.id)">
                {{ p.inTryon ? "已选" : "试穿" }}
              </button>
            </div>
          </div>
        </aside>

        <main class="tryon-panel">
          <div class="tryon-preview-head">
            <h3>⑤ AI 换装预览</h3>
            <div class="tryon-source-wrap">
              <button type="button" class="tryon-btn-source" @click="toggleSrcPopover">
                <span>{{ avDisplay }}</span>
                <span>{{ btnSrcLabel }}</span>
              </button>
              <div class="tryon-source-popover" :class="{ open: srcPopoverOpen }" @click.stop>
                <div class="avatar">{{ avDisplay }}</div>
                <p>{{ bodyHint }}</p>
              </div>
            </div>
          </div>

          <div class="tryon-sel-bar">
            <div
              v-for="(slot, i) in selBarSlots"
              :key="i"
              class="tryon-sel-item"
              :class="{ empty: !slot }"
            >
              {{ slot || "+ 配饰" }}
            </div>
          </div>

          <div class="tryon-ai-preview">
            <div class="lbl">
              <span>AI 换装结果</span>
              <span>{{ genStatus }}</span>
            </div>
            <div class="canvas">
              <div v-if="!showDone">
                <div class="avatar" style="opacity: 0.35">👗</div>
                <div class="hint">中间选商品后点击「开始 AI 换装」</div>
              </div>
              <div v-else>
                <div class="avatar">🧥</div>
                <div class="hint done">完成 · {{ activeSpotName }} 背景</div>
              </div>
            </div>
          </div>

          <div class="tryon-action-row">
            <button
              type="button"
              class="tryon-btn-primary"
              :disabled="generating"
              @click="startGenerate"
            >
              开始 AI 换装
            </button>
          </div>
          <div v-show="generating" class="tryon-progress">
            <div class="fill" :style="{ width: `${progressWidth}%` }" />
          </div>
        </main>
      </div>

      <p class="tryon-note">
        ② 身材数据 + ③ 日期景点背景；虚拟模特无需真人照。
        <RouterLink to="/">返回 v1 行程规划</RouterLink>
      </p>
    </div>
  </div>
</template>
