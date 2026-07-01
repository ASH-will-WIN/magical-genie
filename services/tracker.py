"""
Builds unique UTM-tagged tracking URLs per lead + channel.
"""
from urllib.parse import urlencode

from config import TRACKING_BASE_URL


def build_tracking_url(campaign_id: int, apollo_id: str, channel: str) -> str:
    params = {
        "cid": campaign_id,
        "lid": apollo_id,
        "utm_source": channel,
        "utm_medium": "outbound",
        "utm_campaign": f"magical_genie_{campaign_id}",
    }
    return f"{TRACKING_BASE_URL}?{urlencode(params)}"
