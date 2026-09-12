"""Print je Garmin sessie als één regel tekst, om in Render's omgevingsvariabele
GARMIN_TOKEN_JSON te plakken. Draai dit alleen lokaal, nooit het resultaat delen
in een chat: wie deze tekst heeft, kan inloggen op je Garmin account."""

import json
from pathlib import Path

pad = Path.home() / ".garmin-coach" / "tokens" / "garmin_tokens.json"
print(json.dumps(json.loads(pad.read_text())))
