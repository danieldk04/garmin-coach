"""Webserver voor de Garmin coach app.

Levert twee dingen: een dashboard met de actuele cijfers, en een chat die
dezelfde gegevens live kan opvragen en er vragen over beantwoordt.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google import genai  # noqa: E402
from google.genai import types as gtypes  # noqa: E402

import garmin_client as gc  # noqa: E402
import mcp_server as tools  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "web"
TOEGANGSCODE = os.getenv("TOEGANGSCODE", "")
MODEL = "gemini-3.6-flash"

app = FastAPI(title="Garmin coach")
gemini = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _bewaak(code: str | None) -> None:
    if TOEGANGSCODE and code != TOEGANGSCODE:
        raise HTTPException(status_code=401, detail="Geen toegang")


# --------------------------------------------------------------------------- #
#  Dashboard
# --------------------------------------------------------------------------- #


def _hartslag_nu() -> dict:
    """Laatste gemeten hartslag van vandaag, met het tijdstip erbij."""
    rauw = gc.call("get_heart_rates", gc.vandaag())
    if not isinstance(rauw, dict):
        return {}
    metingen = [m for m in (rauw.get("heartRateValues") or []) if m and m[1] is not None]
    laatste = metingen[-1] if metingen else None
    return {
        "nu": laatste[1] if laatste else None,
        "gemeten_om": datetime.fromtimestamp(laatste[0] / 1000).strftime("%H:%M")
        if laatste
        else None,
        "rust": rauw.get("restingHeartRate"),
        "rust_week": rauw.get("lastSevenDaysAvgRestingHeartRate"),
    }


def dashboard() -> dict:
    """De cijfers die op het scherm passen. Niet meer dan dat."""
    vandaag = gc.vandaag()

    gereed = gc.call("get_training_readiness", vandaag)
    gereed = gereed[0] if isinstance(gereed, list) and gereed else {}

    hrv = (gc.call("get_hrv_data", vandaag) or {}).get("hrvSummary") or {}
    stats = gc.call("get_stats", vandaag) or {}
    hart = _hartslag_nu()

    nachten = gc.call("get_sleep_daily", gc.dagen_terug(1), vandaag) or []
    nacht = nachten[-1].get("values", {}) if nachten else {}

    reeks = gc.call("get_hrv_data_range", gc.dagen_terug(6), vandaag) or {}
    verloop = [
        {"datum": d.get("calendarDate"), "hrv": d.get("lastNightAvg")}
        for d in (reeks.get("hrvSummaries") or [])
        if isinstance(d, dict) and d.get("lastNightAvg")
    ]

    return {
        "opgehaald_om": datetime.now().strftime("%H:%M:%S"),
        "sync": tools._laatste_sync(),
        "groet": _groet(),
        "inzicht": _inzicht(gereed, hrv, nacht, stats),
        "gereedheid": {
            "score": gereed.get("score"),
            "niveau": gereed.get("level"),
            "hersteltijd": gereed.get("recoveryTime"),
        },
        "hrv": {
            "nacht": hrv.get("lastNightAvg"),
            "week": hrv.get("weeklyAvg"),
            "status": hrv.get("status"),
            "verloop": verloop,
        },
        "hartslag": hart,
        "body_battery": {
            "nu": stats.get("bodyBatteryMostRecentValue"),
            "hoogste": stats.get("bodyBatteryHighestValue"),
            "laagste": stats.get("bodyBatteryLowestValue"),
        },
        "slaap": {
            "uren": round((nacht.get("totalSleepTimeInSeconds") or 0) / 3600, 1) or None,
            "score": nacht.get("sleepScore"),
            "kwaliteit": nacht.get("sleepScoreQuality"),
        },
        "stress": {
            "gemiddeld": stats.get("averageStressLevel"),
            "hoogste": stats.get("maxStressLevel"),
        },
        "stappen": {
            "aantal": stats.get("totalSteps"),
            "doel": stats.get("dailyStepGoal"),
        },
    }


def _groet() -> str:
    uur = datetime.now().hour
    if uur < 12:
        return "Goedemorgen"
    if uur < 18:
        return "Goedemiddag"
    return "Goedenavond"


def _inzicht(gereed: dict, hrv: dict, nacht: dict, stats: dict) -> str:
    """Eén korte zin die zegt wat de cijfers vandaag betekenen, zoals een coach dat doet."""
    score = gereed.get("score")
    hrv_status = hrv.get("status")
    slaapscore = nacht.get("sleepScore")

    if score is not None and score >= 75:
        basis = "Je bent goed hersteld, ruimte voor een stevige inspanning vandaag."
    elif score is not None and score >= 50:
        basis = "Redelijk hersteld. Een normale training kan, ga niet over je grens."
    elif score is not None:
        basis = "Nog niet volledig hersteld. Neem het vandaag rustiger aan."
    else:
        basis = "Nog geen recente meting binnen."

    if hrv_status == "UNBALANCED" and slaapscore and slaapscore < 70:
        basis += " Je HRV en slaap zijn beide onder je gemiddelde, let op vermoeidheid."
    elif hrv_status == "UNBALANCED":
        basis += " Je HRV wijkt af van je gemiddelde."
    elif slaapscore and slaapscore < 65:
        basis += " Je sliep minder goed dan gebruikelijk."

    return basis


@app.get("/api/dashboard")
def api_dashboard(x_toegang: str | None = Header(default=None)) -> dict:
    _bewaak(x_toegang)
    try:
        return dashboard()
    except gc.NietIngelogd as fout:
        raise HTTPException(status_code=503, detail=str(fout)) from fout


# --------------------------------------------------------------------------- #
#  Chat
# --------------------------------------------------------------------------- #

SYSTEEM = """Je bent de persoonlijke coach van Daniel en je kijkt mee met zijn
Garmin gegevens. Je praat Nederlands, kort en concreet, zoals een goede coach
dat doet: zeg wat je ziet, wat dat betekent en wat hij eraan heeft.

Regels:
- Geef nooit meer cijfers dan nodig. Twee of drie getallen die ertoe doen zijn
  beter dan een opsomming.
- Wijs op patronen over meerdere dagen, niet alleen op vandaag.
- Gebruik de functies om gegevens op te halen als je ze nodig hebt. De cijfers
  van dit moment krijg je al mee in de vraag.
- Gebruik nooit een gedachtestreepje of los streepje als leesteken.
- Je bent geen arts. Gaat het over pijn, ziekte of medicijnen, zeg dan dat hij
  daarvoor bij een dokter moet zijn.
- Zijn cijfers goed, zeg dat dan gewoon. Niet zoeken naar problemen."""


def geschiedenis(dagen: int = 14) -> str:
    """Haal de reeks per dag op: slaap, HRV, rusthartslag, Body Battery, stappen.

    Args:
        dagen: Hoeveel dagen terug, maximaal 90.
    """
    import json

    return json.dumps(tools.trend(dagen), default=str, ensure_ascii=False)


def trainingen(aantal: int = 10) -> str:
    """Haal de laatste trainingen op met duur, hartslag en trainingseffect.

    Args:
        aantal: Hoeveel trainingen, maximaal 50.
    """
    import json

    return json.dumps(tools.activiteiten(aantal), default=str, ensure_ascii=False)


def een_dag(datum: str) -> str:
    """Haal alles van één dag op.

    Args:
        datum: De dag in de vorm JJJJ-MM-DD.
    """
    import json

    return json.dumps(tools.dag(datum), default=str, ensure_ascii=False)


def langetermijn() -> str:
    """Haal VO2max, trainingsstatus, belasting en wedstrijdvoorspellingen op."""
    import json

    return json.dumps(tools.conditie(), default=str, ensure_ascii=False)


GEREEDSCHAP = [geschiedenis, trainingen, een_dag, langetermijn]


class Vraag(BaseModel):
    vraag: str
    geschiedenis: list[dict[str, Any]] = []


@app.post("/api/chat")
def api_chat(verzoek: Vraag, x_toegang: str | None = Header(default=None)) -> dict:
    _bewaak(x_toegang)
    import json

    nu = json.dumps(dashboard(), default=str, ensure_ascii=False)

    berichten: list[gtypes.Content] = []
    for regel in verzoek.geschiedenis[-8:]:
        if regel.get("rol") in ("user", "assistant") and regel.get("tekst"):
            rol = "user" if regel["rol"] == "user" else "model"
            berichten.append(gtypes.Content(role=rol, parts=[gtypes.Part(text=regel["tekst"])]))
    berichten.append(
        gtypes.Content(
            role="user",
            parts=[
                gtypes.Part(
                    text=f"Zijn cijfers van dit moment:\n{nu}\n\nZijn vraag: {verzoek.vraag}"
                )
            ],
        )
    )

    try:
        antwoord_obj = gemini.models.generate_content(
            model=MODEL,
            contents=berichten,
            config=gtypes.GenerateContentConfig(
                system_instruction=SYSTEEM,
                tools=GEREEDSCHAP,
                automatic_function_calling=gtypes.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=6
                ),
            ),
        )
    except Exception as fout:
        raise HTTPException(status_code=502, detail=f"Gemini gaf een fout: {fout}") from fout

    antwoord = (antwoord_obj.text or "").strip()
    return {"antwoord": antwoord or "Geen antwoord gekregen."}


# --------------------------------------------------------------------------- #
#  De app zelf
# --------------------------------------------------------------------------- #


@app.get("/")
def start() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")
