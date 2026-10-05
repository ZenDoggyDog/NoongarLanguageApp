import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noongar_data import (
    build_quiz_options,
    clean_daily_accuracy,
    load_vocabulary,
    record_daily_accuracy,
    search_vocabulary,
    summarize_categories,
)


class LoadVocabularyTests(unittest.TestCase):
    def write_csv(self, text):
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            suffix=".csv",
            delete=False,
        )
        with temporary_file:
            temporary_file.write(text)
        self.addCleanup(Path(temporary_file.name).unlink, missing_ok=True)
        return Path(temporary_file.name)

    def test_loads_words_and_categories(self):
        path = self.write_csv(
            "English,Noongar,Category\nabove,yira,Concepts\n"
        )
        self.assertEqual(
            load_vocabulary(path),
            [{"english": "above", "noongar": "yira", "category": "Concepts"}],
        )

    def test_loads_bom_and_case_insensitive_headers(self):
        path = self.write_csv(
            "\ufeffENGLISH,NOONGAR,CATEGORY\nabove,yira,Concepts\n"
        )
        self.assertEqual(load_vocabulary(path)[0]["noongar"], "yira")

    def test_missing_category_defaults_to_uncategorised(self):
        path = self.write_csv("English,Noongar\nabove,yira\n")
        self.assertEqual(
            load_vocabulary(path)[0]["category"],
            "Uncategorised",
        )

    def test_blank_word_rows_are_skipped_and_values_trimmed(self):
        path = self.write_csv(
            "English,Noongar,Category\n above , yira , Concepts \n ,noongar,\n"
        )
        self.assertEqual(
            load_vocabulary(path),
            [{"english": "above", "noongar": "yira", "category": "Concepts"}],
        )

    def test_missing_required_columns_raise_value_error(self):
        path = self.write_csv("English,Category\nabove,Concepts\n")
        with self.assertRaisesRegex(ValueError, "Noongar"):
            load_vocabulary(path)

    def test_missing_header_row_raises_value_error(self):
        path = self.write_csv("")
        with self.assertRaisesRegex(ValueError, "header row"):
            load_vocabulary(path)


class SearchVocabularyTests(unittest.TestCase):
    vocabulary = [
        {"english": "above", "noongar": "yira", "category": "Concepts"},
        {"english": "animal", "noongar": "yoorn", "category": "Animals"},
    ]

    def test_search_matches_english_case_insensitively(self):
        self.assertEqual(
            search_vocabulary(self.vocabulary, "ABO"),
            [self.vocabulary[0]],
        )

    def test_search_matches_noongar(self):
        self.assertEqual(
            search_vocabulary(self.vocabulary, "YOOR"),
            [self.vocabulary[1]],
        )

    def test_search_can_filter_by_category_case_insensitively(self):
        self.assertEqual(
            search_vocabulary(self.vocabulary, "a", "animals"),
            [self.vocabulary[1]],
        )

    def test_empty_search_returns_no_results(self):
        self.assertEqual(search_vocabulary(self.vocabulary, "  "), [])


class CategorySummaryTests(unittest.TestCase):
    def test_summaries_include_counts_percentages_and_sort_order(self):
        vocabulary = [
            {"english": "a", "noongar": "a", "category": "Plants"},
            {"english": "b", "noongar": "b", "category": "Animals"},
            {"english": "c", "noongar": "c", "category": "Animals"},
        ]
        summaries = summarize_categories(vocabulary)
        self.assertEqual(
            [(item.category, item.count) for item in summaries],
            [("Animals", 2), ("Plants", 1)],
        )
        self.assertAlmostEqual(summaries[0].percentage, 200 / 3)
        self.assertAlmostEqual(summaries[1].percentage, 100 / 3)

    def test_empty_vocabulary_has_no_category_summaries(self):
        self.assertEqual(summarize_categories([]), [])

    def test_blank_categories_are_counted_as_uncategorised(self):
        item = {"english": "a", "noongar": "a", "category": " "}
        self.assertEqual(
            summarize_categories([item])[0].category,
            "Uncategorised",
        )


class BuildQuizOptionsTests(unittest.TestCase):
    def test_includes_correct_answer_and_samples_from_option_pool(self):
        question = {"english": "cat"}
        pool = [{"english": answer} for answer in ("cat", "dog", "bird", "fish")]
        with patch("noongar_data.random.sample", return_value=["dog", "bird", "fish"]):
            options = build_quiz_options(question, pool)
        self.assertCountEqual(options, ["cat", "dog", "bird", "fish"])

    def test_category_quiz_distractors_come_only_from_category_pool(self):
        question = {"english": "cat", "category": "Animals"}
        category_pool = [
            {"english": "cat", "category": "Animals"},
            {"english": "dog", "category": "Animals"},
            {"english": "oak", "category": "Plants"},
        ]
        animal_pool = [
            item for item in category_pool if item["category"] == "Animals"
        ]
        options = build_quiz_options(question, animal_pool)
        self.assertCountEqual(options, ["cat", "dog"])

    def test_deduplicates_meanings_case_insensitively(self):
        question = {"english": "cat"}
        pool = [{"english": answer} for answer in ("cat", "CAT", "dog", "DOG")]
        with patch("noongar_data.random.sample", side_effect=lambda values, count: values[:count]):
            options = build_quiz_options(question, pool)
        self.assertCountEqual(options, ["cat", "dog"])

    def test_zero_distractors_returns_only_the_correct_answer(self):
        options = build_quiz_options(
            {"english": "cat"},
            [{"english": "cat"}, {"english": "dog"}],
            distractor_count=0,
        )
        self.assertEqual(options, ["cat"])

    def test_negative_distractor_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            build_quiz_options({"english": "cat"}, [], distractor_count=-1)


class DailyAccuracyTests(unittest.TestCase):
    def test_records_a_new_day_without_mutating_existing_history(self):
        history = {"2026-10-04": {"correct": 3, "attempted": 5}}
        updated = record_daily_accuracy(history, 2, 3, "2026-10-05")
        self.assertEqual(updated["2026-10-05"], {"correct": 2, "attempted": 3})
        self.assertNotIn("2026-10-05", history)

    def test_accumulates_multiple_quiz_answers_on_same_day(self):
        history = record_daily_accuracy({}, 2, 3, "2026-10-05")
        updated = record_daily_accuracy(history, 1, 2, "2026-10-05")
        self.assertEqual(updated["2026-10-05"], {"correct": 3, "attempted": 5})

    def test_rejects_invalid_answer_counts(self):
        for correct, attempted in ((0, 0), (-1, 1), (2, 1)):
            with self.subTest(correct=correct, attempted=attempted):
                with self.assertRaises(ValueError):
                    record_daily_accuracy({}, correct, attempted, "2026-10-05")

    def test_rejects_invalid_date(self):
        with self.assertRaises(ValueError):
            record_daily_accuracy({}, 1, 1, "not-a-date")

    def test_cleaner_ignores_invalid_saved_records(self):
        history = {
            "2026-10-05": {"correct": 2, "attempted": 3},
            "not-a-date": {"correct": 1, "attempted": 1},
            "2026-10-04": {"correct": 4, "attempted": 3},
            "2026-10-03": {"correct": True, "attempted": 1},
        }
        self.assertEqual(
            clean_daily_accuracy(history),
            {"2026-10-05": {"correct": 2, "attempted": 3}},
        )


if __name__ == "__main__":
    unittest.main()
