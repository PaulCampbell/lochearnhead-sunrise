#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.wifi_portal_template import render_root_html


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the CritterCam Wi-Fi captive portal HTML to a static file for desktop browser testing."
    )
    parser.add_argument(
        "--out",
        default="wifi-portal.html",
        help="Output HTML filename (default: wifi-portal.html)",
    )
    parser.add_argument(
        "--ssid",
        action="append",
        default=[],
        help="SSID to include (repeatable). If omitted, uses a sample list.",
    )

    args = parser.parse_args()

    ssids = args.ssid or [
        "CritterCam-Guest",
        "Home WiFi",
        "Mobile Hotspot",
        "TestNetwork_2G",
    ]

    html = render_root_html(ssids)
    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
