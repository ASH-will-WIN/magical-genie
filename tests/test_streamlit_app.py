from streamlit.testing.v1 import AppTest


def test_app_loads_without_exception():
    at = AppTest.from_file("streamlit_app.py")
    at.run(timeout=15)
    assert not at.exception


def test_sidebar_navigation_lists_all_six_pages():
    at = AppTest.from_file("streamlit_app.py")
    at.run(timeout=15)
    assert not at.exception
    pages = [
        "app_pages/dashboard.py",
        "app_pages/new_campaign.py",
        "app_pages/review_queue.py",
        "app_pages/history.py",
        "app_pages/settings.py",
        "app_pages/usage.py"
    ]
    for page in pages:
        at.switch_page(page)
        at.run(timeout=15)
        assert not at.exception, f"Failed to switch to {page}"