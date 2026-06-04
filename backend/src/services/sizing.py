"""Clothing size hints from height/weight for Taobao search queries."""


def infer_size_hint(
    height_cm: float | None,
    weight_kg: float | None,
    gender: str | None = None,
) -> str:
    """Return a Taobao-friendly size token, e.g. 'M 165' or 'L 170'."""
    if not height_cm or height_cm <= 0:
        return ""

    h = int(height_cm)
    w = int(weight_kg) if weight_kg and weight_kg > 0 else None

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

    if w is not None:
        bmi = w / ((h / 100) ** 2)
        if bmi >= 26 and letter in {"S", "M"}:
            letter = "L" if letter == "M" else "XL"
        elif bmi >= 24 and letter == "S":
            letter = "M"

    g = (gender or "").strip()
    if g == "男":
        return f"{letter} {h}cm"
    return f"{letter} {h}cm"
