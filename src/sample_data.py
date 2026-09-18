# -*- coding: utf-8 -*-
"""
Bundled sample scrape output so the web UI can be tried with zero API keys.

The video/image URLs below point to real, freely-hostable public sample
media (MDN's cc0-licensed test videos, W3Schools' sample clip, Lorem
Picsum placeholder photos) — not real Facebook ads — so sample-mode
downloads actually work and the report shows real thumbnails/video,
not blank placeholders.
"""

_MDN_CC0 = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos"

SAMPLE_RAW_ADS = [
    {
        "adArchiveId": "1001",
        "isActive": True,
        "startDateFormatted": "Jul 1, 2026",
        "endDateFormatted": None,
        "publisherPlatform": ["FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK"],
        "pageInfo": {"page": {"name": "Dot & Key", "pageId": "555"}},
        "snapshot": {
            "title": "Strawberry Niacinamide Serum",
            "body": "Say goodbye to dark spots in 2 weeks. Dermat-approved.",
            "displayFormat": "VIDEO",
            "videos": [{"videoHdUrl": f"{_MDN_CC0}/flower.mp4"}],
        },
    },
    {
        "adArchiveId": "1002",
        "isActive": True,
        "startDateFormatted": "Jul 3, 2026",
        "endDateFormatted": None,
        "publisherPlatform": ["FACEBOOK", "INSTAGRAM"],
        "pageInfo": {"page": {"name": "Dot & Key", "pageId": "555"}},
        "snapshot": {
            "title": "Strawberry Niacinamide Serum",
            "body": "Say goodbye to dark spots in 2 weeks! Clinically proven.",
            "displayFormat": "VIDEO",
            "videos": [{"videoHdUrl": f"{_MDN_CC0}/friday.mp4"}],
        },
    },
    {
        "adArchiveId": "1003",
        "isActive": False,
        "startDateFormatted": "Jan 1, 2026",
        "endDateFormatted": "Jan 5, 2026",
        "publisherPlatform": ["FACEBOOK"],
        "pageInfo": {"page": {"name": "Dot & Key", "pageId": "555"}},
        "snapshot": {
            "title": "Random one-off test ad",
            "body": "50% off today only.",
            "displayFormat": "DCO",
            "cards": [{"originalImageUrl": "https://picsum.photos/seed/dotkey1003/500/500.jpg"}],
        },
    },
    {
        "adArchiveId": "2001",
        "isActive": True,
        "startDateFormatted": "May 10, 2026",
        "endDateFormatted": None,
        "publisherPlatform": ["FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK", "MESSENGER"],
        "pageInfo": {"page": {"name": "Minimalist", "pageId": "777"}},
        "snapshot": {
            "title": "Sunscreen Aqua Gel SPF 50",
            "body": "The sunscreen that doesn't leave a white cast. 60 days, no breakouts.",
            "displayFormat": "VIDEO",
            "videos": [{"videoHdUrl": f"{_MDN_CC0}/friday.mp4"}],
        },
    },
    {
        "adArchiveId": "2002",
        "isActive": True,
        "startDateFormatted": "May 12, 2026",
        "endDateFormatted": None,
        "publisherPlatform": ["FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK"],
        "pageInfo": {"page": {"name": "Minimalist", "pageId": "777"}},
        "snapshot": {
            "title": "Sunscreen Aqua Gel SPF 50",
            "body": "This sunscreen doesn't leave any white cast, dermatologists confirm.",
            "displayFormat": "VIDEO",
            "videos": [{"videoHdUrl": f"{_MDN_CC0}/flower.mp4"}],
        },
    },
]
