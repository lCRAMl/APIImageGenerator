from core.build_info import BuildInfo


def test_window_title_with_build():
    info = BuildInfo("API Image Generator", "v2.8.4-0-gafaa3f8", "2026-09-22 21:01:30", "afaa3f8", "https://x")
    assert info.window_title == "API Image Generator \nv2.8.4-0-gafaa3f8 \n2026-09-22 21:01:30"


def test_window_title_without_build():
    assert BuildInfo("API Image Generator", "dev", "", "", "").window_title == "API Image Generator \ndev"
