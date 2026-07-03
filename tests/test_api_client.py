from unittest.mock import Mock, patch

import requests

import api_client


def test_run_campaign_posts_url_and_returns_json():
    fake_response = Mock()
    fake_response.json.return_value = {"campaign_id": 1, "status": "generated"}
    fake_response.raise_for_status.return_value = None
    with patch("api_client.requests.post", return_value=fake_response) as mock_post:
        result = api_client.run_campaign(url="https://example.com/article")

    assert result == {"campaign_id": 1, "status": "generated"}
    mock_post.assert_called_once_with(
        f"{api_client.API_BASE}/campaign",
        json={"url": "https://example.com/article", "manual_text": None},
        timeout=90,
    )


def test_run_campaign_returns_soft_error_on_connection_failure():
    with patch("api_client.requests.post", side_effect=requests.ConnectionError("refused")):
        result = api_client.run_campaign(url="https://example.com/article")

    assert "error" in result


def test_get_campaign_returns_none_on_404():
    fake_response = Mock()
    fake_response.status_code = 404
    fake_response.raise_for_status.side_effect = requests.HTTPError(response=fake_response)
    with patch("api_client.requests.get", return_value=fake_response):
        result = api_client.get_campaign(999)

    assert result is None


def test_list_campaigns_returns_empty_list_on_failure():
    with patch("api_client.requests.get", side_effect=requests.ConnectionError("refused")):
        result = api_client.list_campaigns()

    assert result == []


def test_health_keys_returns_false_pair_on_failure():
    with patch("api_client.requests.get", side_effect=requests.ConnectionError("refused")):
        result = api_client.health_keys()

    assert result == {"openai": False, "apollo": False}