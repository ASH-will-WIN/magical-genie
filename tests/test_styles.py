import pytest

from styles import signal_bar_html, venn_svg, mono


@pytest.mark.parametrize("bucket,expected_hex", [
    ("approved", "#4FA88A"),
    ("needs_review", "#E8AA4C"),
    ("rejected", "#C4634B"),
    ("dropped_at_prefilter", "#C4634B"),
])
def test_signal_bar_uses_bucket_color(bucket, expected_hex):
    html = signal_bar_html(score=65, bucket=bucket)
    assert expected_hex in html


def test_signal_bar_width_reflects_score():
    html = signal_bar_html(score=42, bucket="needs_review")
    assert "42%" in html


def test_signal_bar_clamps_score_to_0_100():
    assert "100%" in signal_bar_html(score=150, bucket="approved")
    assert "0%" in signal_bar_html(score=-10, bucket="rejected")


def test_venn_svg_contains_all_three_region_counts():
    svg = venn_svg(article_only=12, icp_only=8, blended=3)
    assert "<svg" in svg
    assert "12" in svg
    assert "8" in svg
    assert "3" in svg


def test_mono_wraps_value_in_monospace_span():
    result = mono(42.5)
    assert "42.5" in result
    assert "gs-mono" in result