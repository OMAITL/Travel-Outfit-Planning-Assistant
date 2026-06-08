<script setup lang="ts">
import { computed, ref, watch } from "vue";
import AvoidMultiselect from "@/components/AvoidMultiselect.vue";
import CitySelect from "@/components/CitySelect.vue";
import PlanModeSection from "@/components/PlanModeSection.vue";
import SpotMultiselect from "@/components/SpotMultiselect.vue";
import StyleMultiselect from "@/components/StyleMultiselect.vue";
import { usePlanningStore } from "@/stores/planning";
import { USE_API } from "@/config";
import { toIsoDate, addDays } from "@/utils/format";

const store = usePlanningStore();

const today = new Date();
const startDate = ref(toIsoDate(addDays(today, 1)));
const endDate = ref(toIsoDate(addDays(today, 3)));
const styleTags = ref<string[]>([]);
const avoidItems = ref<string[]>([]);
const categoryBudgets = ref({
  top: 200,
  bottom: 200,
  shoes: 250,
  acc: 150,
});
const gender = ref("女");
const heightCm = ref(165);
const weightKg = ref(55);
const bodyType = ref("不限");
const skinTone = ref("不限");
const prefsOpen = ref(true);

const categorySum = computed(() =>
  Object.values(categoryBudgets.value).reduce((sum, n) => sum + (n || 0), 0),
);

function resolveBudgets() {
  const values = Object.values(categoryBudgets.value);
  return {
    budget_per_item: Math.max(...values, 0),
    budget_total: categorySum.value,
    budget_by_category: { ...categoryBudgets.value },
  };
}

watch(
  [startDate, endDate],
  () => {
    if (endDate.value >= startDate.value) {
      store.rebuildDaysFromDates(startDate.value, endDate.value);
    }
  },
  { immediate: true },
);

watch(
  () => store.selectedSpotIds,
  () => {
    if (store.planMode === "auto") store.autoAssignDays();
  },
  { deep: true },
);

function onCityChange(key: string) {
  store.setCityKey(key);
}

function onSubmit() {
  const city = store.currentCity;
  if (!city) return;
  if (endDate.value < startDate.value) {
    store.error = "返回日期不能早于出发日期";
    return;
  }
  if (!store.selectedSpotIds.length) {
    store.error = "请至少选择一个景点";
    return;
  }
  if (!styleTags.value.length) {
    store.error = "请至少选择一个风格标签";
    return;
  }
  store.error = null;
  if (store.planMode === "auto") store.autoAssignDays();
  const budgets = resolveBudgets();
  const dailySpotNames = store.days.map((day) =>
    day.spotIds
      .map((id) => store.getSpotById(id)?.name)
      .filter(Boolean) as string[],
  );
  store.submitTrip(
    {
      destination: city.name,
      start_date: startDate.value,
      end_date: endDate.value,
      gender: gender.value,
      styles: [...styleTags.value],
      activities: ["拍照", "逛街"],
      spot_names: store.selectedSpotIds
        .map((id) => store.getSpotById(id)?.name)
        .filter(Boolean) as string[],
      plan_mode: store.planMode,
      daily_spot_names: dailySpotNames,
      budget_per_item: budgets.budget_per_item,
      budget_total: budgets.budget_total,
      budget_by_category: budgets.budget_by_category,
      height_cm: heightCm.value,
      weight_kg: weightKg.value,
      body_type: bodyType.value,
      skin_tone: skinTone.value,
      avoid_items: [...avoidItems.value],
    },
    { useApi: USE_API },
  );
}
</script>

<template>
  <div class="trip-form">
    <CitySelect
      :cities="store.cities"
      :model-value="store.currentCityKey"
      @update:model-value="onCityChange"
    />

    <SpotMultiselect
      v-if="store.currentCity"
      v-model="store.selectedSpotIds"
      :spots="store.currentCity.spots"
      :city-name="store.currentCity.name"
    />

    <div class="row2 date-row">
      <div>
        <label class="field-label">出发</label>
        <input v-model="startDate" type="date" />
      </div>
      <div>
        <label class="field-label">返回</label>
        <input v-model="endDate" type="date" />
      </div>
    </div>

    <PlanModeSection />

    <StyleMultiselect v-model="styleTags" />

    <div class="budget-block">
      <label class="field-label">单品预算 (¥)</label>
      <p class="budget-hint">为每类单品分别设置上限，搜商品时按品类匹配</p>
      <div class="row2">
        <div>
          <label class="field-label field-label-sub">上装</label>
          <input v-model.number="categoryBudgets.top" type="number" min="0" step="50" />
        </div>
        <div>
          <label class="field-label field-label-sub">下装</label>
          <input v-model.number="categoryBudgets.bottom" type="number" min="0" step="50" />
        </div>
      </div>
      <div class="row2">
        <div>
          <label class="field-label field-label-sub">鞋</label>
          <input v-model.number="categoryBudgets.shoes" type="number" min="0" step="50" />
        </div>
        <div>
          <label class="field-label field-label-sub">配饰</label>
          <input v-model.number="categoryBudgets.acc" type="number" min="0" step="20" />
        </div>
      </div>
      <p class="budget-sum-line">合计约 ¥{{ categorySum }} / 套</p>
    </div>

    <details class="prefs-panel" :open="prefsOpen">
      <summary @click.prevent="prefsOpen = !prefsOpen">体型与穿搭偏好</summary>
      <div class="prefs-body">
        <div class="row2">
          <div>
            <label class="field-label">身高 (cm)</label>
            <input v-model.number="heightCm" type="number" />
          </div>
          <div>
            <label class="field-label">体重 (kg)</label>
            <input v-model.number="weightKg" type="number" />
          </div>
        </div>
        <div class="row2">
          <div>
            <label class="field-label">性别</label>
            <select v-model="gender">
              <option>女</option>
              <option>男</option>
              <option>不限</option>
            </select>
          </div>
          <div>
            <label class="field-label">肤色</label>
            <select v-model="skinTone">
              <option>不限</option>
              <option>偏白</option>
              <option>自然</option>
              <option>小麦色</option>
              <option>偏深</option>
            </select>
          </div>
        </div>
        <label class="field-label">体型</label>
        <select v-model="bodyType">
          <option>不限</option>
          <option>偏瘦</option>
          <option>标准</option>
          <option>微胖</option>
          <option>健壮</option>
          <option>苹果型</option>
          <option>梨型</option>
          <option>H型</option>
        </select>

        <AvoidMultiselect v-model="avoidItems" />
      </div>
    </details>

    <button class="btn-primary" type="button" @click="onSubmit">开始规划穿搭</button>
  </div>
</template>
