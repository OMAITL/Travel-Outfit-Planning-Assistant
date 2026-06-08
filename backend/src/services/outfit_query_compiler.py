"""
Outfit Query Compiler — constrained semantic retrieval for Xiaohongshu search.

Step 1 (Profile): structured user prefs (from trip form / LLM trip node).
Step 2 (Compile): deterministic keyword assembly via code rules.
Step 3 (Expand): optional LLM synonym queries (expansion only, not decisions).
Step 4 (Filter): rule-based negative constraint filtering on search results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.graph.state import TripPreferences
from src.services.body_profile import BodyProfile
from src.services.xhs_keywords import (
    avoid_match_tokens,
    body_type_search_label,
    gender_search_label,
    height_search_label,
    season_hint_for_month,
    spot_search_label,
    style_search_label,
)
from src.tools.justone_xhs import XhsNoteSummary

# Semantic expansions for negative constraints (hybrid filter layer).
_SEMANTIC_NEGATIVE: dict[str, tuple[str, ...]] = {
    "暴露": ("比基尼", "超短裙", "超短", "低胸", "露脐", "紧身低胸", "性感吊带"),
    "露背": ("露背", "大露背", "露背装", "吊带露背"),
    "紧身": ("紧身", "修身紧身", "包臀"),
    "高跟": ("高跟鞋", "细高跟", "尖头高跟"),
    "裙": ("连衣裙", "半裙", "长裙", "短裙", "百褶裙"),
    "牛仔": ("牛仔裤", "牛仔裙", "牛仔外套", "牛仔短裤"),
}


class QueryToken(BaseModel):
    token: str
    rule: str


class OutfitSearchProfile(BaseModel):
    """Structured profile for XHS outfit search (Step 1 output)."""

    destination: str
    spot: str
    trip_date: date | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    body_type: str | None = None
    styles: list[str] = Field(default_factory=list)
    gender: str | None = None
    negative_constraints: list[str] = Field(default_factory=list)


class CompiledOutfitQuery(BaseModel):
    """Rule-compiled query with debug metadata (Step 2 output)."""

    profile: OutfitSearchProfile
    base_tokens: list[QueryToken] = Field(default_factory=list)
    final_query: str = ""
    expanded_queries: list[str] = Field(default_factory=list)
    source: str = "rule"


class ExpandQueriesOutput(BaseModel):
    queries: list[str] = Field(default_factory=list, max_length=2)


@dataclass
class XhsFilterStats:
    avoid: int = 0
    non_outfit: int = 0
    low_likes: int = 0


def profile_from_preferences(
    prefs: TripPreferences,
    *,
    destination: str,
    spot: str,
    trip_date: date | None = None,
) -> OutfitSearchProfile:
    raw_style = (prefs.style or "休闲").strip()
    styles = [part.strip() for part in raw_style.replace(",", "、").split("、") if part.strip()]
    return OutfitSearchProfile(
        destination=destination.strip(),
        spot=spot.strip() or destination.strip(),
        trip_date=trip_date,
        height_cm=prefs.height_cm,
        weight_kg=prefs.weight_kg,
        body_type=prefs.body_type,
        styles=styles or ["休闲"],
        gender=prefs.gender,
        negative_constraints=list(prefs.avoid_items or []),
    )


def compile_base_tokens(profile: OutfitSearchProfile) -> list[QueryToken]:
    """Step 2: deterministic token assembly with rule labels for debug UI."""
    tokens: list[QueryToken] = []
    if profile.spot.strip():
        query_spot = spot_search_label(profile.spot, profile.destination)
        tokens.append(QueryToken(token=query_spot, rule="景点"))

    height_label = height_search_label(profile.height_cm)
    if height_label:
        tokens.append(QueryToken(token=height_label, rule="身高"))

    gender_label = gender_search_label(profile.gender)
    if gender_label:
        tokens.append(QueryToken(token=gender_label, rule="性别"))

    body_label = body_type_search_label(profile.body_type)
    body_profile = BodyProfile(
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        body_type=profile.body_type,
        gender=profile.gender,
    )
    xhs_body = body_profile.xhs_body_tokens()
    if xhs_body:
        for token in xhs_body:
            tokens.append(QueryToken(token=token, rule="体型"))
    elif body_label:
        tokens.append(QueryToken(token=body_label, rule="体型"))

    style_label = style_search_label(profile.styles[0] if profile.styles else "")
    if style_label:
        tokens.append(QueryToken(token=style_label, rule="风格"))

    tokens.append(QueryToken(token="穿搭", rule="固定"))
    return tokens


def compile_outfit_query(profile: OutfitSearchProfile) -> CompiledOutfitQuery:
    """Compile one final XHS search string from profile."""
    base_tokens = compile_base_tokens(profile)
    final_query = " ".join(item.token for item in base_tokens)
    return CompiledOutfitQuery(
        profile=profile,
        base_tokens=base_tokens,
        final_query=final_query,
        source="rule",
    )


def compile_city_fallback_query(
    profile: OutfitSearchProfile,
    *,
    season: str | None = None,
) -> list[str]:
    """When no scenic spot is assigned, search at city level."""
    city_profile = profile.model_copy(update={"spot": profile.destination})
    queries = [compile_outfit_query(city_profile).final_query]
    if season:
        queries.append(f"{profile.destination} {season}穿搭")
    return queries


def negative_filter_tokens(negative_constraints: list[str] | None) -> list[str]:
    """Build blocklist tokens from avoid_items + semantic expansions."""
    tokens = avoid_match_tokens(negative_constraints)
    seen = set(tokens)
    for constraint in negative_constraints or []:
        for key, expansions in _SEMANTIC_NEGATIVE.items():
            if key in constraint:
                for word in expansions:
                    if word not in seen:
                        seen.add(word)
                        tokens.append(word)
    return tokens


def note_rejected_by_profile(
    note: XhsNoteSummary,
    profile: OutfitSearchProfile,
) -> str | None:
    """Step 4: return rejection reason or None if note is acceptable."""
    text = f"{note.title} {note.desc}"
    for token in negative_filter_tokens(profile.negative_constraints):
        if token and token in text:
            return f"negative:{token}"
    return None


def expand_queries_with_llm(
    profile: OutfitSearchProfile,
    base_query: str,
    *,
    llm=None,
) -> list[str]:
    """
    Step 3 (optional): LLM suggests 1–2 alternative search phrases.

    Expansion only — must not change hard rules (height/body/gender/spot).
    """
    from src.config import get_settings
    from src.services.llm import get_chat_model, invoke_structured

    if not get_settings().xhs_query_llm_expand:
        return []

    model = llm or get_chat_model()
    profile_json = profile.model_dump(mode="json")
    system = (
        "You expand Xiaohongshu outfit search queries. "
        "Return 1-2 SHORT alternative search phrases users would type on 小红书. "
        "Keep the same spot, gender, and outfit intent. "
        "Do NOT remove 穿搭. Do NOT invent new user constraints."
    )
    user = (
        f"Base query: {base_query}\n"
        f"Profile JSON: {profile_json}\n\n"
        "Examples: 韩系→韩系穿搭/ins风穿搭; 京都→日系街拍穿搭. "
        'Return JSON: {"queries": ["...", "..."]}'
    )
    try:
        result: ExpandQueriesOutput = invoke_structured(
            model,
            ExpandQueriesOutput,
            [SystemMessage(content=system), HumanMessage(content=user)],
            retries=0,
            operation="xhs_query_expand",
        )
    except Exception:
        return []

    expanded: list[str] = []
    seen = {base_query.strip()}
    for query in result.queries:
        cleaned = query.strip()
        if not cleaned or cleaned in seen:
            continue
        if "穿搭" not in cleaned and "ootd" not in cleaned.lower():
            cleaned = f"{cleaned} 穿搭"
        seen.add(cleaned)
        expanded.append(cleaned)
    return expanded[:2]


class OutfitQueryCompiler:
    """Facade for compile → optional expand → filter debug."""

    def compile(self, profile: OutfitSearchProfile) -> CompiledOutfitQuery:
        return compile_outfit_query(profile)

    def compile_queries_for_spots(
        self,
        prefs: TripPreferences,
        *,
        destination: str,
        spots: list[str],
        trip_date: date | None = None,
        llm=None,
    ) -> list[tuple[str, CompiledOutfitQuery]]:
        """Return (search_string, compile_debug) pairs for one trip day."""
        rows: list[tuple[str, CompiledOutfitQuery]] = []
        seen_queries: set[str] = set()
        clean_spots = [s.strip() for s in spots if s.strip()]

        if not clean_spots:
            profile = profile_from_preferences(
                prefs,
                destination=destination,
                spot=destination,
                trip_date=trip_date,
            )
            season = season_hint_for_month(trip_date.month) if trip_date else ""
            compiled = self.compile(profile)
            city_queries = compile_city_fallback_query(profile, season=season or None)
            for query in city_queries:
                if query not in seen_queries:
                    seen_queries.add(query)
                    rows.append((query, compiled))
            return rows

        for spot in clean_spots:
            profile = profile_from_preferences(
                prefs,
                destination=destination,
                spot=spot,
                trip_date=trip_date,
            )
            compiled = self.compile(profile)
            if compiled.final_query not in seen_queries:
                seen_queries.add(compiled.final_query)
                rows.append((compiled.final_query, compiled))

            for alt in expand_queries_with_llm(profile, compiled.final_query, llm=llm):
                if alt in seen_queries:
                    continue
                seen_queries.add(alt)
                expanded = compiled.model_copy(
                    update={"expanded_queries": [*compiled.expanded_queries, alt], "source": "rule+llm"}
                )
                rows.append((alt, expanded))

        return rows
