import unittest

from stock_movement_analyzer.credibility import filter_and_score_results, score_source


class CredibilityTests(unittest.TestCase):
    def test_blacklisted_source_is_rejected(self) -> None:
        credibility = score_source(
            "https://medium.com/@someone/nvda-earnings",
            title="NVDA analysis",
            content="earnings revenue eps guidance",
        )

        self.assertEqual(credibility["tier_label"], "BLACKLISTED")
        self.assertEqual(credibility["score"], 0)

    def test_investor_relations_page_is_primary(self) -> None:
        credibility = score_source(
            "https://investors.nvidia.com/newsroom/press-release/default.aspx",
        )

        self.assertEqual(credibility["tier"], 1)
        self.assertEqual(credibility["tier_label"], "PRIMARY")

    def test_filter_keeps_best_result_when_everything_is_low_score(self) -> None:
        response = {
            "results": [
                {
                    "url": "https://example-one.invalid/post",
                    "title": "Weak source one",
                    "content": "opinion only",
                },
                {
                    "url": "https://example-two.invalid/post",
                    "title": "Weak source two",
                    "content": "still weak",
                },
            ]
        }

        filtered = filter_and_score_results(response, min_score=30)

        self.assertEqual(len(filtered["results"]), 1)
        self.assertIn("credibility_summary", filtered)
