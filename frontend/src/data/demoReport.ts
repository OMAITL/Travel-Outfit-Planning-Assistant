import type { ProductCard } from "@/api/types";

export interface DemoDay {
  dateShort: string;
  dateLabel: string;
  weekday: string;
  weatherLine: string;
  spotChips: string[];
  tips: string[];
  reason: string;
  items: { label: string; text: string }[];
  scores: string[];
  sceneSpots: { id: string; label: string; sceneSub: string; sceneLabel: string }[];
}

export const DEMO_DAYS: DemoDay[] = [
  {
    dateShort: "6/5",
    dateLabel: "6月5日",
    weekday: "周五",
    weatherLine: "🌧 雨 16–27°C · 降水 60%",
    spotChips: ["洱海", "古城"],
    tips: [
      "昼夜温差大，建议洋葱式叠穿，方便中午脱外套",
      "可能降雨，备轻便雨衣或防水外套",
    ],
    reason:
      "洱海骑行需要防风防泼水的薄外套，内搭白色 T 恤 + 牛仔裤经典耐看；卡其色系与湖光山色呼应，拍照出片。",
    items: [
      { label: "上装", text: "白色棉质短袖 T 恤 + 浅卡其防水风衣" },
      { label: "下装", text: "蓝色直筒牛仔裤" },
      { label: "鞋", text: "白色帆布鞋（防泼水）" },
      { label: "配饰", text: "卡其棒球帽 · 米色斜挎包" },
    ],
    scores: ["风格 ★★★★☆", "舒适 ★★★★★", "出片 ★★★★☆", "配色 白·卡其·蓝"],
    sceneSpots: [
      {
        id: "erhai",
        label: "洱海廊道",
        sceneSub: "背景：洱海生态廊道",
        sceneLabel: "AI 生成 · 女 · 休闲风 · 洱海生态廊道",
      },
      {
        id: "gucheng",
        label: "大理古城",
        sceneSub: "背景：大理古城南门",
        sceneLabel: "AI 生成 · 女 · 休闲风 · 大理古城",
      },
    ],
  },
  {
    dateShort: "6/6",
    dateLabel: "6月6日",
    weekday: "周六",
    weatherLine: "☀ 晴 18–28°C · 降水 10%",
    spotChips: ["三塔", "古城"],
    tips: ["紫外线较强，注意防晒与遮阳帽", "午后偏热，内搭可略薄"],
    reason: "三塔与古城步行多，轻便透气上装 + 舒适鞋履；浅色系与石塔、白墙灰瓦更搭。",
    items: [
      { label: "上装", text: "米色亚麻衬衫 + 薄针织披肩" },
      { label: "下装", text: "白色阔腿长裤" },
      { label: "鞋", text: "米色乐福鞋" },
      { label: "配饰", text: "草编帽 · 墨镜" },
    ],
    scores: ["风格 ★★★★☆", "舒适 ★★★★☆", "出片 ★★★★★", "配色 米·白·棕"],
    sceneSpots: [
      {
        id: "santa",
        label: "崇圣寺三塔",
        sceneSub: "背景：三塔倒影",
        sceneLabel: "AI 生成 · 女 · 休闲风 · 崇圣寺三塔",
      },
      {
        id: "gucheng2",
        label: "大理古城",
        sceneSub: "背景：古城街巷",
        sceneLabel: "AI 生成 · 女 · 休闲风 · 大理古城",
      },
    ],
  },
  {
    dateShort: "6/7",
    dateLabel: "6月7日",
    weekday: "周日",
    weatherLine: "⛅ 多云 17–26°C",
    spotChips: ["洱海"],
    tips: ["湖边风大，外套防风", "备一双可走路的鞋"],
    reason: "洱海骑行日，运动休闲风；防风外套 + 束脚裤方便活动。",
    items: [
      { label: "上装", text: "灰色速干 T 恤 + 军绿工装外套" },
      { label: "下装", text: "黑色束脚运动裤" },
      { label: "鞋", text: "灰色跑鞋" },
      { label: "配饰", text: "运动腰包" },
    ],
    scores: ["风格 ★★★☆☆", "舒适 ★★★★★", "出片 ★★★★☆", "配色 灰·绿·黑"],
    sceneSpots: [
      {
        id: "erhai2",
        label: "洱海廊道",
        sceneSub: "背景：洱海日落",
        sceneLabel: "AI 生成 · 女 · 休闲风 · 洱海生态廊道",
      },
    ],
  },
];

export type ProductCategory = "top" | "bottom" | "shoes" | "acc";

export const DEMO_PRODUCTS: Record<ProductCategory, ProductCard[]> = {
  top: [
    {
      title: "女夏季轻薄防晒衬衫 休闲百搭",
      pic_url: "",
      price: 59.9,
      detail_url: "#",
      num_iid: "demo-top-1",
    },
    {
      title: "浅卡其防水风衣 中长款",
      pic_url: "",
      price: 168,
      detail_url: "#",
      num_iid: "demo-top-2",
    },
    {
      title: "白色棉质短袖 T 恤",
      pic_url: "",
      price: 49,
      detail_url: "#",
      num_iid: "demo-top-3",
    },
  ],
  bottom: [
    {
      title: "蓝色直筒牛仔裤 高腰",
      pic_url: "",
      price: 129,
      detail_url: "#",
      num_iid: "demo-bottom-1",
    },
    {
      title: "女亚麻阔腿裤 夏季透气",
      pic_url: "",
      price: 89,
      detail_url: "#",
      num_iid: "demo-bottom-2",
    },
  ],
  shoes: [
    {
      title: "白色帆布鞋 女 防泼水",
      pic_url: "",
      price: 98,
      detail_url: "#",
      num_iid: "demo-shoes-1",
    },
  ],
  acc: [
    {
      title: "卡其棒球帽 可调节",
      pic_url: "",
      price: 35,
      detail_url: "#",
      num_iid: "demo-acc-1",
    },
    {
      title: "米色斜挎包 轻便",
      pic_url: "",
      price: 78,
      detail_url: "#",
      num_iid: "demo-acc-2",
    },
  ],
};
