"""Composición, peso por campaña y disponibilidad del pool de Balcarce."""

from pathlib import Path
import json
import pickle
import shutil

import numpy as np
import pandas as pd
import pytest

from predweem_twin.seasonal import load_local_seasonal_reference, load_seasonal_reference
from predweem_twin.flows import historical_weekly_max


ROOT = Path(__file__).parents[1]
YEARS = (2025,)
COUNTS = Path("data/calibration/balcarce_2026_counts.csv")
MODEL = Path("models/modelo_clusters_k3.pkl")
W2014 = Path("data/reference/balcarce_2014_weekly.csv")
S2014 = Path("data/reference/balcarce_2014_source.json")
P2014 = Path("data/reference/balcarce_2014_diez_de_ulzurrun_2015.pdf")


@pytest.fixture
def local_files(tmp_path):
    for path in (COUNTS, MODEL, W2014, S2014, P2014):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, tmp_path / path)
    return tmp_path


def test_three_campaign_percentiles_have_equal_individual_weight():
    reference = load_local_seasonal_reference(ROOT, "2027-05-05")
    with (ROOT / MODEL).open("rb") as handle:
        payload = pickle.load(handle)
    expected = []
    for year in YEARS:
        raw = np.asarray(payload["curves_interp"])[payload["names"].index("emererel2025 balcarce.xlsx")]
        expected.append(raw.cumsum() / raw.sum())
    counts = pd.read_csv(ROOT / COUNTS)
    flows = counts["PLM2"].to_numpy()
    dates = pd.to_datetime(counts.FECHA)
    expected.append(np.interp(
        reference.Julian_days, dates.dt.dayofyear, flows.cumsum() / flows.sum(),
        left=np.nan, right=1.,
    ))
    weekly = pd.read_csv(ROOT / W2014)
    weekly_dates = pd.to_datetime(weekly.FECHA)
    expected.insert(0, np.interp(
        reference.Julian_days, weekly_dates.dt.dayofyear,
        weekly.PORC_SEMANAL.cumsum() / weekly.PORC_SEMANAL.sum(),
        left=np.nan, right=1.,
    ))
    expected = np.asarray(expected)
    assert reference.N_Campanas.eq(3).all()
    assert reference.Campanas_Anos.eq(", ".join(map(str, (2014, *YEARS, 2026)))).all()
    for q, column in [(0.1, "Progreso_P10"), (.5, "Progreso_Mediano"), (.9, "Progreso_P90")]:
        quantile = np.nanquantile(expected, q, axis=0)
        np.testing.assert_allclose(reference[column + "_Empirico"], quantile)
        np.testing.assert_allclose(reference[column], np.maximum.accumulate(quantile))
        assert reference[column].between(0, 1 + 1e-12).all()
    assert reference.attrs["source_2026"]["window_total_plm2"] == pytest.approx(8280.0)
    np.testing.assert_allclose(
        reference.set_index("Julian_days").loc[dates.dt.dayofyear, "Progreso_2026"],
        flows.cumsum() / flows.sum(),
    )
    assert reference.loc[reference.Julian_days.lt(71), "Progreso_2026"].isna().all()
    assert reference.loc[reference.Julian_days.lt(69), "N_Campanas_Dia"].eq(1).all()
    assert reference.loc[reference.Julian_days.lt(69), "Progreso_2014"].isna().all()


def test_2026_total_is_unavailable_before_last_visit_even_if_future_counts_change(local_files):
    cutoff = "2026-08-14"
    earlier = load_local_seasonal_reference(local_files, cutoff)
    assert earlier.N_Campanas.eq(2).all()
    assert earlier.Campanas_Anos.eq("2014, 2025").all()
    assert "Progreso_2026" not in earlier
    assert not earlier.attrs["source_2026"]["used"]
    counts = pd.read_csv(local_files / COUNTS)
    counts.loc[len(counts) - 1, "PLM2"] = 999999.
    counts.to_csv(local_files / COUNTS, index=False)
    altered = load_local_seasonal_reference(local_files, cutoff)
    np.testing.assert_array_equal(earlier.Progreso_Mediano, altered.Progreso_Mediano)
    assert historical_weekly_max(earlier, cutoff) == historical_weekly_max(altered, cutoff)
    available = load_local_seasonal_reference(local_files, "2026-08-15")
    assert available.N_Campanas.eq(3).all()
    assert available.attrs["source_2026"]["used"]


def test_density_scaling_does_not_change_campaign_weight(local_files):
    original = load_local_seasonal_reference(local_files, "2027-05-05")
    counts = pd.read_csv(local_files / COUNTS)
    counts["PLM2"] *= 100
    counts.to_csv(local_files / COUNTS, index=False)
    scaled = load_local_seasonal_reference(local_files, "2027-05-05")
    np.testing.assert_allclose(original.Progreso_Mediano, scaled.Progreso_Mediano)
    assert historical_weekly_max(original, "2027-05-05") == pytest.approx(
        historical_weekly_max(scaled, "2027-05-05")
    )


def test_excluded_campaigns_cannot_change_the_local_pool_or_intensity_reference(local_files):
    original = load_local_seasonal_reference(local_files, "2027-05-05")
    with (local_files / MODEL).open("rb") as handle:
        payload = pickle.load(handle)
    selected = {"emererel2025 balcarce.xlsx"}
    for i, name in enumerate(payload["names"]):
        if name not in selected:
            payload["curves_interp"][i] = np.arange(len(payload["JD_common"])) * 999
    with (local_files / MODEL).open("wb") as handle:
        pickle.dump(payload, handle)
    altered = load_local_seasonal_reference(local_files, "2027-05-05")
    pd.testing.assert_frame_equal(original, altered)
    assert historical_weekly_max(original, "2027-05-05") == historical_weekly_max(altered, "2027-05-05")


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unnamed"])
def test_missing_duplicated_or_unidentified_local_campaign_is_rejected(local_files, fault):
    with (local_files / MODEL).open("rb") as handle:
        payload = pickle.load(handle)
    if fault == "missing":
        i = payload["names"].index("emererel2025 balcarce.xlsx")
        payload["names"][i] = "otra localidad 2025.xlsx"
    elif fault == "duplicate":
        payload["names"][0] = "emererel2025 balcarce.xlsx"
    else:
        payload["names"][0] = ""
    with (local_files / MODEL).open("wb") as handle:
        pickle.dump(payload, handle)
    with pytest.raises(ValueError):
        load_seasonal_reference(local_files / MODEL)


def test_explicit_whitelist_and_exclusions_are_auditable():
    reference = load_local_seasonal_reference(ROOT, "2027-05-05")
    assert reference.Campanas.iloc[0] == (
        "balcarce_2014_weekly.csv, emererel2025 balcarce.xlsx, balcarce_2026_counts.csv"
    )
    excluded = reference.Campanas_Excluidas.iloc[0].lower()
    for name in ("2008", "2009", "2010", "2011", "2012", "2013", "2014", "2015", "2023", "2024", "san pedro", "tresas"):
        assert name in excluded
    # Empty generic filters cannot re-enable other campaigns.
    unrestricted = load_seasonal_reference(ROOT / MODEL, excluded_years=())
    assert unrestricted.N_Campanas.eq(1).all()
    assert unrestricted.Campanas.eq("emererel2025 balcarce.xlsx").all()


@pytest.mark.parametrize("fault", ["duplicate", "negative", "nan", "no_initial_zero", "wrong_year"])
def test_invalid_counts_fail_instead_of_silently_changing_the_pool(local_files, fault):
    counts = pd.read_csv(local_files / COUNTS)
    if fault == "duplicate":
        counts.loc[2, "FECHA"] = counts.loc[1, "FECHA"]
    elif fault == "wrong_year":
        counts.loc[0, "FECHA"] = "2025-03-12"
    else:
        counts.loc[0 if fault == "no_initial_zero" else 2, "PLM2"] = {
            "negative": -1., "nan": np.nan, "no_initial_zero": 1.,
        }[fault]
    counts.to_csv(local_files / COUNTS, index=False)
    with pytest.raises(ValueError, match="Conteos 2026 inválidos"):
        load_local_seasonal_reference(local_files, "2027-05-05")


def test_2014_is_unavailable_before_publication_and_only_enters_afterwards(local_files):
    before = load_local_seasonal_reference(local_files, "2015-09-09")
    after = load_local_seasonal_reference(local_files, "2015-09-10")
    assert before.Campanas_Anos.eq("2025").all()
    assert "Progreso_2014" not in before
    assert not before.attrs["source_2014"]["used"]
    assert before.Referencia_2014_Desde.eq("2015-09-10").all()
    assert before.Campanas_Excluidas.iloc[0].count("balcarce_2014_weekly.csv") == 1
    assert after.Campanas_Anos.eq("2014, 2025").all()
    assert after.attrs["source_2014"]["used"]
    # Un corte anterior no puede depender de los valores de 2014.
    weekly = pd.read_csv(local_files / W2014)
    weekly.loc[0, "PORC_SEMANAL"] += 5.
    weekly.to_csv(local_files / W2014, index=False)
    # El archivo alterado ya no coincide con su procedencia, aun si no se usa.
    with pytest.raises(ValueError, match="no coincide con su procedencia"):
        load_local_seasonal_reference(local_files, "2015-09-09")


def test_2014_is_the_lolium_series_and_not_avena_fatua():
    source = json.loads((ROOT / S2014).read_text(encoding="utf-8"))
    assert source["species"] == "Lolium multiflorum"
    assert source["site"] == "Balcarce"
    assert "Avena" in source["species_check"]
    weekly = pd.read_csv(ROOT / W2014)
    dates = pd.to_datetime(weekly.FECHA)
    series = pd.Series(weekly.PORC_SEMANAL.to_numpy(), index=dates)
    total = series.sum()
    assert 99 <= total <= 101
    assert series[:"2014-04-30"].sum() / total > 0.80
    assert series["2014-08-01":"2014-09-30"].sum() / total < 0.03
    # No hay cero inicial: la primera semana ya concentra una parte del total.
    assert weekly.PORC_SEMANAL.iloc[0] > 10
    reference = load_local_seasonal_reference(ROOT, "2027-05-05")
    assert reference.attrs["source_2014"]["species"] == "Lolium multiflorum"
    assert "sin cero inicial" in reference.attrs["source_2014"]["scope"]


def test_2014_pdf_hash_and_species_are_validated(local_files):
    (local_files / P2014).write_bytes(b"otro documento")
    with pytest.raises(ValueError, match="PDF de procedencia"):
        load_local_seasonal_reference(local_files, "2027-05-05")


@pytest.mark.parametrize("fault", ["species", "avena_shape"])
def test_2014_series_of_another_species_is_rejected(local_files, fault):
    source = json.loads((local_files / S2014).read_text(encoding="utf-8"))
    if fault == "species":
        source["species"] = "Avena fatua"
    else:
        weekly = pd.read_csv(local_files / W2014)
        weekly.loc[weekly.FECHA >= "2014-08-01", "PORC_SEMANAL"] += 5.
        weekly.to_csv(local_files / W2014, index=False)
        from hashlib import sha256
        source["digitization"]["sha256"] = sha256((local_files / W2014).read_bytes()).hexdigest()
    (local_files / S2014).write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError):
        load_local_seasonal_reference(local_files, "2027-05-05")


def test_median_curve_with_2014_has_no_abrupt_drop():
    for cutoff in ("2015-09-10", "2026-08-15"):
        reference = load_local_seasonal_reference(ROOT, cutoff)
        for column in ("Progreso_P10", "Progreso_Mediano", "Progreso_P90"):
            assert reference[column].dropna().is_monotonic_increasing
        # Entrar una campaña a mitad de ventana no mueve el pool más de ~12 pp en un día.
        assert reference.Progreso_Mediano.diff().max() < 0.12
