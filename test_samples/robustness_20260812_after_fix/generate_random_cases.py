from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path


SEED = 2026081202
ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
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

INTRO = {
    "bar": [
        "The grouped bar chart compares household recycling percentages in five UK cities in 2015 and 2020.",
        "The bar chart gives recycling rates for households in five British cities at two observation points, 2015 and 2020.",
        "The chart displays the proportion of households recycling waste in Bristol, Leeds, Liverpool, Manchester and Sheffield in two years.",
    ],
    "line": [
        "The line graph shows average daily use of bus, rail and metro services between 2010 and 2020, in millions of passengers.",
        "The graph traces daily passenger numbers for three public transport modes over the decade from 2010 to 2020.",
        "The line chart presents changes in the millions of passengers using bus, rail and metro services on an average day.",
    ],
    "pie": [
        "The pie chart shows the distribution of average Canadian household spending across six categories in 2024.",
        "The circular chart presents how household expenditure in Canada was allocated among six items in 2024.",
        "The chart divides average Canadian household expenditure in 2024 into six percentage shares.",
    ],
}

NEUTRAL = {
    "bar": [
        "Overall, the figures differed considerably across the five cities, with several fairly close results.",
        "Overall, recycling levels varied by location and the relative spacing between the cities was not uniform.",
        "Overall, the chart reveals distinct city-level results at both measurement points.",
    ],
    "line": [
        "Overall, the three modes occupied different positions during the decade and the gaps among them changed.",
        "Overall, the lines followed contrasting paths, producing a different ordering by the final observation.",
        "Overall, use of the three services was distributed differently across the period.",
    ],
    "pie": [
        "Overall, the six shares were unevenly distributed, with clear differences between larger and smaller items.",
        "Overall, household spending was divided into a mixture of major, medium and relatively small components.",
        "Overall, the categories accounted for noticeably different proportions of expenditure.",
    ],
}

BAR_VALUE = [
    "{entity} was recorded at {value}% in {year}.",
    "In {year}, the proportion for {entity} stood at {value}%.",
    "The {year} result for {entity} was {value}%.",
    "For {entity}, the rate reached {value}% in {year}.",
]
LINE_ENDPOINT = [
    "{entity} began with {start:.1f} million passengers and ended at {end:.1f} million.",
    "{entity} opened the period at {start:.1f} million and closed it at {end:.1f} million.",
    "At the outset, {entity} carried {start:.1f} million passengers and ultimately reached {end:.1f} million.",
    "In 2010, {entity} served {start:.1f} million passengers, compared with {end:.1f} million in 2020.",
]
LINE_MID = [
    "The {entity} figure in {year} was {value:.1f} million.",
    "In {year}, {entity} carried {value:.1f} million daily passengers.",
    "At the {year} observation, {entity} stood at {value:.1f} million.",
]
PIE_VALUE = [
    "{entity} accounted for {value}% of expenditure.",
    "The proportion spent on {entity} was {value}%.",
    "A share of {value}% went to {entity}.",
    "Households allocated {value}% of their spending to {entity}.",
]

FILLER = {
    "bar": [
        "The two observations therefore allow changes within each location to be considered alongside differences between locations.",
        "Taken together, the city results provide both a time comparison and a cross-sectional comparison.",
        "These values offer a detailed view of recycling participation across the selected urban areas.",
    ],
    "line": [
        "The intermediate observation adds detail to the comparison rather than limiting it to the two endpoints.",
        "Together, these recorded points show how the balance between the services developed during the decade.",
        "The selected middle year helps indicate the position of each service between the first and final observations.",
    ],
    "pie": [
        "The stated shares make it possible to compare the relative weight of the categories in the household budget.",
        "These proportions show the different amounts of attention given to the reported spending items.",
        "The distribution gives a direct comparison of the expenditure categories represented in the report.",
    ],
}


def as_paragraphs(sentences: list[str]) -> str:
    return "\n\n".join((sentences[0], sentences[1], " ".join(sentences[2:-1]), sentences[-1]))


def bar_case(error: str) -> tuple[str, dict]:
    values = {entity: dict(periods) for entity, periods in BAR.items()}
    entities = list(values)
    meta: dict = {}
    overview = RNG.choice(NEUTRAL["bar"])
    omitted = None

    if error == "value_inaccuracy":
        entity = RNG.choice(entities)
        period = RNG.choice(("2015", "2020"))
        values[entity][period] += RNG.choice((-10, -8, -6, 7, 9, 12))
        meta = {"entity": entity, "period": period, "official": BAR[entity][period], "claimed": values[entity][period]}
    elif error == "entity_misalignment":
        left, right = RNG.sample(entities, 2)
        period = RNG.choice(("2015", "2020"))
        values[left][period], values[right][period] = values[right][period], values[left][period]
        meta = {"entities": [left, right], "period": period}
    elif error == "trend_direction_error":
        entity = RNG.choice(entities)
        verb = RNG.choice(("fell", "declined", "followed a downward trend"))
        overview = f"Overall, {entity} {verb} from 2015 to 2020, while the five cities remained separated by noticeable differences."
        meta = {"entity": entity, "official_direction": "increase", "claimed_direction": "decrease"}
    elif error == "comparison_ranking_error":
        period = RNG.choice(("2015", "2020"))
        rank = RNG.choice(("highest", "lowest"))
        official = (max if rank == "highest" else min)(entities, key=lambda item: BAR[item][period])
        entity = RNG.choice([item for item in entities if item != official])
        overview = f"Overall, {entity} had the {rank} recycling rate in {period}, although the locations otherwise showed varied results."
        meta = {"entity": entity, "period": period, "rank": rank, "official_entity": official}
    elif error == "key_feature_omission":
        omitted = RNG.choice(entities)
        meta = {"omitted_entity": omitted}

    details = [
        RNG.choice(BAR_VALUE).format(entity=entity, period=period, year=period, value=value)
        for entity, periods in values.items() if entity != omitted
        for period, value in periods.items()
    ]
    RNG.shuffle(details)
    return as_paragraphs([RNG.choice(INTRO["bar"]), overview, *details, RNG.choice(FILLER["bar"])]), meta


def line_case(error: str) -> tuple[str, dict]:
    values = {entity: dict(periods) for entity, periods in LINE.items()}
    entities = list(values)
    midpoint = RNG.choice(("2012", "2014", "2016", "2018"))
    meta: dict = {"sampled_midpoint": midpoint}
    overview = RNG.choice(NEUTRAL["line"])
    omitted = None

    if error == "value_inaccuracy":
        entity = RNG.choice(entities)
        period = RNG.choice(("2010", midpoint, "2020"))
        values[entity][period] = round(values[entity][period] + RNG.choice((-0.5, -0.4, -0.3, 0.3, 0.4, 0.5)), 1)
        meta.update({"entity": entity, "period": period, "official": LINE[entity][period], "claimed": values[entity][period]})
    elif error == "entity_misalignment":
        left, right = RNG.sample(entities, 2)
        values[left][midpoint], values[right][midpoint] = values[right][midpoint], values[left][midpoint]
        meta.update({"entities": [left, right], "period": midpoint})
    elif error == "trend_direction_error":
        entity = RNG.choice(entities)
        official = "decrease" if LINE[entity]["2020"] < LINE[entity]["2010"] else "increase"
        claimed = "increase" if official == "decrease" else "decrease"
        verb = RNG.choice(("rose", "increased", "climbed")) if claimed == "increase" else RNG.choice(("fell", "decreased", "declined"))
        overview = f"Overall, {entity} {verb} over the decade, while the relative positions of all three modes changed during the period."
        meta.update({"entity": entity, "official_direction": official, "claimed_direction": claimed})
    elif error == "comparison_ranking_error":
        period = RNG.choice(("2010", midpoint, "2020"))
        rank = RNG.choice(("highest", "lowest"))
        official = (max if rank == "highest" else min)(entities, key=lambda item: LINE[item][period])
        entity = RNG.choice([item for item in entities if item != official])
        overview = f"Overall, {entity} was the {rank} transport mode in {period}, while the ordering differed at other observations."
        meta.update({"entity": entity, "period": period, "rank": rank, "official_entity": official})
    elif error == "key_feature_omission":
        omitted = RNG.choice(entities)
        meta.update({"omitted_entity": omitted})

    included = [entity for entity in entities if entity != omitted]
    RNG.shuffle(included)
    endpoints = [
        RNG.choice(LINE_ENDPOINT).format(entity=entity, start=values[entity]["2010"], end=values[entity]["2020"])
        for entity in included
    ]
    middle = [
        RNG.choice(LINE_MID).format(entity=entity, year=midpoint, value=values[entity][midpoint])
        for entity in RNG.sample(included, len(included))
    ]
    return as_paragraphs([RNG.choice(INTRO["line"]), overview, *endpoints, *middle, RNG.choice(FILLER["line"])]), meta


def pie_case(error: str) -> tuple[str, dict]:
    values = dict(PIE)
    entities = list(values)
    meta: dict = {}
    overview = RNG.choice(NEUTRAL["pie"])
    omitted = None

    if error == "value_inaccuracy":
        entity = RNG.choice(entities)
        values[entity] += RNG.choice((-7, -5, -4, 4, 6, 8))
        meta = {"entity": entity, "official": PIE[entity], "claimed": values[entity]}
    elif error == "entity_misalignment":
        left, right = RNG.sample(entities, 2)
        values[left], values[right] = values[right], values[left]
        meta = {"entities": [left, right]}
    elif error == "trend_direction_error":
        entity = RNG.choice(entities)
        verb = RNG.choice(("increased", "decreased", "remained stable"))
        overview = f"Overall, {entity} {verb} over the period, while the six spending categories occupied unequal shares."
        meta = {"entity": entity, "claimed_direction": verb, "expected_applicability": "not_applicable_single_period_pie"}
    elif error == "comparison_ranking_error":
        rank = RNG.choice(("largest", "smallest"))
        official = (max if rank == "largest" else min)(entities, key=lambda item: PIE[item])
        entity = RNG.choice([item for item in entities if item != official])
        overview = f"Overall, {entity} was the {rank} category in the household budget, with unequal shares across the other items."
        meta = {"entity": entity, "rank": rank, "official_entity": official}
    elif error == "key_feature_omission":
        omitted = RNG.choice(entities)
        meta = {"omitted_entity": omitted}

    entries = [(entity, value) for entity, value in values.items() if entity != omitted]
    RNG.shuffle(entries)
    details = [RNG.choice(PIE_VALUE).format(entity=entity, value=value) for entity, value in entries]
    return as_paragraphs([RNG.choice(INTRO["pie"]), overview, *details, RNG.choice(FILLER["pie"])]), meta


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    essays_dir = ROOT / "essays"
    essays_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    builders = {"bar": bar_case, "line": line_case, "pie": pie_case}
    for chart_type, builder in builders.items():
        for error in ERRORS:
            for replicate in range(1, 4):
                essay, metadata = builder(error)
                case_id = f"{chart_type}_{error}_{replicate}"
                essay_path = essays_dir / f"{case_id}.txt"
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

    code_files = (
        PROJECT / "backend" / "chart_feedback.py",
        PROJECT / "backend" / "chart_renderer.py",
        PROJECT / "backend" / "error_taxonomy.py",
    )
    manifest = {
        "protocol": "VividWrite post-fix held-out randomized taxonomy robustness test",
        "seed": SEED,
        "case_count": len(cases),
        "code_sha256": {str(path.relative_to(PROJECT)).replace("\\", "/"): file_sha256(path) for path in code_files},
        "generation_policy": (
            "Targets, periods, error magnitudes, sentence order, and wording were randomized and frozen before inference. "
            "No case may be edited after any model output is observed."
        ),
        "pie_trend_policy": (
            "The source pie contains one period. Trend cases therefore expect no trend issue and an explicit not-applicable result."
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
