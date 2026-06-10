<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { usePlanningStore } from "@/stores/planning";
import { USE_API } from "@/config";

const store = usePlanningStore();
const draft = ref("");
const messagesEl = ref<HTMLElement | null>(null);

const messages = computed(() => store.state?.messages ?? []);

const lastAssistantIndex = computed(() => {
  const list = messages.value;
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].role === "assistant") return i;
  }
  return -1;
});

const showDoneCard = computed(
  () => store.hasLiveReport && !store.loading && messages.value.length > 0,
);

async function scrollToBottom() {
  await nextTick();
  const el = messagesEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}

watch(messages, () => scrollToBottom(), { deep: true });
watch(() => store.loading, () => scrollToBottom());

async function sendText(text: string) {
  const trimmed = text.trim();
  if (!trimmed || store.loading) return;
  await store.sendChat(trimmed, { useApi: USE_API });
  await scrollToBottom();
}

async function send() {
  const text = draft.value;
  draft.value = "";
  await sendText(text);
}

function quickReply(option: string) {
  draft.value = option;
  void send();
}

function showOptions(index: number, msg: { role: string; options?: string[] }) {
  return (
    msg.role === "assistant" &&
    !!msg.options?.length &&
    !store.loading &&
    index === lastAssistantIndex.value
  );
}

function onDoneCardClick() {
  store.highlightReportPanel();
  document.querySelector(".report-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
</script>

<template>
  <div class="chat-panel">
    <div ref="messagesEl" class="chat-messages">
      <p v-if="!messages.length" class="chat-hint">
        描述你的行程和穿搭场景，例如：7月10-12日去大理，想拍出片照片…
      </p>

      <template v-for="(msg, i) in messages" :key="i">
        <div class="chat-bubble" :class="msg.role">
          {{ msg.content }}
        </div>
        <div v-if="showOptions(i, msg)" class="chat-options">
          <button
            v-for="opt in msg.options"
            :key="opt"
            type="button"
            class="chat-option-btn"
            :disabled="store.loading"
            @click="quickReply(opt)"
          >
            {{ opt }}
          </button>
        </div>
      </template>

      <button
        v-if="showDoneCard"
        type="button"
        class="chat-done-card"
        @click="onDoneCardClick"
      >
        ✅ 整套穿搭报告已生成！<br />
        右侧已同步更新，可继续对话追问修改。
        <span class="chat-done-arrow">查看右侧报告 →</span>
      </button>
    </div>

    <div class="chat-input-row">
      <input
        v-model="draft"
        type="text"
        placeholder="描述行程或穿搭场景…"
        :disabled="store.loading"
        @keydown.enter.prevent="send"
      />
      <button class="btn-ghost" type="button" :disabled="store.loading" @click="send">
        发送
      </button>
    </div>
  </div>
</template>
