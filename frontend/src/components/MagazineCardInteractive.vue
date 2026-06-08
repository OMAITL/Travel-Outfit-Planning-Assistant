<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type { DailyReportCard, ProductCard, ProductItemGroup } from "@/api/types";
import { DEMO_PRODUCTS, type ProductCategory } from "@/data/demoReport";
import { usePlanningStore } from "@/stores/planning";
import {
  formatMd,
  outfitLabelToCategory,
  parseOutfitItems,
  scoreProductTitleMatch,
  splitCompoundItemText,
  weatherLine,
  weekdayLabel,
} from "@/utils/format";
import { proxiedImageUrl } from "@/utils/proxyImage";

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
const brokenImages = ref<Set<string>>(new Set());

function productImageKey(product: ProductCard, index: number): string {
  return productKey(product) || `${index}`;
}

function onProductImageError(key: string) {
  brokenImages.value = new Set([...brokenImages.value, key]);
}

const MAX_PRODUCTS_PER_CAT = 3;

const CATEGORY_ORDER = ["top", "bottom", "shoes", "acc"] as const;
const CATEGORY_LABELS: Record<string, string> = {
  top: "上装",
  bottom: "下装",
  shoes: "鞋",
  acc: "配饰",
};

function groupCategory(group: ProductItemGroup): string {
  return group.category || group.id.split("-")[0] || "top";
}

const productGroups = computed(() => {
  if (props.card?.product_groups?.length) return props.card.product_groups;
  return [];
});

const categoryKeys = computed(() => {
  if (productGroups.value.length) {
    const seen = new Set<string>();
    for (const group of productGroups.value) {
      seen.add(groupCategory(group));
    }
    return CATEGORY_ORDER.filter((cat) => seen.has(cat));
  }
  return ["top", "bottom", "shoes", "acc"];
});

interface ProductSection {
  id: string;
  itemText: string;
  products: ProductCard[];
}

function inferProductCategory(title: string): ProductCategory {
  if (/鞋|靴|凉鞋|拖鞋|帆布鞋|运动鞋/.test(title)) return "shoes";
  if (/裤|裙|短裤|半裙|阔腿裤|牛仔裤/.test(title)) return "bottom";
  if (/帽|包|围巾|腰带|配饰|眼镜|首饰|手表|袜|手套/.test(title)) return "acc";
  return "top";
}

function productKey(product: ProductCard): string {
  return product.num_iid ?? product.detail_url ?? product.title;
}

function dedupeProducts(products: ProductCard[]): ProductCard[] {
  const seen = new Set<string>();
  const unique: ProductCard[] = [];
  for (const product of products) {
    const key = productKey(product);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(product);
  }
  return unique;
}

function categoryProducts(cat: string): ProductCard[] {
  const fromGroups = productGroups.value
    .filter((group) => groupCategory(group) === cat)
    .flatMap((group) => group.products);
  const fromCard =
    props.card?.products?.filter(
      (product) => (product.category ?? inferProductCategory(product.title)) === cat,
    ) ?? [];
  return dedupeProducts([...fromGroups, ...fromCard]);
}

function categoryItemTexts(cat: string): string[] {
  const groups = productGroups.value.filter((group) => groupCategory(group) === cat);
  if (groups.length) {
    const texts: string[] = [];
    for (const group of groups) {
      for (const part of splitCompoundItemText(group.item_text)) {
        if (!texts.includes(part)) texts.push(part);
      }
    }
    return texts;
  }

  const outfitItem = items.value.find((item) => outfitLabelToCategory(item.label) === cat);
  if (!outfitItem) return [];
  return splitCompoundItemText(outfitItem.text);
}

function pickProductsForItem(itemText: string, pool: ProductCard[], used: Set<string>): ProductCard[] {
  const matched: ProductCard[] = [];

  for (const product of pool) {
    const key = productKey(product);
    if (used.has(key)) continue;
    const tagged = (product.item_text || "").trim();
    if (
      tagged &&
      (tagged === itemText || tagged.includes(itemText) || itemText.includes(tagged))
    ) {
      matched.push(product);
      used.add(key);
      if (matched.length >= MAX_PRODUCTS_PER_CAT) return matched;
    }
  }

  const ranked = pool
    .filter((product) => !used.has(productKey(product)))
    .map((product) => ({ product, score: scoreProductTitleMatch(product.title, itemText) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score);

  for (const row of ranked) {
    matched.push(row.product);
    used.add(productKey(row.product));
    if (matched.length >= MAX_PRODUCTS_PER_CAT) break;
  }

  return matched;
}

function buildCategorySections(cat: string, pool: ProductCard[], itemTexts: string[]): ProductSection[] {
  if (itemTexts.length <= 1) {
    const demoProducts =
      !pool.length && !props.card?.outfit
        ? (DEMO_PRODUCTS[cat as ProductCategory]?.slice(0, MAX_PRODUCTS_PER_CAT) ?? [])
        : pool.slice(0, MAX_PRODUCTS_PER_CAT);
    return [
      {
        id: `${cat}-0`,
        itemText: itemTexts[0] ?? "",
        products: demoProducts,
      },
    ];
  }

  const used = new Set<string>();
  return itemTexts.map((itemText, index) => ({
    id: `${cat}-${index}`,
    itemText,
    products: pickProductsForItem(itemText, pool, used),
  }));
}

function sectionsFromProductGroups(cat: string): ProductSection[] {
  const groups = productGroups.value.filter((group) => groupCategory(group) === cat);
  const sections: ProductSection[] = [];

  for (const group of groups) {
    const parts = splitCompoundItemText(group.item_text);
    if (parts.length <= 1) {
      sections.push({
        id: group.id,
        itemText: group.item_text,
        products: group.products.slice(0, MAX_PRODUCTS_PER_CAT),
      });
      continue;
    }

    const used = new Set<string>();
    for (const [index, part] of parts.entries()) {
      sections.push({
        id: `${group.id}-${index}`,
        itemText: part,
        products: pickProductsForItem(part, group.products, used),
      });
    }
  }

  return sections;
}

const activeCategorySections = computed((): ProductSection[] => {
  const cat = productCat.value;

  if (productGroups.value.length) {
    const sections = sectionsFromProductGroups(cat);
    if (sections.length) return sections;
  }

  const itemTexts = categoryItemTexts(cat);
  if (!itemTexts.length) return [];
  return buildCategorySections(cat, categoryProducts(cat), itemTexts);
});

watch(
  categoryKeys,
  (cats) => {
    if (cats.length && !cats.includes(productCat.value as (typeof CATEGORY_ORDER)[number])) {
      productCat.value = cats[0];
    }
  },
  { immediate: true },
);

const hasCategoryProducts = computed(() =>
  activeCategorySections.value.some((section) => section.products.length > 0),
);

const productSourceHint = computed(() => {
  if (!props.card?.outfit) return "";
  const errs = store.state?.errors ?? [];
  const apiUnavailable = errs.some(
    (e) =>
      e.includes("4013") ||
      e.includes("超限") ||
      e.includes("OneBound") ||
      e.includes("Just One API") ||
      e.includes("JUSTONE") ||
      e.includes("303") ||
      e.includes("601") ||
      e.includes("配额"),
  );
  const quotaTrace = (store.state?.trace ?? []).some(
    (t) => t.agent === "Shopping" && t.message.includes("quota reached"),
  );
  if (!hasCategoryProducts.value && !productGroups.value.some((group) => group.products.length)) {
    if (apiUnavailable || quotaTrace) {
      if (typeof console !== "undefined") {
        console.warn("[Shopping] product links unavailable", { apiUnavailable, quotaTrace, errs });
      }
      return "商品链接暂时无法加载，请稍后重新规划或适当提高预算后再试。";
    }
    return "暂无符合预算的商品推荐，可尝试提高分类预算。";
  }
  return "";
});

function categoryTabLabel(cat: string): string {
  const base = CATEGORY_LABELS[cat] ?? cat;
  const groups = productGroups.value.filter((group) => groupCategory(group) === cat);
  if (groups.length) {
    const combined = groups.map((group) => group.item_text).join("、");
    const short = combined.length > 14 ? `${combined.slice(0, 14)}…` : combined;
    return `${base}·${short}`;
  }

  const outfitItem = items.value.find((item) => outfitLabelToCategory(item.label) === cat);
  if (outfitItem) {
    const short =
      outfitItem.text.length > 14 ? `${outfitItem.text.slice(0, 14)}…` : outfitItem.text;
    return `${base}·${short}`;
  }

  if (props.card?.outfit) return base;
  return base;
}

const catLabels = computed(() => {
  return categoryKeys.value.map((cat) => ({
    key: cat,
    label: categoryTabLabel(cat),
  }));
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

const tips = computed(() => {
  if (props.card?.travel_tips?.length) return props.card.travel_tips;
  if (props.card?.weather) {
    const w = props.card.weather;
    const hints: string[] = [];
    const spread = w.temp_max - w.temp_min;
    if (w.temp_max >= 30) {
      hints.push(
        "☀️ 高温提醒：午间紫外线较强、体感闷热，建议配备墨镜、防晒帽，并随身携带补充水分。",
      );
    } else if (w.temp_max >= 28) {
      hints.push(
        `🌡️ 体感偏热：最高气温约 ${w.temp_max}°C，推荐轻薄透气面料，午间注意防晒补水。`,
      );
    }
    if (w.temp_min <= 18 && spread >= 10) {
      hints.push(
        `🌡️ 温差提醒：早晚温差达 ${Math.round(spread)}°C，上午10点前及晚上8点后体感较凉，外搭的轻薄外套不可少。`,
      );
    } else if (spread >= 8 && w.temp_min <= 20) {
      hints.push(
        `🌡️ 昼夜温差：当日温差 ${Math.round(spread)}°C，建议洋葱式分层，中午可脱外套、早晚及时添衣。`,
      );
    }
    if (w.condition.includes("雨") || (w.rain_prob ?? 0) >= 40) {
      hints.push("🌧️ 降雨可能：备轻便雨具或防水外套，路面湿滑请选择防滑鞋。");
    }
    if (hints.length) return hints;
    return [`当日 ${w.temp_min}–${w.temp_max}°C、${w.condition}，根据体感灵活增减衣物`];
  }
  return demoDay.value?.tips ?? [];
});

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

const xhsSourceHint = computed(() => {
  if (!props.card?.outfit) return "";
  const refs = styleReferences.value;
  if (refs.length > 0) {
    if (refs.length < 3 && typeof console !== "undefined") {
      console.warn("[XHS] fewer than 3 reference notes", {
        count: refs.length,
        trace: store.state?.trace?.filter((t) => t.agent === "Inspiration"),
      });
    }
    return "";
  }
  if (typeof console !== "undefined") {
    console.warn("[XHS] no reference notes for this day", {
      errors: store.state?.errors,
      trace: store.state?.trace?.filter((t) => t.agent === "Inspiration"),
    });
  }
  return "暂未找到匹配的小红书穿搭参考，不影响当日 AI 穿搭推荐。";
});

const xhsPartialHint = computed(() => {
  const n = styleReferences.value.length;
  if (n > 0 && n < 3) return `已精选 ${n} 条高赞穿搭笔记供参考`;
  return "";
});

const sceneSpots = computed(() => {
  if (isLive.value && props.card?.spot_names?.length) {
    return props.card.spot_names.map((name, i) => ({
      id: `live-${i}`,
      spotName: name,
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
        spotName: label,
        label,
        sceneSub: `背景：${label}`,
        sceneLabel: `AI 生成 · ${props.destination || ""} · ${label}`,
      }));
    }
    return [
      {
        id: "live",
        spotName: props.destination || "旅行",
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
    spotName: label === "洱海廊道" ? "洱海生态廊道" : label,
    label,
    sceneSub: `背景：${label === "洱海廊道" ? "洱海生态廊道" : label}`,
    sceneLabel: `AI 生成 · 女 · 休闲风 · ${label === "洱海廊道" ? "洱海生态廊道" : label}`,
  }));
});

const activeScene = computed(
  () => sceneSpots.value.find((s) => s.id === sceneId.value) ?? sceneSpots.value[0],
);

const activeLookImageUrl = computed(() => {
  const card = props.card;
  if (!card) return null;
  const spotName = activeScene.value?.spotName;
  if (spotName && card.look_images_by_spot?.[spotName]) {
    return card.look_images_by_spot[spotName];
  }
  return card.look_image_url;
});

watch(
  () => props.demoDayIndex ?? store.selectedDayIndex,
  () => {
    const spots = sceneSpots.value;
    sceneId.value = spots[0]?.id ?? "";
    tab.value = "summary";
    productCat.value = categoryKeys.value[0] ?? "top";
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
          <div v-if="styleReferences.length || xhsSourceHint" class="section">
            <div class="section-title">小红书穿搭参考</div>
            <ul v-if="styleReferences.length" class="xhs-ref-list">
              <li v-for="ref in styleReferences" :key="ref.note_id">
                <a
                  class="xhs-ref-link"
                  :href="ref.note_url || '#'"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ ref.title || "小红书笔记" }}
                  <span v-if="ref.user_name"> · @{{ ref.user_name }}</span>
                </a>
              </li>
            </ul>
            <p v-if="xhsPartialHint" class="xhs-partial-hint">{{ xhsPartialHint }}</p>
            <p v-else-if="xhsSourceHint" class="xhs-empty-hint">{{ xhsSourceHint }}</p>
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
            <img
              v-if="activeLookImageUrl"
              :src="proxiedImageUrl(activeLookImageUrl)"
              alt="穿搭效果图"
            />
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
      <div class="product-item-list">
        <div
          v-for="(section, sectionIndex) in activeCategorySections"
          :key="section.id"
          class="product-item-section"
        >
        <div class="product-item-head">
          <span
            class="product-item-badge"
            :class="sectionIndex === 0 ? 'primary' : 'secondary'"
          >
            {{ sectionIndex === 0 ? "当前单品" : "其他单品" }}
          </span>
          <span class="product-item-name">
            对应单品 {{ sectionIndex + 1 }}：{{ section.itemText }}
          </span>
        </div>
        <div v-if="section.products.length" class="product-grid">
          <a
            v-for="(p, i) in section.products"
            :key="p.num_iid ?? `${section.id}-${i}`"
            class="p-card"
            :href="p.detail_url || '#'"
            target="_blank"
            rel="noopener noreferrer"
          >
            <div class="img">
              <img
                v-if="p.pic_url && !brokenImages.has(productImageKey(p, i))"
                :src="proxiedImageUrl(p.pic_url)"
                alt=""
                loading="lazy"
                referrerpolicy="no-referrer"
                @error="onProductImageError(productImageKey(p, i))"
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
        <p v-else class="product-item-empty">该单品暂无匹配商品</p>
        </div>
      </div>
      <p v-if="productSourceHint" class="products-empty products-api-hint">{{ productSourceHint }}</p>
      <p v-else-if="!hasCategoryProducts" class="products-empty">该品类暂无匹配商品</p>
    </div>
  </article>
</template>
