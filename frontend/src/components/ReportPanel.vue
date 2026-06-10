<script setup lang="ts">
import { computed } from "vue";
import RichReportBody from "./RichReportBody.vue";
import TextReportView from "./TextReportView.vue";
import { usePlanningStore } from "@/stores/planning";

const store = usePlanningStore();

const showChatReportActions = computed(
  () => store.inputTab === "chat" && store.hasLiveReport,
);

const collectingHints = computed(() => {
  const intent = store.state?.chat_intent;
  const hints: { text: string; missing?: boolean }[] = [];

  if (intent?.destination) hints.push({ text: `📍 ${intent.destination}` });
  if (intent?.start_date && intent?.end_date) {
    hints.push({ text: `📅 ${intent.start_date} – ${intent.end_date}` });
  }
  if (intent?.scene_type) hints.push({ text: `🎯 ${intent.scene_type}` });
  if (intent?.style_tendency) hints.push({ text: `🎨 ${intent.style_tendency}` });
  if (intent?.gender) hints.push({ text: `👤 ${intent.gender}` });
  if (intent?.spot_names?.length) hints.push({ text: `📍 ${intent.spot_names.join("、")}` });
  if (intent?.budget_per_item) hints.push({ text: `💰 单品约 ¥${intent.budget_per_item}` });
  if (intent?.body_type) hints.push({ text: `🧍 ${intent.body_type}` });
  if (intent?.height_cm && intent?.weight_kg) {
    hints.push({ text: `📏 ${intent.height_cm}cm / ${intent.weight_kg}kg` });
  }
  if (intent?.skin_tone) hints.push({ text: `🎨 肤色 ${intent.skin_tone}` });
  if (intent?.avoid_items?.length) hints.push({ text: `🚫 ${intent.avoid_items.join("、")}` });
  if (intent?.climate_hint) hints.push({ text: `🌤 ${intent.climate_hint}` });

  const fieldLabels: Record<string, string> = {
    scene_type: "场景偏好",
    destination: "目的地",
    dates: "出行日期",
    start_date: "出行日期",
    end_date: "返程日期",
    gender: "性别",
    spot_names: "景点",
    budget: "预算",
    body_type: "体型",
    height_weight: "身高体重",
    skin_tone: "肤色",
    avoid_items: "穿搭避雷",
  };

  for (const field of intent?.missing_fields ?? []) {
    hints.push({ text: `${fieldLabels[field] ?? field} ？`, missing: true });
  }

  if (!hints.length) {
    const userMsgs = (store.state?.messages ?? []).filter((m) => m.role === "user");
    const last = userMsgs.at(-1);
    if (last) hints.push({ text: last.content.slice(0, 40) + (last.content.length > 40 ? "…" : "") });
  }
  return hints;
});
</script>

<template>
  <section
    class="report-panel"
    :class="{ 'report-panel-highlight': store.reportHighlight }"
  >
    <div v-if="store.toast" class="toast-banner">{{ store.toast }}</div>

    <div class="report-head">
      <h2>行程报告</h2>
      <div class="report-head-right">
        <div
          v-if="(store.inputTab === 'form' && store.hasReport) || showChatReportActions"
          class="report-actions"
        >
          <button
            v-show="store.planMode === 'auto' && store.demoReportActive && !store.state?.report?.daily_cards?.length"
            type="button"
            class="btn-ghost"
            @click="store.regenItinerary()"
          >
            ↻ 重新智能分配
          </button>
          <button
            v-show="store.planMode === 'auto' && store.demoReportActive && !store.state?.report?.daily_cards?.length"
            type="button"
            class="btn-ghost"
            :class="{ active: store.editItinerary }"
            @click="store.toggleEditItinerary()"
          >
            {{ store.editItineraryLabel }}
          </button>
          <button type="button" class="btn-ghost" @click="store.reset()">重新规划</button>
        </div>
      </div>
    </div>

    <!-- ═══ 快速填写：保持原有逻辑 ═══ -->
    <template v-if="store.inputTab === 'form'">
      <div v-if="store.error && !store.hasReport" class="error-banner">{{ store.error }}</div>

      <div v-if="!store.hasReport" class="report-empty">
        <div class="report-empty-card">
          <div class="report-empty-icon" aria-hidden="true">🗺️</div>
          <h3 class="report-empty-title">尚未生成行程报告</h3>
          <p class="report-empty-desc">
            请在左侧填写目的地、出行日期、景点与风格偏好，点击
            <strong>「开始规划穿搭」</strong>
            后，AI 将为你生成每日行程分配、穿搭推荐与购物清单。
          </p>
          <ul class="report-empty-steps">
            <li><span>1</span>选择目的地与景点</li>
            <li><span>2</span>设置风格与预算</li>
            <li><span>3</span>一键生成专属报告</li>
          </ul>
        </div>
      </div>

      <template v-else>
        <div v-if="store.error" class="error-banner">{{ store.error }}</div>
        <RichReportBody />
      </template>
    </template>

    <!-- ═══ 自由对话：仅文字报告 ═══ -->
    <template v-else>
      <div v-if="store.error && store.showChatEmpty" class="error-banner">{{ store.error }}</div>

      <div v-if="store.showChatEmpty" class="report-empty">
        <div class="report-empty-card">
          <div class="report-empty-icon" aria-hidden="true">💬</div>
          <h3 class="report-empty-title">尚未生成行程报告</h3>
          <p class="report-empty-desc">
            在左侧<strong>自由对话</strong>中描述你的行程，AI 会追问补充信息。
            信息齐全后，右侧将生成行程穿搭文字报告。
          </p>
          <ul class="report-empty-steps">
            <li><span>1</span>用自然语言描述行程</li>
            <li><span>2</span>回答 AI 的追问</li>
            <li><span>3</span>右侧同步文字报告</li>
          </ul>
        </div>
      </div>

      <div v-else-if="store.chatCollecting" class="report-collecting">
        <div class="collecting-card">
          <div class="collecting-icon" aria-hidden="true">💬</div>
          <h3>对话收集中…</h3>
          <p>AI 正在通过对话收集行程信息，补齐后将自动生成报告</p>
          <div v-if="collectingHints.length" class="collecting-chips">
            <span
              v-for="(hint, i) in collectingHints"
              :key="i"
              class="chip"
              :class="{ missing: hint.missing }"
            >{{ hint.text }}</span>
          </div>
        </div>
        <div v-if="store.error" class="error-banner">{{ store.error }}</div>
      </div>

      <div v-else-if="store.chatGenerating" class="report-generating">
        <div class="generating-card">
          <div class="generating-spinner" aria-hidden="true" />
          <p>正在规划行程穿搭…</p>
          <p class="generating-sub">天气 / 小红书参考 / 穿搭分析可能需要 1–4 分钟</p>
        </div>
      </div>

      <template v-else-if="store.hasLiveReport">
        <div v-if="store.error" class="error-banner">{{ store.error }}</div>
        <TextReportView />
      </template>
    </template>
  </section>
</template>
