<script setup lang="ts">
import { onMounted } from "vue";
import ChatPanel from "@/components/ChatPanel.vue";
import ReportPanel from "@/components/ReportPanel.vue";
import TripFormPanel from "@/components/TripFormPanel.vue";
import { fetchCities } from "@/api/client";
import { STATIC_CITIES } from "@/data/cities";
import { usePlanningStore } from "@/stores/planning";

const store = usePlanningStore();

onMounted(async () => {
  store.setCities(STATIC_CITIES);
  try {
    const data = await fetchCities();
    store.setCities(data.cities);
  } catch {
    /* static catalog is enough for UI demo */
  }
});
</script>

<template>
  <div>
    <header class="hero">
      <div class="hero-inner">
        <div>
          <h1>旅行穿搭规划助手</h1>
          <p>AI 旅游穿搭与淘宝导购 · 按景点定制出片造型</p>
        </div>
      </div>
    </header>

    <div v-if="store.loading" class="loading-overlay">
      <p>正在规划行程穿搭…</p>
      <p style="font-size: 0.8rem">天气 / 穿搭 / 生图 / 商品匹配可能需要 1–3 分钟</p>
    </div>

    <main class="shell">
      <aside class="panel">
        <h2>行程输入</h2>
        <div class="form-tabs">
          <button
            type="button"
            :class="{ active: store.inputTab === 'form' }"
            @click="store.inputTab = 'form'"
          >
            📋 快速填写
          </button>
          <button
            type="button"
            :class="{ active: store.inputTab === 'chat' }"
            @click="store.inputTab = 'chat'"
          >
            💬 自由对话
          </button>
        </div>
        <TripFormPanel v-if="store.inputTab === 'form'" />
        <ChatPanel v-else />
      </aside>
      <ReportPanel />
    </main>
  </div>
</template>
