<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { usePlanningStore } from "@/stores/planning";
import {
  filterSessionHistory,
  formatHistoryTime,
  formPreviewText,
  reportPreviewText,
  type HistoryFilter,
  type SessionRecord,
} from "@/utils/sessionHistory";

const store = usePlanningStore();
const filter = ref<HistoryFilter>("all");
const selectedId = ref<string | null>(null);

const open = computed(() => store.historyOpen);

const filteredRecords = computed(() =>
  filterSessionHistory(store.sessionHistory, filter.value),
);

const selectedRecord = computed(() => {
  if (!selectedId.value) return filteredRecords.value[0] ?? null;
  return (
    filteredRecords.value.find((r) => r.id === selectedId.value) ??
    filteredRecords.value[0] ??
    null
  );
});

const previewMessages = computed(() => {
  const msgs = selectedRecord.value?.state?.messages ?? [];
  return msgs.slice(-6);
});

const previewReport = computed(() => {
  const rec = selectedRecord.value;
  if (!rec?.state) return "暂无报告内容";
  if (rec.mode === "form") return formPreviewText(rec.state);
  return reportPreviewText(rec.state);
});

const isFormRecord = computed(() => selectedRecord.value?.mode === "form");

watch(open, (isOpen) => {
  if (!isOpen) return;
  filter.value = "all";
  const active = store.activeSessionId;
  const list = store.sessionHistory;
  if (active && list.some((r) => r.id === active)) {
    selectedId.value = active;
  } else {
    selectedId.value = list[0]?.id ?? null;
  }
});

watch(open, (isOpen) => {
  if (!isOpen) return;
  const onEscape = (event: KeyboardEvent) => {
    if (event.key === "Escape") store.closeHistoryDrawer();
  };
  window.addEventListener("keydown", onEscape);
  return () => window.removeEventListener("keydown", onEscape);
});

watch(filteredRecords, (list) => {
  if (!list.length) {
    selectedId.value = null;
    return;
  }
  if (!list.some((r) => r.id === selectedId.value)) {
    selectedId.value = list[0].id;
  }
});

function modeLabel(mode: SessionRecord["mode"]): string {
  return mode === "chat" ? "对话" : "表单";
}

function selectRecord(id: string) {
  selectedId.value = id;
}

function restoreSession() {
  const id = selectedRecord.value?.id;
  if (!id) return;
  store.loadSession(id);
  store.closeHistoryDrawer();
}

function deleteRecord() {
  const id = selectedRecord.value?.id;
  if (!id) return;
  store.deleteSession(id);
  selectedId.value = filteredRecords.value[0]?.id ?? null;
}

function onBackdropClick() {
  store.closeHistoryDrawer();
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="history-drawer-root">
      <div class="history-drawer-backdrop" @click="onBackdropClick" />

      <aside class="history-drawer" role="dialog" aria-label="历史记录">
        <div class="history-drawer-head">
          <h3>历史记录</h3>
          <button type="button" class="history-drawer-close" @click="store.closeHistoryDrawer()">
            ×
          </button>
        </div>

        <div class="history-drawer-filters">
          <button
            type="button"
            :class="{ active: filter === 'all' }"
            @click="filter = 'all'"
          >
            全部
          </button>
          <button
            type="button"
            :class="{ active: filter === 'form' }"
            @click="filter = 'form'"
          >
            📋 快速填写
          </button>
          <button
            type="button"
            :class="{ active: filter === 'chat' }"
            @click="filter = 'chat'"
          >
            💬 自由对话
          </button>
        </div>

        <div v-if="!filteredRecords.length" class="history-drawer-empty">
          <p>暂无历史记录</p>
          <p class="sub">完成一次规划或对话后会自动保存</p>
        </div>

        <div v-else class="history-drawer-body">
          <div class="history-drawer-list">
            <button
              v-for="rec in filteredRecords"
              :key="rec.id"
              type="button"
              class="hist-item"
              :class="{ selected: rec.id === selectedRecord?.id }"
              @click="selectRecord(rec.id)"
            >
              <div class="hist-item-head">
                <span class="mode-tag" :data-mode="rec.mode">{{ modeLabel(rec.mode) }}</span>
                <span class="hist-time">{{ formatHistoryTime(rec.updatedAt) }}</span>
              </div>
              <div class="hist-title">{{ rec.title }}</div>
              <div class="hist-sub">{{ rec.status }}</div>
            </button>
          </div>

          <div v-if="selectedRecord" class="history-drawer-preview">
            <template v-if="isFormRecord">
              <h4>表单行程</h4>
              <div class="preview-report form-preview">{{ previewReport }}</div>
            </template>
            <template v-else>
              <h4>对话摘要</h4>
              <div v-if="previewMessages.length" class="preview-chat">
                <div
                  v-for="(msg, i) in previewMessages"
                  :key="i"
                  class="bubble"
                  :class="msg.role"
                >
                  {{ msg.content }}
                </div>
              </div>
              <p v-else class="preview-empty">暂无对话内容</p>
            </template>

            <h4>{{ isFormRecord ? "图文报告" : "关联报告" }}</h4>
            <div class="preview-report">{{ reportPreviewText(selectedRecord.state) }}</div>

            <div class="history-drawer-actions">
              <button type="button" class="btn-primary-sm" @click="restoreSession">
                恢复此会话
              </button>
              <button type="button" class="btn-outline-sm danger" @click="deleteRecord">
                删除
              </button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
