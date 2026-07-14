import unittest
from unittest.mock import patch

from sample_essay import SampleEssayRequest, generate_sample_essay


class SampleEssayTests(unittest.TestCase):
    @patch("sample_essay.get_deepseek_client")
    @patch("sample_essay.get_deepseek_api_key", return_value="test-key")
    def test_invalid_pie_data_is_rejected_before_calling_deepseek(self, _key, client):
        response = generate_sample_essay(
            SampleEssayRequest(
                chart_type="pie",
                deplot_text=(
                    "TITLE | Spending<0x0A>Category | Percentage<0x0A>"
                    "Housing | 32%<0x0A>Food | 8%<0x0A>Other | 8%"
                ),
                flowchart={
                    "nodes": [
                        {"type": "background"},
                        {"type": "presentation"},
                        {"type": "comment"},
                    ],
                    "edges": [],
                },
            )
        )

        self.assertFalse(response.success)
        self.assertIn("expected about 100%", response.error or "")
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
