import type { City } from "@/api/types";

/** 热门城市首字母（用于分组排序） */
export const CITY_INITIAL: Record<string, string> = {
  dali: "D",
  lijiang: "L",
  chengdu: "C",
  sanya: "S",
  tokyo: "D",
};

export const STATIC_CITIES: City[] = [
  {
    key: "dali",
    name: "大理",
    default_spot_ids: ["erhai", "gucheng"],
    spots: [
      { id: "erhai", emoji: "🌊", name: "洱海生态廊道", tag: "拍照 · 骑行" },
      { id: "gucheng", emoji: "🏯", name: "大理古城", tag: "逛街 · 人文" },
      { id: "santa", emoji: "🗼", name: "崇圣寺三塔", tag: "观光 · 出片" },
      { id: "cangshan", emoji: "⛰️", name: "苍山索道", tag: "徒步 · 温差大" },
      { id: "shuanglang", emoji: "🏘️", name: "双廊古镇", tag: "海景 · 慢生活" },
      { id: "xizhou", emoji: "🌾", name: "喜洲古镇", tag: "麦浪 · 拍照" },
    ],
  },
  {
    key: "lijiang",
    name: "丽江",
    default_spot_ids: ["gucheng_lj", "yulong"],
    spots: [
      { id: "gucheng_lj", emoji: "🏯", name: "丽江古城", tag: "逛街 · 夜景" },
      { id: "yulong", emoji: "🏔️", name: "玉龙雪山", tag: "雪山 · 防寒" },
      { id: "lashi", emoji: "🌅", name: "拉市海", tag: "骑马 · 湿地" },
    ],
  },
  {
    key: "chengdu",
    name: "成都",
    default_spot_ids: ["kuanzhai", "panda"],
    spots: [
      { id: "kuanzhai", emoji: "🏮", name: "宽窄巷子", tag: "逛街 · 美食" },
      { id: "panda", emoji: "🐼", name: "大熊猫基地", tag: "亲子 · 户外" },
      { id: "jinli", emoji: "🏯", name: "锦里古街", tag: "夜景 · 人文" },
    ],
  },
  {
    key: "sanya",
    name: "三亚",
    default_spot_ids: ["yalong", "tianya"],
    spots: [
      { id: "yalong", emoji: "🏖️", name: "亚龙湾", tag: "海滩 · 度假" },
      { id: "tianya", emoji: "🌅", name: "天涯海角", tag: "打卡 · 海景" },
      { id: "wuzhizhou", emoji: "🤿", name: "蜈支洲岛", tag: "潜水 · 防晒" },
    ],
  },
  {
    key: "tokyo",
    name: "东京",
    default_spot_ids: ["shibuya", "sensoji"],
    spots: [
      { id: "shibuya", emoji: "🚶", name: "涩谷十字路口", tag: "街拍 · 都市" },
      { id: "sensoji", emoji: "⛩️", name: "浅草寺", tag: "人文 · 和服" },
      { id: "skytree", emoji: "🗼", name: "东京晴空塔", tag: "观光 · 夜景" },
    ],
  },
];

export function cityInitial(key: string, name: string): string {
  return CITY_INITIAL[key] ?? name.charAt(0).toUpperCase();
}

export function sortCitiesByInitial(cities: City[]): City[] {
  return [...cities].sort((a, b) => {
    const ia = cityInitial(a.key, a.name);
    const ib = cityInitial(b.key, b.name);
    if (ia !== ib) return ia.localeCompare(ib, "en");
    return a.name.localeCompare(b.name, "zh");
  });
}

export function groupCitiesByInitial(cities: City[]): { letter: string; items: City[] }[] {
  const sorted = sortCitiesByInitial(cities);
  const map = new Map<string, City[]>();
  for (const c of sorted) {
    const letter = cityInitial(c.key, c.name);
    if (!map.has(letter)) map.set(letter, []);
    map.get(letter)!.push(c);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b, "en"))
    .map(([letter, items]) => ({ letter, items }));
}
