import logging
import os
import tempfile
import unittest

import pandas as pd

from tvscreener.lib.screeners.export_helpers import export_to_xml


class TestExportHelpers(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test")
        self.logger.addHandler(logging.NullHandler())

    def test_export_to_xml_injection(self):
        df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        metadata = {
            "title": "My <script>alert(1)</script> Export",
            "author": "John & Co",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.xml")
            export_to_xml(
                lambda: df,
                path,
                include_index=False,
                logger=self.logger,
                label="test",
                metadata=metadata,
            )

            with open(path) as f:
                content = f.read()

            # Check for escaped characters
            self.assertIn(
                "<title>My &lt;script&gt;alert(1)&lt;/script&gt; Export</title>",
                content,
            )
            self.assertIn("<author>John &amp; Co</author>", content)
            self.assertNotIn("<script>", content)
            self.assertNotIn("John & Co", content)

    def test_export_to_xml_key_sanitization(self):
        df = pd.DataFrame({"col1": [1]})
        metadata = {
            "invalid tag name": "value",
            "123startWithDigit": "value",
            "safe_key": "value",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_keys.xml")
            export_to_xml(
                lambda: df,
                path,
                include_index=False,
                logger=self.logger,
                label="test",
                metadata=metadata,
            )

            with open(path) as f:
                content = f.read()

            # Check for sanitized keys
            self.assertIn("<invalidtagname>value</invalidtagname>", content)
            self.assertIn("<meta_123startWithDigit>value</meta_123startWithDigit>", content)
            self.assertIn("<safe_key>value</safe_key>", content)


if __name__ == "__main__":
    unittest.main()
