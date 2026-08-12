from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path


SEED = 20260812
ROOT = Path(__file__).resolve().parent
RNG = random.Random(SEED)

ERRORS = (
    "value_inaccuracy",
    "entity_misalignment",
    "trend_direction_error",
    "comparison_ranking_error",
    "key_feature_omission",
)

BAR = {
    "Bristol": {"2015": 42, "2020": 55},
    "Leeds": {"2015": 35, "2020": 48},
    "Liverpool": {"2015": 28, "2020": 39},
    "Manchester": {"2015": 31, "2020": 46},
    "Sheffield": {"2015": 38, "2020": 51},
}
LINE = {
    "Bus": {"2010": 1.8, "2012": 1.9, "2014": 1.7, "2016": 1.6, "2018": 1.5, "2020": 1.3},
    "Rail": {"2010": 1.1, "2012": 1.3, "2014": 1.5, "2016": 1.8, "2018": 2.0, "2020": 2.2},
    "Metro": {"2010": 0.8, "2012": 1.0, "2014": 1.2, "2016": 1.5, "2018": 1.7, "2020": 1.9},
}
PIE = {"Housing": 32, "Food": 21, "Transport": 17, "Leisure": 12, "Utilities": 10, "Other": 8}

INTROS = {
    "bar": [
        "The bar chart compares the percentages of households recycling waste in five British cities in 2015 and 2020.",
        "The chart presents household recycling rates for five cities in the United Kingdom at two points in time, 2015 and 2020.",
        "The grouped bars show the share of households that recycled in Bristol, Leeds, Liverpool, Manchester and Sheffield in 2015 and 2020.",
    ],
    "line": [
        "The line graph compares average daily passenger numbers for bus, rail and metro services between 2010 and 2020, measured in millions.",
        "The graph plots the number of passengers using three forms of public transport on an average day from 2010 to 2020.",
        "The line chart illustrates changes in daily bus, rail and metro use over the period 2010-2020, with figures given in millions.",
    ],
    "pie": [
        "The pie chart breaks down average Canadian household expenditure in 2024 across six spending categories.",
        "The chart shows how an average household in Canada allocated its spending in 2024.",
        "The circular chart presents the percentage distribution of Canadian household expenditure among six categories in 2024.",
    ],
}

NEUTRAL_OVERVIEWS = {
    "bar": [
        "Overall, the distribution changed across the two observations, and the five locations remained separated by noticeable margins.",
        "Overall, there were clear differences between the cities, while the second observation generally occupied a higher part of the scale.",
        "Overall, the figures varied by location and the distance between neighbouring cities was often modest.",
    ],
    "line": [
        "Overall, the three services followed visibly different paths and their relative positions changed during the decade.",
        "Overall, passenger use was distributed differently across the three modes by the end of the period.",
        "Overall, the lines did not remain in their initial order, and the gap between services changed over time.",
    ],
    "pie": [
        "Overall, spending was spread unevenly, with several medium-sized components and a smaller group of minor items.",
        "Overall, the household budget was divided into clearly unequal shares rather than being distributed evenly.",
        "Overall, a few categories accounted for substantial portions of the budget, while the remaining shares were more limited.",
    ],
}

BAR_VALUE_PATTERNS = [
    "In {year}, {entity} registered {value}%.",
    "{entity}'s figure in {year} was {value}%.",
    "For {year}, the rate reported for {entity} stood at {value}%.",
]
LINE_ENDPOINT_PATTERNS = [
    "{entity} carried {start:.1f} million passengers in 2010 and {end:.1f} million in 2020.",
    "The figures for {entity} were {start:.1f} million at the beginning and {end:.1f} million at the end.",
    "In 2010, {entity} served {start:.1f} million passengers per day, compared with {end:.1f} million in 2020.",
]
LINE_MID_PATTERNS = [
    "In {year}, the figure for {entity} was {value:.1f} million.",
    "{entity} recorded {value:.1f} million daily users in {year}.",
    "At {year}, {entity} stood at {value:.1f} million passengers.",
]
PIE_VALUE_PATTERNS = [
    "{entity} represented {value}% of the budget.",
    "The share allocated to {entity} was {value}%.",
    "Households devoted {value}% of expenditure to {entity}.",
]
FILLERS = {
    "bar": [
        "Taken together, the observations provide a compact comparison of local recycling behaviour.",
        "The data therefore show measurable variation rather than a uniform pattern across the country.",
        "These percentages allow both changes over time and differences between places to be compared directly.",
    ],
    "line": [
        "The intermediate observations help to show how the ordering developed rather than only giving two isolated totals.",
        "These figures make the changing balance among the transport services visible across the decade.",
        "The recorded points provide enough detail to compare the services at both the beginning and the end.",
    ],
    "pie": [
        "Together, the listed components account for the complete household budget shown in the chart.",
        "The proportions give a direct view of how the household budget was divided during the year.",
        "This distribution makes it possible to compare major commitments with smaller items of expenditure.",
    ],
}


def paragraphs(sentences: list[str]) -> str:
    return "\n\n".join((sentences[0], sentences[1], " ".join(sentences[2:-1]), sentences[-1]))


def bar_case(error: str, replicate: int) -> tuple[str, dict]:
    values = {city: dict(years) for city, years in BAR.items()}
    cities = list(values)
    metadata: dict = {}
    overview = RNG.choice(NEUTRAL_OVERVIEWS["bar"])
    omitted = None

    if error == "value_inaccuracy":
        city = RNG.choice(cities)
        year = RNG.choice(["2015", "2020"])
        delta = RNG.choice([-9, -7, 6, 8, 11])
        values[city][year] += delta
        metadata = {"entity": city, "period": year, "official": BAR[city][year], "claimed": values[city][year]}
    elif error == "entity_misalignment":
        left, right = RNG.sample(cities, 2)
        year = RNG.choice(["2015", "2020"])
        values[left][year], values[right][year] = values[right][year], values[left][year]
        metadata = {"entities": [left, right], "period": year}
    elif error == "trend_direction_error":
        city = RNG.choice(cities)
        overview = RNG.choice([
            f"Overall, {city} decreased over the period, while the chart continued to show marked differences between the five cities.",
            f"Overall, the recycling rate in {city} fell between the two years, and the cities remained distributed across a fairly broad range.",
            f"Overall, {city} followed a downward trend from 2015 to 2020, against a background of variation between locations.",
        ])
        metadata = {"entity": city, "official_direction": "increase", "claimed_direction": "decrease"}
    elif error == "comparison_ranking_error":
        year = RNG.choice(["2015", "2020"])
        rank = RNG.choice(["highest", "lowest"])
        official = max(cities, key=lambda c: BAR[c][year]) if rank == "highest" else min(cities, key=lambda c: BAR[c][year])
        wrong = RNG.choice([city for city in cities if city != official])
        overview = f"Overall, {wrong} recorded the {rank} recycling rate in {year}, while the cities remained separated by clear differences."
        metadata = {"entity": wrong, "period": year, "rank": rank, "official_entity": official}
    elif error == "key_feature_omission":
        omitted = RNG.choice(cities)
        metadata = {"omitted_entity": omitted}

    details = []
    cells = [(city, year, value) for city, years in values.items() if city != omitted for year, value in years.items()]
    RNG.shuffle(cells)
    for city, year, value in cells:
        details.append(RNG.choice(BAR_VALUE_PATTERNS).format(entity=city, year=year, value=value))
    sentences = [RNG.choice(INTROS["bar"]), overview, *details, RNG.choice(FILLERS["bar"])]
    return paragraphs(sentences), metadata


def line_case(error: str, replicate: int) -> tuple[str, dict]:
    values = {mode: dict(years) for mode, years in LINE.items()}
    modes = list(values)
    midpoint = RNG.choice(["2012", "2014", "2016", "2018"])
    metadata: dict = {"sampled_midpoint": midpoint}
    overview = RNG.choice(NEUTRAL_OVERVIEWS["line"])
    omitted = None

    if error == "value_inaccuracy":
        mode = RNG.choice(modes)
        year = RNG.choice(["2010", midpoint, "2020"])
        delta = RNG.choice([-0.4, -0.3, 0.3, 0.4, 0.5])
        values[mode][year] = round(values[mode][year] + delta, 1)
        metadata.update({"entity": mode, "period": year, "official": LINE[mode][year], "claimed": values[mode][year]})
    elif error == "entity_misalignment":
        left, right = RNG.sample(modes, 2)
        values[left][midpoint], values[right][midpoint] = values[right][midpoint], values[left][midpoint]
        metadata.update({"entities": [left, right], "period": midpoint})
    elif error == "trend_direction_error":
        mode = RNG.choice(modes)
        official_direction = "decrease" if LINE[mode]["2020"] < LINE[mode]["2010"] else "increase"
        claimed = "increase" if official_direction == "decrease" else "decrease"
        phrase = RNG.choice(["increased", "rose", "climbed"]) if claimed == "increase" else RNG.choice(["decreased", "fell", "declined"])
        overview = f"Overall, {mode} {phrase} over the period, while the relative positions of the three services changed during the decade."
        metadata.update({"entity": mode, "official_direction": official_direction, "claimed_direction": claimed})
    elif error == "comparison_ranking_error":
        year = RNG.choice(["2010", midpoint, "2020"])
        rank = RNG.choice(["highest", "lowest"])
        official = max(modes, key=lambda m: LINE[m][year]) if rank == "highest" else min(modes, key=lambda m: LINE[m][year])
        wrong = RNG.choice([mode for mode in modes if mode != official])
        overview = f"Overall, {wrong} was the {rank} transport mode in {year}, while the ordering of the three services changed elsewhere in the period."
        metadata.update({"entity": wrong, "period": year, "rank": rank, "official_entity": official})
    elif error == "key_feature_omission":
        omitted = RNG.choice(modes)
        metadata.update({"omitted_entity": omitted})

    details = []
    included = [mode for mode in modes if mode != omitted]
    RNG.shuffle(included)
    for mode in included:
        details.append(RNG.choice(LINE_ENDPOINT_PATTERNS).format(
            entity=mode, start=values[mode]["2010"], end=values[mode]["2020"]
        ))
    mid_modes = list(included)
    RNG.shuffle(mid_modes)
    for mode in mid_modes:
        details.append(RNG.choice(LINE_MID_PATTERNS).format(
            entity=mode, year=midpoint, value=values[mode][midpoint]
        ))
    sentences = [RNG.choice(INTROS["line"]), overview, *details, RNG.choice(FILLERS["line"])]
    return paragraphs(sentences), metadata


def pie_case(error: str, replicate: int) -> tuple[str, dict]:
    values = dict(PIE)
    categories = list(values)
    metadata: dict = {}
    overview = RNG.choice(NEUTRAL_OVERVIEWS["pie"])
    omitted = None

    if error == "value_inaccuracy":
        category = RNG.choice(categories)
        delta = RNG.choice([-6, -4, 4, 5, 7])
        values[category] += delta
        metadata = {"entity": category, "official": PIE[category], "claimed": values[category]}
    elif error == "entity_misalignment":
        left, right = RNG.sample(categories, 2)
        values[left], values[right] = values[right], values[left]
        metadata = {"entities": [left, right]}
    elif error == "trend_direction_error":
        category = RNG.choice(categories)
        direction = RNG.choice(["increased", "decreased", "remained stable"])
        overview = f"Overall, {category} {direction} over the period, while expenditure was distributed unevenly across the six categories."
        metadata = {
            "entity": category,
            "claimed_direction": direction,
            "expected_applicability": "not_applicable_single_period_pie",
        }
    elif error == "comparison_ranking_error":
        rank = RNG.choice(["largest", "smallest"])
        official = max(categories, key=lambda c: PIE[c]) if rank == "largest" else min(categories, key=lambda c: PIE[c])
        wrong = RNG.choice([category for category in categories if category != official])
        overview = f"Overall, {wrong} was the {rank} component of household expenditure, while the remaining categories occupied unequal shares."
        metadata = {"entity": wrong, "rank": rank, "official_entity": official}
    elif error == "key_feature_omission":
        omitted = RNG.choice(categories)
        metadata = {"omitted_entity": omitted}

    details = []
    entries = [(category, value) for category, value in values.items() if category != omitted]
    RNG.shuffle(entries)
    for category, value in entries:
        details.append(RNG.choice(PIE_VALUE_PATTERNS).format(entity=category, value=value))
    sentences = [RNG.choice(INTROS["pie"]), overview, *details, RNG.choice(FILLERS["pie"])]
    return paragraphs(sentences), metadata


def main() -> None:
    case_dir = ROOT / "essays"
    case_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    builders = {"bar": bar_case, "line": line_case, "pie": pie_case}
    for chart_type, builder in builders.items():
        for error in ERRORS:
            for replicate in range(1, 4):
                essay, metadata = builder(error, replicate)
                case_id = f"{chart_type}_{error}_{replicate}"
                essay_path = case_dir / f"{case_id}.txt"
                essay_path.write_text(essay + "\n", encoding="utf-8")
                cases.append({
                    "case_id": case_id,
                    "chart_type": chart_type,
                    "expected_error": error,
                    "replicate": replicate,
                    "essay_file": str(essay_path.relative_to(ROOT)).replace("\\", "/"),
                    "essay_sha256": hashlib.sha256(essay.encode("utf-8")).hexdigest(),
                    "generation_metadata": metadata,
                    "essay": essay,
                })

    manifest = {
        "protocol": "VividWrite taxonomy randomized robustness test",
        "seed": SEED,
        "case_count": len(cases),
        "generation_policy": (
            "Targets, error magnitude, detail order, and wording templates were sampled before inference. "
            "Cases are frozen and must not be edited in response to classifier output."
        ),
        "pie_trend_policy": (
            "The source pie is single-period. These three cases expect trend_direction_error to be "
            "reported as not applicable, not as a detected error."
        ),
        "cases": cases,
    }
    canonical = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    (ROOT / "cases.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "manifest.sha256").write_text(f"{digest}  cases.json\n", encoding="ascii")
    print(json.dumps({"seed": SEED, "cases": len(cases), "manifest_sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
