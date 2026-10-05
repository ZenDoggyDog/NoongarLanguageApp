import csv
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class CategorySummary:
    category: str
    count: int
    percentage: float


def record_daily_accuracy(
    history: dict[str, dict[str, int]],
    correct_count: int,
    attempted_count: int,
    day: str | None = None,
) -> dict[str, dict[str, int]]:
    if attempted_count < 1 or not 0 <= correct_count <= attempted_count:
        raise ValueError("Daily quiz counts must satisfy 0 <= correct <= attempted.")

    day_key = day or date.today().isoformat()
    if date.fromisoformat(day_key).isoformat() != day_key:
        raise ValueError("The daily accuracy date must use YYYY-MM-DD format.")
    updated_history = clean_daily_accuracy(history)
    counts = updated_history.setdefault(day_key, {"correct": 0, "attempted": 0})
    counts["correct"] += correct_count
    counts["attempted"] += attempted_count
    return updated_history


def clean_daily_accuracy(history: object) -> dict[str, dict[str, int]]:
    if not isinstance(history, dict):
        return {}

    clean_history = {}
    for day_key, counts in history.items():
        if not isinstance(day_key, str) or not isinstance(counts, dict):
            continue
        try:
            if date.fromisoformat(day_key).isoformat() != day_key:
                continue
        except ValueError:
            continue
        correct = counts.get("correct")
        attempted = counts.get("attempted")
        if (
            type(correct) is int
            and type(attempted) is int
            and attempted > 0
            and 0 <= correct <= attempted
        ):
            clean_history[day_key] = {
                "correct": correct,
                "attempted": attempted,
            }
    return clean_history


def load_vocabulary(csv_path: Path) -> list[dict[str, str]]:
    vocabulary = []
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("The dictionary CSV has no header row.")

        normalized_headers = {
            (header or "").strip().casefold(): header
            for header in reader.fieldnames
        }
        if "noongar" not in normalized_headers or "english" not in normalized_headers:
            raise ValueError(
                "The dictionary CSV must have 'Noongar' and 'English' columns."
            )
        category_header = normalized_headers.get("category")

        for row in reader:
            noongar_word = (
                row.get(normalized_headers["noongar"]) or ""
            ).strip()
            english_word = (
                row.get(normalized_headers["english"]) or ""
            ).strip()
            category = (
                (row.get(category_header) or "").strip()
                if category_header
                else ""
            )
            if noongar_word and english_word:
                vocabulary.append(
                    {
                        "noongar": noongar_word,
                        "english": english_word,
                        "category": category or "Uncategorised",
                    }
                )
    return vocabulary


def search_vocabulary(
    vocabulary: list[dict[str, str]],
    query: str,
    category: str | None = None,
) -> list[dict[str, str]]:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return []

    normalized_category = category.casefold() if category else None
    return [
        item
        for item in vocabulary
        if (
            normalized_category is None
            or item["category"].casefold() == normalized_category
        )
        and (
            normalized_query in item["noongar"].casefold()
            or normalized_query in item["english"].casefold()
        )
    ]


def summarize_categories(
    vocabulary: list[dict[str, str]],
) -> list[CategorySummary]:
    if not vocabulary:
        return []

    counts = Counter(item.get("category", "").strip() or "Uncategorised" for item in vocabulary)
    total = len(vocabulary)
    return [
        CategorySummary(
            category=category,
            count=count,
            percentage=count / total * 100,
        )
        for category, count in sorted(
            counts.items(),
            key=lambda entry: (-entry[1], entry[0].casefold()),
        )
    ]


def build_quiz_options(
    question: dict[str, str],
    option_pool: list[dict[str, str]],
    distractor_count: int = 3,
) -> list[str]:
    if distractor_count < 0:
        raise ValueError("The number of distractors cannot be negative.")

    correct_answer = question["english"]
    correct_key = correct_answer.casefold()
    answers = {}
    for item in option_pool:
        answer = item["english"]
        answer_key = answer.casefold()
        if answer_key != correct_key:
            answers.setdefault(answer_key, answer)
    distractors = random.sample(
        list(answers.values()),
        min(distractor_count, len(answers)),
    )
    options = [*distractors, correct_answer]
    random.shuffle(options)
    return options
