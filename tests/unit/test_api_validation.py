import unittest
from unittest.mock import MagicMock, patch

from tvscreener import StockScreener
from tvscreener.exceptions import MalformedRequestException


class TestApiValidation(unittest.TestCase):
    def setUp(self):
        self.ss = StockScreener()
        self.ss.url = "https://example.com/scan"

    @patch("requests.post")
    def test_validate_correct_response(self, mock_post):
        # Mock a valid response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "totalCount": 1,
            "data": [{"s": "NASDAQ:AAPL", "d": [150.0, 1000000]}],
        }
        mock_post.return_value = mock_response

        # We need to know how many columns are expected.
        # StockScreener defaults to some columns.
        # Let's mock the columns to match our data.
        with patch("tvscreener.core.base.get_columns_to_request") as mock_cols:
            mock_cols.return_value = {"price": "Price", "volume": "Volume"}
            df = self.ss.get()

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["Symbol"], "NASDAQ:AAPL")

    @patch("requests.post")
    def test_validate_missing_data_key(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"totalCount": 0}  # Missing "data"
        mock_post.return_value = mock_response

        with self.assertRaises(MalformedRequestException) as cm:
            self.ss.get()
        self.assertIn("missing 'data' key", str(cm.exception))

    @patch("requests.post")
    def test_validate_data_not_list(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "not a list"}
        mock_post.return_value = mock_response

        with self.assertRaises(MalformedRequestException) as cm:
            self.ss.get()
        self.assertIn("should be a list", str(cm.exception))

    @patch("requests.post")
    def test_validate_item_missing_keys(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"s": "AAPL"}]  # Missing "d"
        }
        mock_post.return_value = mock_response

        with self.assertRaises(MalformedRequestException) as cm:
            self.ss.get()
        self.assertIn("missing data 'd' key", str(cm.exception))

    @patch("requests.post")
    def test_validate_column_length_mismatch(self, mock_post):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"s": "AAPL", "d": [150.0]}]  # Only 1 value
        }
        mock_post.return_value = mock_response

        with patch("tvscreener.core.base.get_columns_to_request") as mock_cols:
            mock_cols.return_value = {"p": "Price", "v": "Vol"}  # Expects 2 values
            with self.assertRaises(MalformedRequestException) as cm:
                self.ss.get()
        self.assertIn("Data length mismatch", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
