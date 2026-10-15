from __future__ import annotations

import json
import urllib.request

from app.config import settings

url = f"http://127.0.0.1:{settings.port}/api/health"
with urllib.request.urlopen(url, timeout=5) as response:
    print(json.dumps(json.load(response), indent=2, ensure_ascii=False))
