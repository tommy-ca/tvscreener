from rich.console import Console

from tvscreener_ext.orchestrator import ScreenerController


def test_fetch_data_with_progress_skips_spinner_for_recording_console() -> None:
    console = Console(record=True, force_terminal=True, width=80)
    controller = ScreenerController(console=console)

    with console.capture() as capture:
        out = controller._workflow._fetch_data_with_progress(lambda: 123)

    assert out == 123
    assert capture.get() == ""
