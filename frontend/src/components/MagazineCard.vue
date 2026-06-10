<script setup lang="ts">
import { ref } from "vue";
import type { DailyReportCard } from "@/api/types";
import { formatMd, parseOutfitItems, weatherLine, weekdayLabel } from "@/utils/format";

defineProps<{
  card: DailyReportCard;
  destination?: string;
}>();

const tab = ref<"summary" | "look" | "products">("summary");
</script>

<template>
  <article class="magazine">
    <div class="mag-header">
      <h3>{{ formatMd(card.date) }} · {{ weekdayLabel(card.date) }}</h3>
      <div v-if="card.weather" class="weather-line">{{ weatherLine(card.weather) }}</div>
    </div>

    <div class="content-tabs">
      <button type="button" :class="{ active: tab === 'summary' }" @click="tab = 'summary'">概要</button>
      <button type="button" :class="{ active: tab === 'look' }" @click="tab = 'look'">AI 效果图</button>
      <button type="button" :class="{ active: tab === 'products' }" @click="tab = 'products'">推荐商品</button>
    </div>

    <div class="tab-panel">
      <div v-if="tab === 'summary' && card.outfit" class="mag-body">
        <div class="mag-text">
          <div class="section">
            <div class="section-title">推荐理由</div>
            <div class="reason-box">
              {{ card.outfit.recommendation_reason || card.outfit.outfit_summary }}
            </div>
          </div>
          <div class="section">
            <div class="section-title">单品清单</div>
            <div class="items-grid">
              <div v-for="item in parseOutfitItems(card.outfit.outfit_summary)" :key="item.label" class="item-cell">
                <span class="lbl">{{ item.label }}</span><br />
                {{ item.text }}
              </div>
            </div>
          </div>
          <div class="scores-row">
            <span>风格 ★★★★☆</span>
            <span>舒适 ★★★★★</span>
            <span>出片 ★★★★☆</span>
          </div>
        </div>
        <div class="mag-visual">
          <div class="ai-frame">
            <img v-if="card.look_image_url" :src="card.look_image_url" alt="穿搭效果图" />
            <div v-else class="placeholder">
              <div style="font-size: 2.5rem">📸</div>
              <p>今日穿搭预览</p>
            </div>
            <div class="scene-label">AI 生成 · {{ destination || "旅行" }}</div>
          </div>
        </div>
      </div>

      <div v-else-if="tab === 'look'" class="mag-visual" style="min-height: 320px">
        <div class="ai-frame" style="min-height: 300px">
          <img v-if="card.look_image_url" :src="card.look_image_url" alt="穿搭效果图" />
          <div v-else class="placeholder">
            <div style="font-size: 3rem">🖼️</div>
            <p>效果图生成中或未配置 Key</p>
          </div>
        </div>
      </div>

      <div v-else-if="tab === 'products'">
        <p v-if="!card.products.length" style="color: var(--muted); font-size: 0.85rem">暂无推荐商品</p>
        <div v-else class="products-grid">
          <a
            v-for="(p, i) in card.products"
            :key="i"
            class="product-card"
            :href="p.detail_url"
            target="_blank"
            rel="noopener"
          >
            <img :src="p.pic_url" :alt="p.title" />
            <div class="info">
              <div>{{ p.title.slice(0, 40) }}</div>
              <div class="price">¥{{ p.price }}</div>
            </div>
          </a>
        </div>
      </div>
    </div>
  </article>
</template>
