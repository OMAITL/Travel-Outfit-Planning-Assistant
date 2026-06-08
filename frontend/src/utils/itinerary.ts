/** User-selected spots — mirrors backend itinerary_rules planning modes. */

import type { City } from "@/api/types";

export interface DaySlotPlan {
  spotIds: string[];
  morningId?: string;
  afternoonId?: string;
  eveningId?: string;
}

export function buildPoiPoolIds(userSpotIds: string[]): string[] {
  const pool: string[] = [];
  const seen = new Set<string>();
  for (const id of userSpotIds) {
    if (!id || seen.has(id)) continue;
    pool.push(id);
    seen.add(id);
  }
  return pool;
}

function contiguousSlotAssignment(pool: string[], slotCount: number): string[] {
  if (slotCount <= 0) return [];
  if (!pool.length) return Array(slotCount).fill("");

  const base = Math.floor(slotCount / pool.length);
  const extra = slotCount % pool.length;
  const assigned: string[] = [];
  pool.forEach((spot, index) => {
    const block = base + (index < extra ? 1 : 0);
    for (let i = 0; i < block; i++) assigned.push(spot);
  });
  return assigned.slice(0, slotCount);
}

function planEqualDays(pool: string[], dayCount: number): DaySlotPlan[] {
  return Array.from({ length: dayCount }, (_, i) => ({
    spotIds: pool[i] ? [pool[i]] : [],
    morningId: undefined,
    afternoonId: undefined,
    eveningId: undefined,
  }));
}

function planPackDays(pool: string[], dayCount: number): DaySlotPlan[] {
  const plans: DaySlotPlan[] = Array.from({ length: dayCount }, () => ({ spotIds: [] }));
  pool.forEach((id, index) => {
    const dayIdx = index % dayCount;
    const plan = plans[dayIdx];
    if (!plan.spotIds.includes(id)) plan.spotIds.push(id);
  });
  plans.forEach((plan) => {
    if (plan.spotIds.length > 1) {
      plan.morningId = plan.spotIds[0];
      plan.afternoonId = plan.spotIds[1];
      if (plan.spotIds.length > 2) plan.eveningId = plan.spotIds[2];
    }
  });
  return plans;
}

export function distributePoiPoolIds(pool: string[], dayCount: number): DaySlotPlan[] {
  if (dayCount <= 0) return [];
  if (pool.length === dayCount) return planEqualDays(pool, dayCount);
  if (pool.length > dayCount) return planPackDays(pool, dayCount);

  const timeline: Array<{ day: number; period: "morning" | "afternoon" }> = [];
  for (let day = 0; day < dayCount; day++) {
    timeline.push({ day, period: "morning" });
    timeline.push({ day, period: "afternoon" });
  }

  const assignments = contiguousSlotAssignment(pool, timeline.length);
  const plans: DaySlotPlan[] = Array.from({ length: dayCount }, () => ({ spotIds: [] }));

  timeline.forEach(({ day, period }, index) => {
    const spotId = assignments[index];
    if (!spotId) return;
    const plan = plans[day];
    if (period === "morning") plan.morningId = spotId;
    else plan.afternoonId = spotId;
    if (!plan.spotIds.includes(spotId)) plan.spotIds.push(spotId);
  });

  return plans;
}

export function planAutoItineraryIds(userSpotIds: string[], _city: City, dayCount: number): DaySlotPlan[] {
  const pool = buildPoiPoolIds(userSpotIds);
  return distributePoiPoolIds(pool, dayCount);
}
