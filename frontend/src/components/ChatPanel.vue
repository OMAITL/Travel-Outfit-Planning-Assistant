<script setup lang="ts">
import { ref } from "vue";
import { usePlanningStore } from "@/stores/planning";
import { USE_API } from "@/config";

const store = usePlanningStore();
const draft = ref("");

async function send() {
  const text = draft.value;
  draft.value = "";
  await store.sendChat(text, { useApi: USE_API });
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-messages">
      <p
        v-if="!store.state?.messages?.length"
        style="color: var(--muted); font-size: 0.85rem"
      >
        也可直接描述行程，例如：7月10-12日去大理，休闲风…
      </p>
      <div
        v-for="(msg, i) in store.state?.messages ?? []"
        :key="i"
        class="chat-bubble"
        :class="msg.role"
      >
        {{ msg.content }}
      </div>
    </div>
    <div class="chat-input-row">
      <input
        v-model="draft"
        type="text"
        placeholder="描述你的行程…"
        :disabled="store.loading"
        @keydown.enter.prevent="send"
      />
      <button class="btn-ghost" type="button" :disabled="store.loading" @click="send">发送</button>
    </div>
  </div>
</template>
