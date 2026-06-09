"""User body profile — BMI, plus-size hints for image gen & commerce search."""

from __future__ import annotations

from dataclasses import dataclass

from src.graph.state import TripPreferences


@dataclass(frozen=True)
class BodyProfile:
    height_cm: float | None = None
    weight_kg: float | None = None
    body_type: str | None = None
    skin_tone: str | None = None
    gender: str | None = None

    @classmethod
    def from_preferences(cls, prefs: TripPreferences | None) -> BodyProfile:
        if prefs is None:
            return cls()
        return cls(
            height_cm=prefs.height_cm,
            weight_kg=prefs.weight_kg,
            body_type=prefs.body_type,
            skin_tone=prefs.skin_tone,
            gender=prefs.gender,
        )

    @property
    def bmi(self) -> float | None:
        if not self.height_cm or self.height_cm <= 0:
            return None
        if not self.weight_kg or self.weight_kg <= 0:
            return None
        h_m = self.height_cm / 100.0
        return self.weight_kg / (h_m * h_m)

    @property
    def is_plus_size(self) -> bool:
        bmi = self.bmi
        if bmi is not None and bmi >= 28:
            return True
        body = (self.body_type or "").strip()
        return body in {"微胖", "健壮", "苹果型"}

    @property
    def is_heavyweight(self) -> bool:
        bmi = self.bmi
        return bmi is not None and bmi >= 32

    def commerce_size_keywords(self) -> list[str]:
        """Extra Taobao / XHS tokens for size-aware search."""
        keywords: list[str] = []
        if self.is_heavyweight:
            keywords.extend(["大码", "加肥加大"])
        elif self.is_plus_size:
            keywords.append("大码")
        label = body_type_search_token(self.body_type)
        if label and label not in keywords:
            keywords.append(label)
        return keywords

    def xhs_body_tokens(self) -> list[str]:
        """At most two body-related tokens for XHS queries (legacy)."""
        tokens: list[str] = []
        if self.is_plus_size:
            tokens.append("大码")
        label = body_type_search_token(self.body_type)
        if label:
            tokens.append(label)
        elif self.is_heavyweight:
            tokens.append("加肥加大")
        return tokens[:2]

    def xhs_search_body_tokens(self) -> list[str]:
        """小红书搜索专用身材标签 — 避免程序标签如「健壮」."""
        tokens: list[str] = []
        gender = (self.gender or "").strip()

        if self.is_heavyweight:
            if gender == "男":
                tokens.extend(["大码男生", "大码"])
            else:
                tokens.extend(["大码女生", "150斤女生"])
        elif self.is_plus_size:
            if gender == "男":
                tokens.append("微胖男生")
            else:
                tokens.extend(["微胖女生", "大码女生"])

        label = body_type_search_token(self.body_type)
        if label and label not in {"健壮", "偏瘦", "标准", "无", "不限"}:
            if label not in tokens:
                tokens.append(label)

        return tokens[:2]

    def image_subject_zh(self) -> str:
        """Natural-language model description for Jimeng Chinese prompts."""
        gender = (self.gender or "").strip()
        if gender == "男":
            role = "成年男性"
        elif gender == "女":
            role = "成年女性"
        else:
            role = "成年游客"

        traits: list[str] = []
        if self.height_cm and self.height_cm > 0:
            traits.append(f"身高约{int(self.height_cm)}厘米")
        if self.weight_kg and self.weight_kg > 0 and self.bmi and self.bmi >= 24:
            traits.append(f"体重约{int(self.weight_kg)}公斤")

        if self.is_heavyweight:
            traits.append("大码丰满身材")
            traits.append("体型真实自然、并非时装模特的极瘦体型")
        elif self.is_plus_size:
            traits.append("微胖丰满身材")
            traits.append("真实自然的体型比例")

        body = (self.body_type or "").strip()
        if body == "健壮":
            traits.append("健壮结实的体格")
        elif body == "苹果型":
            traits.append("苹果型身材（腰腹较丰满）")
        elif body == "梨型":
            traits.append("梨形身材（下半身较丰满）")
        elif body == "H型":
            traits.append("H型直筒身材")

        skin = (self.skin_tone or "").strip()
        if skin and skin not in {"不限", "自然", "自然色"}:
            traits.append(f"{skin}肤色")

        if traits:
            return f"一位{'、'.join([role, *traits])}"
        return f"一位{role}游客"

    def image_negative_extra(self) -> str:
        """Append to negative prompt when plus-size user should not get thin models."""
        if not self.is_plus_size:
            return ""
        return (
            "thin model, underweight, skinny, extremely slim, 极瘦, 骨感, 纸片人, "
            "时装模特身材, 过度修图瘦身"
        )

    def stylist_constraints_zh(self) -> str:
        """Short bullet for stylist LLM context."""
        lines: list[str] = []
        if self.height_cm:
            lines.append(f"身高 {int(self.height_cm)}cm")
        if self.weight_kg:
            lines.append(f"体重 {int(self.weight_kg)}kg")
        if self.bmi:
            lines.append(f"BMI≈{self.bmi:.1f}")
        if self.body_type and self.body_type not in {"不限"}:
            lines.append(f"体型 {self.body_type}")
        if self.skin_tone and self.skin_tone not in {"不限", "自然", "自然色"}:
            lines.append(f"肤色 {self.skin_tone}")
        if self.is_plus_size:
            lines.append(
                "必须推荐真正适合大码/微胖体型的单品（宽松度、遮肉、垂坠、A字/直筒版型），"
                "search_keywords 须含「大码」或「加肥加大」等可搜到的尺码词"
            )
        return "；".join(lines)


def body_type_search_token(body_type: str | None) -> str:
    value = (body_type or "").strip()
    if not value or value in {"不限", "标准", "无"}:
        return ""
    mapping = {
        "梨型": "梨形",
        "梨形": "梨形",
        "苹果型": "苹果型",
        "H型": "H型",
        "h型": "H型",
        "微胖": "微胖",
        "健壮": "健壮",
        "偏瘦": "偏瘦",
    }
    return mapping.get(value, value)


def infer_size_hint(
    height_cm: float | None,
    weight_kg: float | None,
    gender: str | None = None,
    *,
    body_type: str | None = None,
) -> str:
    """Return Taobao-friendly size token, e.g. '4XL 165cm 大码'."""
    profile = BodyProfile(
        height_cm=height_cm,
        weight_kg=weight_kg,
        body_type=body_type,
        gender=gender,
    )
    if not profile.height_cm or profile.height_cm <= 0:
        return ""

    h = int(profile.height_cm)
    w = int(profile.weight_kg) if profile.weight_kg and profile.weight_kg > 0 else None
    bmi = profile.bmi

    if h < 158:
        letter = "S"
    elif h < 165:
        letter = "M"
    elif h < 172:
        letter = "L"
    elif h < 178:
        letter = "XL"
    else:
        letter = "XXL"

    size_order = ["S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL"]

    def bump(steps: int) -> None:
        nonlocal letter
        try:
            idx = size_order.index(letter)
        except ValueError:
            idx = 2
        letter = size_order[min(idx + steps, len(size_order) - 1)]

    if bmi is not None:
        if bmi >= 35:
            letter = "5XL"
        elif bmi >= 32:
            letter = "4XL"
        elif bmi >= 28:
            bump(2)
            if size_order.index(letter) < size_order.index("3XL"):
                letter = "3XL"
        elif bmi >= 24:
            bump(1)
    elif profile.is_plus_size:
        bump(1)

    parts = [letter, f"{h}cm"]
    if profile.is_plus_size:
        parts.append("大码")
    if profile.is_heavyweight:
        parts.append("加肥加大")

    g = (gender or "").strip()
    if g == "男":
        return " ".join(parts)
    return " ".join(parts)
