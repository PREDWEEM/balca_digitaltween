from pathlib import Path

import numpy as np
import pandas as pd

from predweem_twin.core import ModelParameters, PracticalANNModel, run_predweem
from predweem_twin.seasonal import load_seasonal_reference


ROOT = Path(__file__).parents[1]


def test_partial_run_uses_historical_season_instead_of_ending_at_one():
    weather = pd.read_csv(ROOT / "data" / "meteo_daily.csv")
    weather["Fecha"] = pd.to_datetime(weather["Fecha"])
    cutoff = pd.Timestamp("2026-03-30")
    weather = weather[weather["Fecha"] <= cutoff + pd.Timedelta(days=7)]
    model = PracticalANNModel.from_directory(ROOT / "models")
    reference = load_seasonal_reference(
        ROOT / "models" / "modelo_clusters_k3.pkl",
        excluded_years=(),
        include_patterns=("balcarce",),
    )

    result = run_predweem(
        weather,
        model,
        ModelParameters(cobertura_pct=60.0),
        normalization_as_of=cutoff,
        seasonal_reference=reference,
    )
    at_cutoff = result[result["Fecha"] <= cutoff].iloc[-1]

    assert np.isclose(
        at_cutoff["EMERAC_NORMALIZADA"],
        at_cutoff["Progreso_Estacional_Referencia"],
    )
    assert result.iloc[-1]["EMERAC_NORMALIZADA"] < 1.0
    assert result["Normalizacion_Modo"].eq(
        "referencia estacional histórica"
    ).all()


def test_reference_is_restricted_to_balcarce_campaigns():
    reference = load_seasonal_reference(
        ROOT / "models" / "modelo_clusters_k3.pkl",
        excluded_years=(),
        include_patterns=("balcarce",),
    )

    assert reference["N_Campanas"].eq(1).all()
    assert reference["Campanas"].str.contains("balcarce", case=False).all()
