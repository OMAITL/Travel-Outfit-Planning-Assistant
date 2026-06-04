<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type { DailyReportCard, ProductCard } from "@/api/types";
import { DEMO_PRODUCTS, type ProductCategory } from "@/data/demoReport";
import { usePlanningStore } from "@/stores/planning";
import { formatMd, parseOutfitItems, weatherLine, weekdayLabel } from "@/utils/format";

const props = defineProps<{
  card?: DailyReportCard | null;
  demoDayIndex?: number;
  destination?: string;
}>();

const store = usePlanningStore();
const router = useRouter();
const tab = ref<"summary" | "products">("summary");
const sceneId = ref("");
const productCat = ref<string>("");

const productGroups = computed(() => {
  if (props.card?.product_groups?.length) return props.card.product_groups;
  return [];
});

const activeGroup = computed(() => {
  const groups = productGroups.value;
  if (!groups.length) return null;
  if (productCat.value) {
    return groups.find((g) => g.id === productCat.value) ?? groups[0];
  }
  return groups[0];
});

watch(
  productGroups,
  (groups) => {
    if (groups.length && !groups.some((g) => g.id === productCat.value)) {
      productCat.value = groups[0].id;
    }
  },
  { immediate: true },
);

const MAX_PRODUCTS_PER_CAT = 3;

function inferProductCategory(title: string): ProductCategory {
  if (/鞋|靴|凉鞋|拖鞋|帆布鞋|运动鞋/.test(title)) return "shoes";
  if (/裤|裙|短裤|半裙|阔腿裤|牛仔裤/.test(title)) return "bottom";
  if (/帽|包|围巾|腰带|配饰|眼镜|首饰|手表|袜|手套/.test(title)) return "acc";
  return "top";
}

const products = computed((): ProductCard[] => {
  if (activeGroup.value?.products?.length) {
    return activeGroup.value.products.slice(0, MAX_PRODUCTS_PER_CAT);
  }
  if (props.card?.products?.length) {
    const legacyCat = (productCat.value.split("-")[0] || "top") as ProductCategory;
    return props.card.products
      .filter((p) => (p.category ?? inferProductCategory(p.title)) === legacyCat)
      .slice(0, MAX_PRODUCTS_PER_CAT);
  }
  // Live report but no products — do not show demo placeholders (no pic/link)
  if (props.card?.outfit) return [];
  const demoKey = (productCat.value.split("-")[0] || "top") as ProductCategory;
  return DEMO_PRODUCTS[demoKey]?.slice(0, MAX_PRODUCTS_PER_CAT) ?? [];
});

const productSourceHint = computed(() => {
  if (!props.card?.outfit) return "";
  const errs = store.state?.errors ?? [];
  const oneboundErr = errs.find(
    (e) => e.includes("4013") || e.includes("超限") || e.includes("OneBound"),
  );
  const justoneErr = errs.find(
    (e) =>
      e.includes("Just One API") ||
      e.includes("JUSTONE") ||
      e.includes("303") ||
      e.includes("601"),
  );
  if (justoneErr) {
    return "Just One API 配额或余额不足，无法获取淘宝商品。请检查控制台或更换 JUSTONEAPI_TOKEN。";
  }
  if (oneboundErr) {
    return "万邦 API 调用次数已用尽，无法获取淘宝商品图与链接。请登录 open.onebound.cn 充值后重新规划。";
  }
  if (!products.value.length && !productGroups.value.some((g) => g.products.length)) {
    return "暂无符合预算的淘宝商品，可尝试提高分类预算或稍后重试。";
  }
  return "";
});

const catLabels = computed(() => {
  if (productGroups.value.length) {
    return productGroups.value.map((g) => ({ key: g.id, label: g.label }));
  }
  return [
    { key: "top", label: "上装" },
    { key: "bottom", label: "下装" },
    { key: "shoes", label: "鞋" },
    { key: "acc", label: "配饰" },
  ];
});

function budgetLabel(p: ProductCard): string {
  return p.within_budget === false ? "超出预算" : "符合预算";
}

const demoDay = computed(() => store.days[props.demoDayIndex ?? store.selectedDayIndex]);

const isLive = computed(() => !!props.card?.outfit);

const headerTitle = computed(() => {
  if (props.card) return `${formatMd(props.card.date)} · ${weekdayLabel(props.card.date)}`;
  const d = demoDay.value;
  return d ? d.title : "";
});

const headerWeather = computed(() => {
  if (props.card?.weather) return weatherLine(props.card.weather);
  return demoDay.value?.weather ?? "";
});

const tips = computed(() => [
  "昼夜温差大，建议洋葱式叠穿，方便中午脱外套",
  "可能降雨，备轻便雨衣或防水外套",
]);

const reason = computed(() => {
  if (props.card?.outfit?.recommendation_reason) return props.card.outfit.recommendation_reason;
  if (props.card?.outfit?.outfit_summary) return props.card.outfit.outfit_summary;
  return demoDay.value?.reason ?? "";
});

const items = computed(() => {
  if (props.card?.outfit_items?.length) {
    return props.card.outfit_items.map((i) => ({ label: i.label, text: i.text }));
  }
  if (props.card?.outfit) return parseOutfitItems(props.card.outfit.outfit_summary);
  return (
    demoDay.value?.spotIds.length
      ? [
          { label: "上装", text: "白色棉质短袖 T 恤 + 浅卡其防水风衣" },
          { label: "下装", text: "蓝色直筒牛仔裤" },
          { label: "鞋", text: "白色帆布鞋（防泼水）" },
          { label: "配饰", text: "卡其棒球帽 · 米色斜挎包" },
        ]
      : []
  );
});

const scores = computed(() => [
  "风格 ★★★★☆",
  "舒适 ★★★★★",
  "出片 ★★★★☆",
  "配色 白·卡其·蓝",
]);

const styleReferences = computed(() => props.card?.style_references ?? []);

const sceneSpots = computed(() => {
  if (isLive.value && props.card?.spot_names?.length) {
    return props.card.spot_names.map((name, i) => ({
      id: `live-${i}`,
      label: store.shortSpotLabel(name),
      sceneSub: `背景：${name}`,
      sceneLabel: `AI 生成 · ${props.destination || ""} · ${name}`,
    }));
  }
  if (isLive.value) {
    const d = demoDay.value;
    if (d?.sceneSpots.length) {
      return d.sceneSpots.map((label, i) => ({
        id: `sync-${i}`,
        label,
        sceneSub: `背景：${label}`,
        sceneLabel: `AI 生成 · ${props.destination || ""} · ${label}`,
      }));
    }
    return [
      {
        id: "live",
        label: props.destination || "旅行",
        sceneSub: "",
        sceneLabel: `AI 生成 · ${props.destination || ""}`,
      },
    ];
  }
  const d = demoDay.value;
  if (!d) return [];
  return d.sceneSpots.map((label, i) => ({
    id: `scene-${i}`,
    label,
    sceneSub: `背景：${label === "洱海廊道" ? "洱海生态廊道" : label}`,
    sceneLabel: `AI 生成 · 女 · 休闲风 · ${label === "洱海廊道" ? "洱海生态廊道" : label}`,
  }));
});

const activeScene = computed(
  () => sceneSpots.value.find((s) => s.id === sceneId.value) ?? sceneSpots.value[0],
);

watch(
  () => props.demoDayIndex ?? store.selectedDayIndex,
  () => {
    const spots = sceneSpots.value;
    sceneId.value = spots[0]?.id ?? "";
    tab.value = "summary";
    productCat.value = productGroups.value[0]?.id ?? "top";
  },
  { immediate: true },
);

function goTryon() {
  router.push("/tryon");
}
</script>

<template>
  <article class="magazine">
    <div class="mag-header">
      <h3>{{ headerTitle }}</h3>
      <div class="weather-line">{{ headerWeather }}</div>
    </div>

    <div class="content-tabs">
      <button type="button" :class="{ active: tab === 'summary' }" @click="tab = 'summary'">
        概要
      </button>
      <button type="button" :class="{ active: tab === 'products' }" @click="tab = 'products'">
        推荐商品
      </button>
    </div>

    <div class="tab-panel" :class="{ active: tab === 'summary' }">
      <div class="mag-body">
        <div class="mag-text">
          <div class="section">
            <div class="section-title">旅行提醒</div>
            <ul class="tips-list">
              <li v-for="(tip, i) in tips" :key="i">{{ tip }}</li>
            </ul>
          </div>
          <div class="section">
            <div class="section-title">推荐理由</div>
            <div class="reason-box">{{ reason }}</div>
          </div>
          <div class="section">
            <div class="section-title">单品清单</div>
            <div class="items-grid">
              <div v-for="item in items" :key="item.label" class="item-cell">
                <span class="lbl">{{ item.label }}</span><br />
                {{ item.text }}
              </div>
            </div>
          </div>
          <div v-if="styleReferences.length" class="section">
            <div class="section-title">小红书穿搭参考</div>
            <div class="xhs-ref-grid">
              <a
                v-for="ref in styleReferences"
                :key="ref.note_id"
                class="xhs-ref-card"
                :href="ref.note_url || '#'"
                target="_blank"
                rel="noopener noreferrer"
              >
                <img
                  v-if="ref.cover_url"
                  :src="ref.cover_url"
                  :alt="ref.title || '穿搭参考'"
                  loading="lazy"
                  referrerpolicy="no-referrer"
                />
                <div class="xhs-ref-body">
                  <div class="xhs-ref-title">{{ ref.title || "小红书笔记" }}</div>
                  <div v-if="ref.user_name" class="xhs-ref-meta">@{{ ref.user_name }}</div>
                </div>
              </a>
            </div>
          </div>
          <div class="scores">
            <span v-for="(s, i) in scores" :key="i">{{ s }}</span>
          </div>
        </div>
        <div class="mag-visual">
          <div class="spot-pills">
            <button
              v-for="s in sceneSpots"
              :key="s.id"
              type="button"
              class="spot-pill"
              :class="{ active: sceneId === s.id || (!sceneId && s === sceneSpots[0]) }"
              @click="sceneId = s.id"
            >
              {{ s.label }}
            </button>
          </div>
          <div class="ai-frame">
            <img v-if="card?.look_image_url" :src="card.look_image_url" alt="穿搭效果图" />
            <div v-else class="placeholder">
              <div class="icon">📸</div>
              <p>今日穿搭预览</p>
              <p v-if="activeScene?.sceneSub" class="scene-sub">{{ activeScene.sceneSub }}</p>
            </div>
            <div class="scene-label">{{ activeScene?.sceneLabel }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="tab-panel" :class="{ active: tab === 'products' }">
      <div class="products-head">
        <h4>🛍 推荐商品 — 与穿搭一一对应</h4>
        <button type="button" class="link-tryon" @click="goTryon">✨ AI 试衣</button>
      </div>
      <div class="cat-tabs">
        <button
          v-for="c in catLabels"
          :key="c.key"
          type="button"
          class="cat-tab"
          :class="{ active: productCat === c.key }"
          @click="productCat = c.key"
        >
          {{ c.label }}
        </button>
      </div>
      <p v-if="activeGroup?.item_text" class="product-item-hint">
        对应单品：{{ activeGroup.item_text }}
      </p>
      <div class="product-grid">
        <a
          v-for="(p, i) in products"
          :key="p.num_iid ?? i"
          class="p-card"
          :href="p.detail_url || '#'"
          target="_blank"
          rel="noopener noreferrer"
        >
          <div class="img">
            <img
              v-if="p.pic_url"
              :src="p.pic_url"
              :alt="p.title"
              loading="lazy"
              referrerpolicy="no-referrer"
            />
            <span v-else class="img-fallback">🛍️</span>
          </div>
          <div class="body">
            <div class="title">{{ p.title }}</div>
            <div class="price">¥{{ p.price }}</div>
            <div class="budget" :class="{ over: p.within_budget === false }">
              {{ budgetLabel(p) }}
            </div>
            <span class="cta">去淘宝购买</span>
          </div>
        </a>
      </div>
      <p v-if="productSourceHint" class="products-empty products-api-hint">{{ productSourceHint }}</p>
      <p v-else-if="!products.length" class="products-empty">该品类暂无匹配商品</p>
    </div>
  </article>
</template>
