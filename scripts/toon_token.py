"""Kopieert je Garmin sessie direct naar het klembord, klaar om in Render's
GARMIN_TOKEN_JSON veld te plakken. Niets handmatig selecteren nodig, dat is
precies waar het eerder misging. Draai dit alleen lokaal, deel de uitkomst
nooit in een chat: wie deze tekst heeft, kan inloggen op je Garmin account."""

import json
import subprocess
from pathlib import Path

pad = Path.home() / ".garmin-coach" / "tokens" / "garmin_tokens.json"
tekst = json.dumps(json.loads(pad.read_text()))

subprocess.run("pbcopy", input=tekst.encode(), check=True)
print(f"Klaar. {len(tekst)} tekens staan nu op je klembord.")
print("Ga naar Render, klik in het GARMIN_TOKEN_JSON veld, maak het leeg")
print("en plak met cmd+V. Niets hier uit de terminal kopiëren.")
