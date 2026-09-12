"""Eenmalige Garmin login. Draai dit zelf in je terminal.

Je typt hier je eigen Garmin e-mailadres en wachtwoord. Ze worden nergens
opgeslagen: alleen het sessietoken dat Garmin teruggeeft gaat naar
~/.garmin-coach/tokens, een bestand dat alleen jij kunt lezen.
"""

import getpass
import os
from pathlib import Path

from garminconnect import Garmin

TOKENSTORE = str(Path(os.path.expanduser("~/.garmin-coach/tokens")))


def main() -> int:
    email = input("Garmin e-mailadres: ").strip()
    wachtwoord = getpass.getpass("Garmin wachtwoord (blijft onzichtbaar): ")

    garmin = Garmin(
        email,
        wachtwoord,
        prompt_mfa=lambda: input("Verificatiecode uit je mail of app: ").strip(),
    )
    garmin.login(TOKENSTORE)

    print(f"\nGelukt. Ingelogd als {garmin.get_full_name()}.")
    print(f"Sessie opgeslagen in {TOKENSTORE}")
    print("Vanaf nu is je wachtwoord niet meer nodig.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAfgebroken.")
        raise SystemExit(1)
