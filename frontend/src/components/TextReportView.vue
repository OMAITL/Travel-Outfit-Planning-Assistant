<script setup lang="ts">
import { computed } from "vue";
import type { DailyReportCard, OutfitItemView, StyleReference } from "@/api/types";
import { usePlanningStore } from "@/stores/planning";
import { formatMd, parseOutfitItems, weekdayLabel, weatherLine } from "@/utils/format";

const store = usePlanningStore();
const report = computed(() => store.state?.report ?? null);
const cards = computed(() => report.value?.daily_cards ?? []);

const tripMeta = computed(() => {
  const r = report.value;
  if (!r) return "";
  const parts: string[] = [];
  if (r.start_date && r.end_date) {
    parts.push(`${formatMd(r.start_date)} – ${formatMd(r.end_date)}`);
  }
  if (r.trip_days) parts.push(`${r.trip_days} 日`);
  return parts.join(" · ");
});

const intentSummary = computed(() => report.value?.summary ?? "");

function dayLabel(card: DailyReportCard, index: number): string {
  return `Day ${index + 1}`;
}

function dayDateLine(card: DailyReportCard): string {
  return `${formatMd(card.date)} ${weekdayLabel(card.date)}`;
}

function spotsLine(card: DailyReportCard): string {
  const parts: string[] = [];
  if (card.morning) parts.push(`上午 ${card.morning}`);
  if (card.afternoon) parts.push(`下午 ${card.afternoon}`);
  if (card.evening) parts.push(`晚间 ${card.evening}`);
  if (parts.length) return parts.join(" → ");
  if (card.spot_names?.length) return card.spot_names.join(" · ");
  return "待分配景点";
}

function outfitItems(card: DailyReportCard): OutfitItemView[] {
  if (card.outfit_items?.length) return card.outfit_items;
  const summary = card.outfit?.outfit_summary ?? "";
  return parseOutfitItems(summary).map((item) => ({ label: item.label, text: item.text }));
}

function alternativeItems(card: DailyReportCard): OutfitItemView[] {
  const alt = card.outfit?.alternative_outfit_summary?.trim();
  if (!alt) return [];
  return parseOutfitItems(alt).map((item) => ({ label: item.label, text: item.text }));
}

function sceneAdaptation(card: DailyReportCard): string {
  return card.outfit?.recommendation_reason?.trim() || "";
}

function xhsRefsForCard(card: DailyReportCard): StyleReference[] {
  const refs = card.style_references ?? [];
  const notes = refs.filter((r) => r.note_url && !r.is_search_link);
  if (notes.length) return notes;
  return refs.filter((r) => r.is_search_link && r.note_url);
}

function xhsLinkTitle(ref: StyleReference): string {
  return ref.title || ref.search_keyword || "穿搭参考";
}
</script>

<template>
  <div v-if="report" class="text-report">
    <header class="tr-summary">
      <div class="tr-summary-top">
        <h3 class="tr-destination">{{ report.destination }}</h3>
        <span class="tr-badge">整套穿搭</span>
      </div>
      <p v-if="tripMeta" class="tr-dates">{{ tripMeta }}</p>
      <p v-if="intentSummary" class="tr-desc">{{ intentSummary }}</p>
    </header>

    <article v-for="(card, i) in cards" :key="card.date" class="tr-day">
      <header class="tr-day-header">
        <div class="tr-day-left">
          <span class="tr-day-num">{{ dayLabel(card, i) }}</span>
          <span class="tr-day-date">{{ dayDateLine(card) }}</span>
        </div>
        <span v-if="card.weather" class="tr-day-weather">{{ weatherLine(card.weather) }}</span>
      </header>

      <div class="tr-spots">
        <span class="tr-spots-icon" aria-hidden="true">📍</span>
        {{ spotsLine(card) }}
      </div>

      <section v-if="outfitItems(card).length" class="tr-section">
        <h4 class="tr-section-title">整套搭配</h4>
        <div class="tr-outfit-rows">
          <div v-for="(item, j) in outfitItems(card)" :key="j" class="tr-outfit-row">
            <span class="tr-outfit-label">{{ item.label }}</span>
            <span class="tr-outfit-text">{{ item.text }}</span>
          </div>
        </div>
      </section>

      <section v-if="sceneAdaptation(card)" class="tr-scene">
        <h4 class="tr-section-title">场景适配</h4>
        <p>{{ sceneAdaptation(card) }}</p>
      </section>

      <section v-if="alternativeItems(card).length" class="tr-section tr-section-muted">
        <h4 class="tr-section-title">替代方案</h4>
        <div class="tr-outfit-rows">
          <div v-for="(item, j) in alternativeItems(card)" :key="j" class="tr-outfit-row">
            <span class="tr-outfit-label">{{ item.label }}</span>
            <span class="tr-outfit-text">{{ item.text }}</span>
          </div>
        </div>
      </section>

      <section v-if="xhsRefsForCard(card).length" class="tr-xhs">
        <h4 class="tr-section-title">小红书参考</h4>
        <ul class="tr-xhs-links">
          <li v-for="ref in xhsRefsForCard(card)" :key="ref.note_id">
            <a :href="ref.note_url" target="_blank" rel="noopener noreferrer">
              {{ xhsLinkTitle(ref) }}
            </a>
          </li>
        </ul>
      </section>
    </article>

    <footer v-if="report.disclaimer" class="tr-footer">{{ report.disclaimer }}</footer>
  </div>
</template>
