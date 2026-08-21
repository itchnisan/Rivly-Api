"""Calcul de l'indice de pêchabilité.

Le score agrège des facteurs météo et astronomiques pondérés, chacun ramené sur
une échelle 0..1 par interpolation linéaire entre des points de contrôle. Les
pondérations et les optima sont empiriques : ils viennent des règles usuelles de
la pêche en eau douce, pas d'un modèle entraîné. Ils sont réunis ici pour être
ajustables d'un seul endroit, une fois qu'assez de captures réelles auront été
enregistrées pour les recaler.

Les fonctions de ce module sont pures : elles ne font ni requête réseau ni accès
base, ce qui les rend testables directement.
"""

from datetime import date, datetime, timezone
from typing import Literal, TypedDict

from app.models.species import Species
from app.services.weather_service import WeatherSnapshot

Rating = Literal["poor", "fair", "good", "excellent"]
AdvisoryLevel = Literal["info", "warning", "blocking"]


class FactorResult(TypedDict):
    name: str
    label: str
    weight: int
    score: float
    contribution: float
    detail: str


class AdvisoryResult(TypedDict):
    level: AdvisoryLevel
    message: str


class WeatherResult(TypedDict):
    temperature_c: float
    pressure_hpa: float
    pressure_trend_hpa: float
    cloud_cover_pct: float
    wind_speed_kmh: float
    precipitation_mm: float
    sunrise: datetime
    sunset: datetime


class FishabilityResult(TypedDict):
    at: datetime
    score: float
    rating: Rating
    factors: list[FactorResult]
    advisories: list[AdvisoryResult]
    weather: WeatherResult

# Pondération de chaque facteur, en points sur 100.
FACTOR_WEIGHTS: dict[str, int] = {
    "pressure_trend": 25,
    "time_of_day": 18,
    "cloud_cover": 14,
    "wind": 14,
    "temperature": 14,
    "precipitation": 10,
    "moon_phase": 5,
}

FACTOR_LABELS: dict[str, str] = {
    "pressure_trend": "Tendance barométrique",
    "time_of_day": "Moment de la journée",
    "cloud_cover": "Couverture nuageuse",
    "wind": "Vent",
    "temperature": "Température",
    "precipitation": "Précipitations",
    "moon_phase": "Phase lunaire",
}

# Mois lunaire moyen et nouvelle lune de référence (UTC).
SYNODIC_MONTH_DAYS = 29.530588853
REFERENCE_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


def _interpolate(points: list[tuple[float, float]], x: float) -> float:
    """Interpole linéairement entre des points de contrôle, en bornant aux extrémités."""
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]

    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            ratio = (x - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return points[-1][1]


def moon_illumination(at: datetime) -> float:
    """Position dans le cycle lunaire : 0 = nouvelle lune, 0.5 = pleine lune.

    Modèle à mois lunaire moyen : il ignore l'ellipticité de l'orbite et dérive
    donc de l'ordre d'un jour par rapport aux éphémérides. Négligeable pour un
    facteur pesant 5 points ; à remplacer par une vraie éphéméride si la phase
    devait peser davantage.
    """
    elapsed_days = (at.astimezone(timezone.utc) - REFERENCE_NEW_MOON).total_seconds() / 86400
    return (elapsed_days % SYNODIC_MONTH_DAYS) / SYNODIC_MONTH_DAYS


def _score_pressure_trend(trend_hpa: float) -> tuple[float, str]:
    """Une pression qui baisse doucement avant un front déclenche l'activité.

    C'est le signal le plus fiable, d'où la pondération la plus forte. Une chute
    brutale (orage) ou une remontée franche après un front referment l'activité.
    """
    score = _interpolate(
        [(-8, 0.35), (-3, 0.75), (-1.5, 1.0), (-0.4, 0.85), (0.4, 0.6), (2, 0.4), (5, 0.2)],
        trend_hpa,
    )
    if trend_hpa <= -3:
        detail = f"Chute rapide de {abs(trend_hpa):.1f} hPa sur 3 h — front actif"
    elif trend_hpa < -0.4:
        detail = f"Baisse régulière de {abs(trend_hpa):.1f} hPa sur 3 h — conditions favorables"
    elif trend_hpa <= 0.4:
        detail = "Pression stable"
    else:
        detail = f"Hausse de {trend_hpa:.1f} hPa sur 3 h — activité en berne"
    return score, detail


def _score_time_of_day(at: datetime, sunrise: datetime, sunset: datetime) -> tuple[float, str]:
    """L'aube et le crépuscule restent les deux meilleurs créneaux."""
    hours_to_golden = min(
        abs((at - sunrise).total_seconds()), abs((at - sunset).total_seconds())
    ) / 3600
    score = _interpolate([(0, 1.0), (1, 0.9), (2, 0.7), (4, 0.5), (8, 0.4)], hours_to_golden)

    if hours_to_golden <= 1:
        detail = "Dans le créneau doré (lever ou coucher du soleil)"
    elif hours_to_golden <= 2:
        detail = f"À {hours_to_golden:.1f} h du créneau doré"
    else:
        detail = f"Loin du créneau doré ({hours_to_golden:.1f} h)"
    return score, detail


def _score_cloud_cover(cover_pct: float) -> tuple[float, str]:
    """Un ciel couvert met le poisson en confiance ; le grand soleil le plaque au fond."""
    score = _interpolate(
        [(0, 0.45), (25, 0.6), (50, 0.9), (70, 1.0), (90, 0.85), (100, 0.7)], cover_pct
    )
    if cover_pct < 25:
        detail = f"Ciel dégagé ({cover_pct:.0f} %) — lumière forte"
    elif cover_pct < 70:
        detail = f"Ciel voilé ({cover_pct:.0f} %) — lumière idéale"
    else:
        detail = f"Ciel couvert ({cover_pct:.0f} %)"
    return score, detail


def _score_wind(speed_kmh: float) -> tuple[float, str]:
    """Une brise ride la surface et oxygène l'eau ; le calme plat et le coup de vent nuisent."""
    score = _interpolate(
        [(0, 0.5), (5, 0.75), (10, 1.0), (18, 0.9), (30, 0.5), (45, 0.2), (70, 0.1)], speed_kmh
    )
    if speed_kmh < 5:
        detail = f"Calme plat ({speed_kmh:.0f} km/h) — surface lisse"
    elif speed_kmh <= 18:
        detail = f"Brise favorable ({speed_kmh:.0f} km/h)"
    elif speed_kmh <= 30:
        detail = f"Vent soutenu ({speed_kmh:.0f} km/h)"
    else:
        detail = f"Vent fort ({speed_kmh:.0f} km/h) — pêche difficile"
    return score, detail


def _score_temperature(temp_c: float) -> tuple[float, str]:
    """Approximation par la température de l'air, faute de température d'eau.

    L'eau suit l'air avec de l'inertie : c'est le maillon faible du modèle, à
    remplacer par une vraie mesure ou une estimation par inertie thermique.
    """
    score = _interpolate(
        [(-5, 0.15), (2, 0.3), (8, 0.6), (14, 0.95), (19, 1.0), (25, 0.8), (30, 0.5), (38, 0.2)],
        temp_c,
    )
    if temp_c < 8:
        detail = f"{temp_c:.0f} °C — eau froide, poisson lent"
    elif temp_c <= 25:
        detail = f"{temp_c:.0f} °C — plage favorable"
    else:
        detail = f"{temp_c:.0f} °C — eau chaude, moins d'oxygène"
    return score, detail


def _score_precipitation(precip_mm: float) -> tuple[float, str]:
    """Une pluie fine brouille la surface et fait manger ; la grosse pluie trouble tout."""
    score = _interpolate([(0, 0.8), (0.3, 1.0), (2, 0.8), (6, 0.45), (15, 0.2)], precip_mm)
    if precip_mm < 0.1:
        detail = "Temps sec"
    elif precip_mm <= 2:
        detail = f"Pluie fine ({precip_mm:.1f} mm/h) — favorable"
    else:
        detail = f"Pluie soutenue ({precip_mm:.1f} mm/h)"
    return score, detail


def _score_moon_phase(at: datetime) -> tuple[float, str]:
    """Théorie solunaire : activité accrue autour de la nouvelle et de la pleine lune.

    Bien moins étayé que les autres facteurs, d'où sa pondération marginale.
    """
    phase = moon_illumination(at)
    distance = min(phase, abs(phase - 0.5), 1 - phase)
    score = 0.6 + 0.4 * (1 - distance / 0.25)

    if phase < 0.03 or phase > 0.97:
        detail = "Nouvelle lune"
    elif 0.47 < phase < 0.53:
        detail = "Pleine lune"
    elif distance < 0.1:
        detail = "Proche d'une nouvelle ou pleine lune"
    else:
        detail = "Quartier de lune"
    return score, detail


def is_species_in_season(species: Species, at_date: date) -> bool | None:
    """Indique si l'espèce est ouverte à cette date, ou None si la saison est inconnue.

    Seuls le mois et le jour comptent : la saison se répète chaque année, alors
    que les colonnes stockent une date complète. Une saison dont le début tombe
    après la fin (brochet, par exemple) chevauche le nouvel an.
    """
    start, end = species.open_season_start, species.open_season_end
    if start is None or end is None:
        return None

    start_md = (start.month, start.day)
    end_md = (end.month, end.day)
    today_md = (at_date.month, at_date.day)

    if start_md <= end_md:
        return start_md <= today_md <= end_md
    return today_md >= start_md or today_md <= end_md


def rating_for(score: float) -> Rating:
    if score < 3.5:
        return "poor"
    if score < 5.5:
        return "fair"
    if score < 7.5:
        return "good"
    return "excellent"


def compute_factors(snapshot: WeatherSnapshot) -> list[FactorResult]:
    """Évalue chaque facteur et le pondère. La somme des contributions donne le score."""
    raw = {
        "pressure_trend": _score_pressure_trend(snapshot.pressure_trend_hpa),
        "time_of_day": _score_time_of_day(snapshot.at, snapshot.sunrise, snapshot.sunset),
        "cloud_cover": _score_cloud_cover(snapshot.cloud_cover_pct),
        "wind": _score_wind(snapshot.wind_speed_kmh),
        "temperature": _score_temperature(snapshot.temperature_c),
        "precipitation": _score_precipitation(snapshot.precipitation_mm),
        "moon_phase": _score_moon_phase(snapshot.at),
    }

    factors: list[FactorResult] = []
    for name, (score, detail) in raw.items():
        weight = FACTOR_WEIGHTS[name]
        factors.append(
            {
                "name": name,
                "label": FACTOR_LABELS[name],
                "weight": weight,
                "score": round(score, 3),
                "contribution": round(weight * score, 2),
                "detail": detail,
            }
        )
    return factors


def build_advisories(species: Species | None, at: datetime) -> list[AdvisoryResult]:
    advisories: list[AdvisoryResult] = []
    if species is None:
        return advisories

    in_season = is_species_in_season(species, at.date())
    if in_season is False:
        advisories.append(
            {
                "level": "blocking",
                "message": f"{species.common_name} est hors saison à cette date.",
            }
        )
    elif in_season is None:
        advisories.append(
            {
                "level": "info",
                "message": f"Aucune saison renseignée pour {species.common_name}.",
            }
        )

    if species.legal_size_cm is not None:
        advisories.append(
            {
                "level": "info",
                "message": (
                    f"Taille légale de capture pour {species.common_name} : "
                    f"{species.legal_size_cm:.0f} cm."
                ),
            }
        )
    return advisories


def compute_fishability(
    snapshot: WeatherSnapshot, species: Species | None = None
) -> FishabilityResult:
    """Assemble le score, ses facteurs et les avis réglementaires.

    Une espèce hors saison force le score à zéro : la question posée est « est-ce
    que je vais pêcher ça ici maintenant », et la réponse est non quelle que soit
    la pression atmosphérique. Les facteurs restent renvoyés tels quels pour que
    le détail reste lisible.
    """
    factors = compute_factors(snapshot)
    advisories = build_advisories(species, snapshot.at)

    blocked = any(advisory["level"] == "blocking" for advisory in advisories)
    # Les facteurs contribuent sur 100 (poids historiques) ; l'indice affiché est /10.
    score = 0.0 if blocked else round(sum(f["contribution"] for f in factors) / 10, 1)

    return {
        "at": snapshot.at,
        "score": score,
        "rating": rating_for(score),
        "factors": factors,
        "advisories": advisories,
        "weather": {
            "temperature_c": snapshot.temperature_c,
            "pressure_hpa": snapshot.pressure_hpa,
            "pressure_trend_hpa": round(snapshot.pressure_trend_hpa, 2),
            "cloud_cover_pct": snapshot.cloud_cover_pct,
            "wind_speed_kmh": snapshot.wind_speed_kmh,
            "precipitation_mm": snapshot.precipitation_mm,
            "sunrise": snapshot.sunrise,
            "sunset": snapshot.sunset,
        },
    }
