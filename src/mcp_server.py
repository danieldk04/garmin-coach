"""Garmin coach: MCP server die live je eigen Garmin Connect data ophaalt.

Elke vraag haalt de gegevens op het moment zelf op, dus je ziet precies wat er
ook in de Garmin Connect app staat. Verser dan dat kan niet: het horloge zet
zijn gegevens naar Garmin toe bij elke synchronisatie met je telefoon.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

import garmin_client as gc  # noqa: E402

mcp = MCPServer("garmin-coach", instructions=__doc__)

MAX_LIJST = 12  # lange reeksen meetpunten inkorten, anders wordt elk antwoord onleesbaar


def _krimp(waarde: Any, diepte: int = 0) -> Any:
    """Haal lege velden weg en kort hele lange reeksen in."""
    if diepte > 6:
        return waarde
    if isinstance(waarde, dict):
        uit = {}
        for sleutel, inhoud in waarde.items():
            if inhoud is None or inhoud == [] or inhoud == {}:
                continue
            uit[sleutel] = _krimp(inhoud, diepte + 1)
        return uit
    if isinstance(waarde, list):
        if len(waarde) > MAX_LIJST:
            kort = [_krimp(x, diepte + 1) for x in waarde[:MAX_LIJST]]
            kort.append(f"... nog {len(waarde) - MAX_LIJST} metingen weggelaten")
            return kort
        return [_krimp(x, diepte + 1) for x in waarde]
    return waarde


def _veilig(naam: str, *args, **kwargs) -> Any:
    """Eén onderdeel mag ontbreken zonder dat het hele antwoord sneuvelt."""
    try:
        return _krimp(gc.call(naam, *args, **kwargs))
    except gc.NietIngelogd:
        raise
    except Exception as fout:
        return {"niet_beschikbaar": str(fout)[:200]}


def _eerste(bron: Any, *sleutels: str) -> Any:
    if not isinstance(bron, dict):
        return None
    for sleutel in sleutels:
        if bron.get(sleutel) is not None:
            return bron[sleutel]
    return None


def _pluk(bron: Any, velden: dict[str, str]) -> dict:
    """Kies alleen de velden die ertoe doen en geef ze een leesbare naam."""
    if not isinstance(bron, dict):
        return {}
    uit = {}
    for nieuw, oud in velden.items():
        waarde = bron.get(oud)
        if waarde is not None:
            uit[nieuw] = round(waarde, 1) if isinstance(waarde, float) else waarde
    return uit


DAGVELDEN = {
    "rusthartslag": "restingHeartRate",
    "laagste_hartslag": "minHeartRate",
    "hoogste_hartslag": "maxHeartRate",
    "stappen": "totalSteps",
    "stappendoel": "dailyStepGoal",
    "afstand_m": "totalDistanceMeters",
    "gem_stress": "averageStressLevel",
    "max_stress": "maxStressLevel",
    "stress_oordeel": "stressQualifier",
    "bb_nu": "bodyBatteryMostRecentValue",
    "bb_hoogste": "bodyBatteryHighestValue",
    "bb_laagste": "bodyBatteryLowestValue",
    "bb_geladen": "bodyBatteryChargedValue",
    "bb_verbruikt": "bodyBatteryDrainedValue",
    "actieve_calorieen": "activeKilocalories",
    "totale_calorieen": "totalKilocalories",
    "matige_intensiteit_min": "moderateIntensityMinutes",
    "hoge_intensiteit_min": "vigorousIntensityMinutes",
    "gem_ademhaling": "avgWakingRespirationValue",
    "gem_spo2": "averageSpo2",
    "slaap_seconden": "sleepingSeconds",
}

NACHTVELDEN = {
    "slaapscore": "sleepScore",
    "slaapkwaliteit": "sleepScoreQuality",
    "slaap_uren": "totalSleepTimeInSeconds",
    "diep_min": "deepTime",
    "rem_min": "remTime",
    "licht_min": "lightTime",
    "wakker_min": "awakeTime",
    "hrv_nacht": "avgOvernightHrv",
    "hrv_week": "hrv7dAverage",
    "hrv_status": "hrvStatus",
    "rusthartslag": "restingHeartRate",
    "gem_hartslag": "avgHeartRate",
    "ademhaling": "respiration",
    "bb_opgeladen": "bodyBatteryChange",
    "slaapbehoefte_min": "sleepNeed",
}


def _nacht(waarden: Any) -> dict:
    """Zet een nacht om naar uren en minuten in plaats van seconden."""
    rij = _pluk(waarden, NACHTVELDEN)
    if isinstance(rij.get("slaap_uren"), (int, float)):
        rij["slaap_uren"] = round(rij["slaap_uren"] / 3600, 1)
    for veld in ("diep_min", "rem_min", "licht_min", "wakker_min"):
        if isinstance(rij.get(veld), (int, float)):
            rij[veld] = round(rij[veld] / 60)
    return rij


def _laatste_sync() -> dict:
    """Wanneer heeft het horloge voor het laatst gesynchroniseerd."""
    rauw = _veilig("get_device_last_used")
    if not isinstance(rauw, dict):
        return {}
    stempel = _eerste(rauw, "lastUsedDeviceUploadTime")
    leesbaar = None
    if isinstance(stempel, (int, float)):
        leesbaar = datetime.fromtimestamp(stempel / 1000).isoformat(timespec="minutes")
    return {
        "horloge": _eerste(rauw, "lastUsedDeviceName", "displayName"),
        "laatste_synchronisatie": leesbaar,
    }


@mcp.tool()
def status_nu() -> dict:
    """Actuele status op dit moment: hoe uitgerust ben ik, hoe was mijn nacht,
    wat is mijn Body Battery, stress, rusthartslag en HRV. Gebruik dit voor
    vragen als 'hoe sta ik ervoor', 'kan ik vandaag hard trainen', 'hoe was
    mijn herstel'. Haalt de gegevens live op bij Garmin."""
    vandaag = gc.vandaag()

    readiness = _veilig("get_training_readiness", vandaag)
    if isinstance(readiness, list) and readiness:
        readiness = readiness[0]

    hrv = _veilig("get_hrv_data", vandaag)
    nachten = _veilig("get_sleep_daily", gc.dagen_terug(1), vandaag)
    laatste_nacht = {}
    if isinstance(nachten, list) and nachten:
        laatste = nachten[-1]
        laatste_nacht = {"datum": laatste.get("calendarDate")}
        laatste_nacht.update(_nacht(laatste.get("values")))

    status = _veilig("get_training_status", vandaag)
    vo2 = None
    if isinstance(status, dict):
        vo2 = ((status.get("mostRecentVO2Max") or {}).get("generic") or {}).get(
            "vo2MaxPreciseValue"
        )

    return {
        "opgehaald_op": datetime.now().isoformat(timespec="seconds"),
        "datum": vandaag,
        "apparaat": _laatste_sync(),
        "trainingsgereedheid": _pluk(
            readiness,
            {
                "score": "score",
                "niveau": "level",
                "toelichting": "feedbackShort",
                "slaapscore": "sleepScore",
                "hersteltijd_uren": "recoveryTime",
                "acute_belasting": "acuteLoad",
                "hrv_factor": "hrvFactorPercent",
                "slaapfactor": "sleepScoreFactorPercent",
                "stressfactor": "stressHistoryFactorPercent",
                "gemeten_om": "timestampLocal",
            },
        ),
        "hrv": _pluk(
            hrv.get("hrvSummary") if isinstance(hrv, dict) else None,
            {
                "afgelopen_nacht": "lastNightAvg",
                "weekgemiddelde": "weeklyAvg",
                "hoogste_5min": "lastNight5MinHigh",
                "status": "status",
            },
        ),
        "slaap_afgelopen_nacht": laatste_nacht,
        "vandaag_tot_nu": _pluk(_veilig("get_stats", vandaag), DAGVELDEN),
        "vo2max": vo2,
    }


@mcp.tool()
def dag(datum: str) -> dict:
    """Volledig beeld van één dag (datum als JJJJ-MM-DD): slaap, stress,
    Body Battery, hartslag, stappen, HRV en trainingsgereedheid."""
    nachten = _veilig("get_sleep_daily", datum, datum)
    nacht = {}
    if isinstance(nachten, list) and nachten:
        nacht = _nacht(nachten[-1].get("values"))

    readiness = _veilig("get_training_readiness", datum)
    if isinstance(readiness, list) and readiness:
        readiness = readiness[0]

    hrv = _veilig("get_hrv_data", datum)
    stress = _veilig("get_all_day_stress", datum)
    bb = _veilig("get_body_battery", datum, datum)
    bb_dag = {}
    if isinstance(bb, list) and bb and isinstance(bb[0], dict):
        bb_dag = {"opgeladen": bb[0].get("charged"), "verbruikt": bb[0].get("drained")}

    trainingen = []
    for a in (_veilig("get_activities_fordate", datum) or {}).get(
        "ActivitiesForDay", {}
    ).get("payload", []) or []:
        if isinstance(a, dict):
            trainingen.append(
                {
                    "naam": a.get("activityName"),
                    "soort": (a.get("activityType") or {}).get("typeKey"),
                    "duur_min": round(a["duration"] / 60, 1) if a.get("duration") else None,
                    "gem_hartslag": a.get("averageHR"),
                    "calorieen": a.get("calories"),
                }
            )

    return {
        "datum": datum,
        "dagtotalen": _pluk(_veilig("get_stats", datum), DAGVELDEN),
        "slaap": nacht,
        "hrv": _pluk(
            hrv.get("hrvSummary") if isinstance(hrv, dict) else None,
            {
                "afgelopen_nacht": "lastNightAvg",
                "weekgemiddelde": "weeklyAvg",
                "status": "status",
            },
        ),
        "stress": _pluk(
            stress,
            {
                "gemiddeld": "avgStressLevel",
                "hoogste": "maxStressLevel",
                "rust_seconden": "restStressDuration",
                "lage_stress_seconden": "lowStressDuration",
                "gemiddelde_stress_seconden": "mediumStressDuration",
                "hoge_stress_seconden": "highStressDuration",
            },
        ),
        "body_battery": bb_dag,
        "trainingsgereedheid": _pluk(
            readiness,
            {
                "score": "score",
                "niveau": "level",
                "toelichting": "feedbackShort",
                "hersteltijd_uren": "recoveryTime",
                "acute_belasting": "acuteLoad",
            },
        ),
        "trainingen": trainingen,
    }


@mcp.tool()
def trend(dagen: int = 14) -> dict:
    """Compacte reeks per dag over de afgelopen periode: slaapduur en score,
    HRV, rusthartslag, Body Battery, stappen. Gebruik dit voor vergelijkingen
    en vragen over patronen, bijvoorbeeld 'hoe was mijn herstel deze week
    vergeleken met vorige maand'."""
    dagen = max(2, min(int(dagen), 90))
    start = gc.dagen_terug(dagen - 1)
    eind = gc.vandaag()

    rijen: dict[str, dict] = {}

    def rij(datum: Any) -> dict:
        return rijen.setdefault(str(datum), {"datum": str(datum)})

    for nacht in _veilig("get_sleep_daily", start, eind) or []:
        if isinstance(nacht, dict):
            rij(nacht.get("calendarDate")).update(_nacht(nacht.get("values")))

    for dag_bb in _veilig("get_body_battery", start, eind) or []:
        if isinstance(dag_bb, dict):
            r = rij(dag_bb.get("date"))
            r["bb_geladen"] = dag_bb.get("charged")
            r["bb_verbruikt"] = dag_bb.get("drained")

    for dag_stap in _veilig("get_daily_steps", start, eind) or []:
        if isinstance(dag_stap, dict):
            rij(dag_stap.get("calendarDate"))["stappen"] = dag_stap.get("totalSteps")

    for dag_rhr in _veilig("get_rhr_daily", start, eind) or []:
        if isinstance(dag_rhr, dict) and dag_rhr.get("value") is not None:
            rij(dag_rhr.get("calendarDate"))["rusthartslag"] = dag_rhr["value"]

    return {
        "periode": f"{start} tot en met {eind}",
        "per_dag": [rijen[k] for k in sorted(rijen) if k != "None"],
        "stress_per_week": _veilig("get_weekly_stress", eind, max(2, dagen // 7 + 1)),
    }


@mcp.tool()
def slaap(dagen: int = 7) -> dict:
    """Slaapdetails over de afgelopen dagen: duur, diepe slaap, REM, wakker,
    slaapscore, HRV tijdens de nacht, ademhaling en rusthartslag."""
    dagen = max(1, min(int(dagen), 60))
    start = gc.dagen_terug(dagen - 1)
    nachten = []
    for nacht in _veilig("get_sleep_daily", start, gc.vandaag()) or []:
        if isinstance(nacht, dict):
            regel = {"datum": nacht.get("calendarDate")}
            regel.update(_nacht(nacht.get("values")))
            nachten.append(regel)
    return {"periode": f"{start} tot en met {gc.vandaag()}", "nachten": nachten}


@mcp.tool()
def activiteiten(aantal: int = 10) -> dict:
    """De laatste trainingen met afstand, duur, tempo, hartslag en
    trainingseffect. Gebruik dit voor vragen over workouts en hardlopen."""
    aantal = max(1, min(int(aantal), 50))
    lijst = _veilig("get_activities", 0, aantal)
    if not isinstance(lijst, list):
        return {"activiteiten": lijst}
    kort = []
    for a in lijst:
        if not isinstance(a, dict):
            continue
        kort.append(
            {
                "id": a.get("activityId"),
                "naam": a.get("activityName"),
                "soort": (a.get("activityType") or {}).get("typeKey"),
                "start": a.get("startTimeLocal"),
                "duur_min": round(a["duration"] / 60, 1) if a.get("duration") else None,
                "afstand_km": round(a["distance"] / 1000, 2) if a.get("distance") else None,
                "gem_hartslag": a.get("averageHR"),
                "max_hartslag": a.get("maxHR"),
                "calorieen": a.get("calories"),
                "aeroob_effect": a.get("aerobicTrainingEffect"),
                "anaeroob_effect": a.get("anaerobicTrainingEffect"),
                "gem_tempo_min_per_km": round(1000 / a["averageSpeed"] / 60, 2)
                if a.get("averageSpeed")
                else None,
                "hoogtemeters": a.get("elevationGain"),
            }
        )
    return {"activiteiten": kort}


@mcp.tool()
def activiteit(activiteit_id: str) -> dict:
    """Alle details van één training, opgehaald met het id uit activiteiten()."""
    return {
        "samenvatting": _veilig("get_activity", activiteit_id),
        "rondes": _veilig("get_activity_splits", activiteit_id),
        "hartslagzones": _veilig("get_activity_hr_in_timezones", activiteit_id),
    }


def _tijden(voorspelling: Any) -> dict:
    """Zet voorspelde wedstrijdtijden om van seconden naar uu:mm:ss."""
    namen = {
        "time5K": "5 km",
        "time10K": "10 km",
        "timeHalfMarathon": "halve marathon",
        "timeMarathon": "marathon",
    }
    uit = {}
    for sleutel, naam in namen.items():
        s = voorspelling.get(sleutel) if isinstance(voorspelling, dict) else None
        if isinstance(s, (int, float)):
            uren, rest = divmod(int(s), 3600)
            minuten, seconden = divmod(rest, 60)
            uit[naam] = (
                f"{uren}:{minuten:02d}:{seconden:02d}"
                if uren
                else f"{minuten}:{seconden:02d}"
            )
    return uit


@mcp.tool()
def conditie() -> dict:
    """Langetermijnbeeld: VO2max, trainingsstatus en trainingsbelasting,
    uithoudingsscore, heuvelscore en voorspelde wedstrijdtijden."""
    vandaag = gc.vandaag()
    status = _veilig("get_training_status", vandaag)

    vo2, belasting, samenvatting = None, {}, {}
    if isinstance(status, dict):
        vo2 = ((status.get("mostRecentVO2Max") or {}).get("generic") or {}).get(
            "vo2MaxPreciseValue"
        )
        per_apparaat = (status.get("mostRecentTrainingStatus") or {}).get(
            "latestTrainingStatusData"
        ) or {}
        laatste = next(iter(per_apparaat.values()), {}) if per_apparaat else {}
        acuut = laatste.get("acuteTrainingLoadDTO") or {}
        samenvatting = {
            "datum": laatste.get("calendarDate"),
            "sinds": laatste.get("sinceDate"),
            "oordeel": laatste.get("trainingStatusFeedbackPhrase"),
            "gepauzeerd": laatste.get("trainingPaused"),
        }
        belasting = {
            "acute_belasting": acuut.get("dailyTrainingLoadAcute"),
            "chronische_belasting": acuut.get("dailyTrainingLoadChronic"),
            "verhouding": acuut.get("dailyAcuteChronicWorkloadRatio"),
            "oordeel": acuut.get("acwrStatus"),
            "streefbereik": [
                acuut.get("minTrainingLoadChronic"),
                acuut.get("maxTrainingLoadChronic"),
            ],
        }

    uithouding = _veilig("get_endurance_score", vandaag)
    heuvel = _veilig("get_hill_score", gc.dagen_terug(30), vandaag)

    return {
        "vo2max": vo2,
        "trainingsstatus": _krimp(samenvatting),
        "belastingverdeling": _krimp(belasting),
        "uithoudingsscore": {
            "score": _eerste(uithouding, "overallScore"),
            "niveau": _eerste(uithouding, "classification", "feedbackPhrase"),
        },
        "heuvelscore": _eerste(heuvel, "periodAvgScore", "maxScore", "overallScore"),
        "wedstrijdvoorspellingen": _tijden(_veilig("get_race_predictions")),
    }


@mcp.tool()
def garmin_endpoint(pad: str) -> Any:
    """Noodgreep: haal een willekeurig Garmin Connect endpoint op als er iets
    nodig is dat de andere functies niet geven. Pad begint met een schuine streep."""
    if not pad.startswith("/"):
        pad = "/" + pad
    return _veilig("connectapi", pad)


if __name__ == "__main__":
    mcp.run()
