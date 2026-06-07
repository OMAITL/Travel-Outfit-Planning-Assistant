export interface Spot {
  id: string;
  emoji: string;
  name: string;
  tag: string;
}

export interface City {
  key: string;
  name: string;
  spots: Spot[];
  default_spot_ids: string[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface DailyWeather {
  date: string;
  temp_min: number;
  temp_max: number;
  condition: string;
  rain_prob?: number | null;
  estimated?: boolean;
}

export interface DailyOutfit {
  date: string;
  outfit_summary: string;
  search_keywords: string[];
  recommendation_reason: string;
}

export interface ProductCard {
  title: string;
  pic_url: string;
  price: number;
  detail_url: string;
  num_iid?: string | null;
  trip_date?: string | null;
  category?: "top" | "bottom" | "shoes" | "acc" | null;
  item_label?: string | null;
  item_text?: string | null;
  within_budget?: boolean;
  size_hint?: string | null;
}

export interface OutfitItemView {
  label: string;
  text: string;
}

export interface ProductItemGroup {
  id: string;
  label: string;
  item_text: string;
  category: string;
  products: ProductCard[];
}

export interface StyleReference {
  note_id: string;
  title: string;
  cover_url: string;
  image_urls: string[];
  note_url: string;
  user_name?: string | null;
  liked_count?: number | null;
  search_keyword?: string | null;
}

export interface DailyReportCard {
  date: string;
  spot_names?: string[];
  morning?: string | null;
  afternoon?: string | null;
  evening?: string | null;
  weather: DailyWeather | null;
  outfit: DailyOutfit | null;
  outfit_items?: OutfitItemView[];
  product_groups?: ProductItemGroup[];
  look_image_url: string | null;
  look_images_by_spot?: Record<string, string>;
  style_references?: StyleReference[];
  products: ProductCard[];
  degraded?: boolean;
}

export interface TravelReport {
  destination: string;
  start_date: string;
  end_date: string;
  trip_days: number;
  daily_cards: DailyReportCard[];
  summary?: string | null;
  disclaimer: string;
}

export type PlanningPhase = "collecting" | "planning" | "done";

export interface XhsQueryDebugEntry {
  trip_date: string;
  spot: string;
  profile: Record<string, unknown>;
  final_query: string;
  base_tokens: { token: string; rule: string }[];
  expanded_queries: string[];
  compile_source: string;
  filtered_avoid: number;
  filtered_non_outfit: number;
  filtered_low_likes: number;
  notes_kept: number;
}

export interface PlanningState {
  messages: ChatMessage[];
  trip: Record<string, unknown> | null;
  weather: DailyWeather[];
  outfits: DailyOutfit[];
  look_images: { date: string; image_url: string; spot_name?: string | null; prompt?: string | null }[];
  products: ProductCard[];
  xhs_query_debug?: XhsQueryDebugEntry[];
  report: TravelReport | null;
  phase: PlanningPhase;
  errors: string[];
  trace: { agent: string; message: string; level?: string }[];
}

export interface TripFormPayload {
  destination: string;
  start_date: string;
  end_date: string;
  gender: string;
  styles: string[];
  activities: string[];
  spot_names: string[];
  plan_mode?: "auto" | "manual";
  daily_spot_names?: string[][];
  budget_per_item?: number | null;
  budget_total?: number | null;
  budget_by_category?: {
    top: number;
    bottom: number;
    shoes: number;
    acc: number;
  };
  height_cm?: number | null;
  weight_kg?: number | null;
  body_type?: string | null;
  skin_tone?: string | null;
  avoid_items: string[];
}

export interface PlanRequest {
  message?: string;
  trip?: TripFormPayload;
  state?: PlanningState | null;
}

export interface PlanResponse {
  state: PlanningState;
}

export interface CatalogResponse {
  cities: City[];
}
