import unittest
from unittest.mock import MagicMock

import pandas as pd
from rich.console import Console
from rich.table import Table

from tvscreener.beauty import VisualStyler
from tvscreener.lib.screeners.renderers.rich_console import RichConsoleRenderer


class TestRichConsoleRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = RichConsoleRenderer()
        self.console = Console(width=100, force_terminal=True)

        # Sample data
        self.df = pd.DataFrame(
            {
                "PAIR": ["EURUSD", "GBPUSD"],
                "ENSEMBLE_SCORE": [0.8, -0.2],
                "GRID_ALIGNED": [10, 5],
                "GRID_TOTAL": [12, 12],
                "GRADE": ["A", "C"],
                "TF_CONFLUENCE": ["3/3", "1/3"],
                "FACTOR_CONFLUENCE": ["4/4", "2/4"],
                "STRATEGY": ["trend_following", "mean_reversion"],
            }
        )

    def test_visual_styler_logic(self):
        """Verify that VisualStyler logic is correct (moved from renderer)."""
        self.assertEqual(VisualStyler.direction_emoji(0.6), "🟢🟢")
        self.assertEqual(VisualStyler.direction_emoji(0.2), "🟢")
        self.assertEqual(VisualStyler.direction_emoji(-0.6), "🔴🔴")
        self.assertEqual(VisualStyler.direction_emoji(-0.2), "🔴")

        self.assertEqual(VisualStyler.matrix_sign(1.0), "🟢")
        self.assertEqual(VisualStyler.matrix_sign(-1.0), "🔴")
        self.assertEqual(VisualStyler.matrix_sign(0.0), "⚪")

    def test_renderer_registry(self):
        """Test that the registry works as expected."""
        mock_screener = MagicMock()
        mock_screener.__class__.__name__ = "CustomScreener"
        mock_screener._prepare_enriched_data.return_value = self.df

        # Register a custom render method
        self.renderer.register(
            "CustomScreener",
            empty_rich_message="No custom results",
            render_method="_render_generic",  # Use generic for testing
        )

        # Should find it in registry
        self.assertIn("CustomScreener", RichConsoleRenderer._registry)

        # Rendering should work
        self.renderer.render(mock_screener)

    def test_renderer_class_registry(self):
        """Test that registering an alternative renderer class works."""

        class AltRenderer:
            def __init__(self):
                self.called = False

            def render(self, screener, **kwargs):
                screener.alt_rendered = True

        mock_screener = MagicMock()
        mock_screener.__class__.__name__ = "AltScreener"

        self.renderer.register("AltScreener", renderer_class=AltRenderer)

        self.renderer.render(mock_screener)
        self.assertTrue(mock_screener.alt_rendered)

    def test_render_opportunity_output(self):
        # Mock screener
        screener = MagicMock()
        screener.__class__.__name__ = "ForexOpportunityScreener"
        screener.config.show_risk = False
        screener._prepare_enriched_data.return_value = self.df

        # This should run without error
        self.renderer.render(screener)

    def test_render_strategy_output(self):
        # Mock screener
        screener = MagicMock()
        screener.__class__.__name__ = "ForexStrategyScanner"
        screener.config.show_risk = False
        screener._prepare_enriched_data.return_value = self.df

        # This should run without error
        self.renderer.render(screener)

    def test_matrix_cells_do_not_truncate_with_ellipsis(self):
        screener = MagicMock()
        screener.__class__.__name__ = "ForexOpportunityScreener"
        screener.timeframes = ["240", "60", "15"]

        df = pd.DataFrame(
            {
                "PAIR": ["RENDERUSDT.P"],
                "DIRECTION": ["long"],
                "GRADE": ["A+"],
                "GRID_ALIGNED": [11],
                "GRID_TOTAL": [12],
                "TREND_240": [1.0],
                "TREND_60": [1.0],
                "TREND_15": [1.0],
                "MA_240": [1.0],
                "MA_60": [1.0],
                "MA_15": [1.0],
                "OSC_240": [1.0],
                "OSC_60": [0.0],
                "OSC_15": [-1.0],
                "ROC_240": [1.0],
                "ROC_60": [1.0],
                "ROC_15": [1.0],
            }
        )

        console = Console(width=80, force_terminal=True)
        with console.capture() as capture:
            self.renderer._render_confluence_matrix(
                screener, df, console, Table, title="Confluence Matrix"
            )

        out = capture.get()
        self.assertNotIn("|…", out)
        self.assertIn("🟢|🟢|🟢", out)
