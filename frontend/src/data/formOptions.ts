export const STYLE_OPTIONS = [
  "休闲",
  "简约",
  "文艺",
  "复古",
  "森系",
  "甜美",
  "温柔",
  "知性",
  "通勤",
  "商务休闲",
  "运动休闲",
  "街头",
  "潮酷",
  "民族风",
  "度假风",
  "海岛风",
  "户外机能",
  "法式",
  "韩系",
  "日系",
  "学院风",
  "轻奢",
  "极简",
  "田园",
  "波西米亚",
  "新中式",
  "辣妹",
  "Y2K",
  "老钱风",
  "山系",
  "城市户外",
  "拍照出片",
  "舒适优先",
] as const;

export interface AvoidOption {
  id: string;
  label: string;
}

export const SKIN_TONE_OPTIONS = [
  "不限",
  "偏白",
  "自然",
  "小麦色",
  "偏深",
] as const;

export const AVOID_OPTIONS: AvoidOption[] = [
  { id: "no_crop", label: "不露腰 / 短款上装" },
  { id: "no_shorts", label: "不穿短裤" },
  { id: "no_skirt", label: "不穿裙装" },
  { id: "no_hat", label: "不要帽子" },
  { id: "no_heel", label: "不要高跟鞋" },
  { id: "no_tight", label: "避免紧身" },
  { id: "no_dark", label: "不要深色" },
  { id: "no_pattern", label: "不要大面积印花" },
  { id: "no_wool", label: "不要羊毛 / 厚毛衣" },
  { id: "no_denim", label: "不要牛仔" },
  { id: "no_leather", label: "不要皮衣" },
  { id: "no_synthetic", label: "避免化纤材质" },
  { id: "no_sleeveless", label: "不要无袖" },
  { id: "no_low_waist", label: "不要低腰裤" },
  { id: "no_bright", label: "不要荧光色" },
  { id: "no_logo", label: "不要大 Logo" },
];
