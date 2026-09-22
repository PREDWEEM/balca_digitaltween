"""Pool histórico local de Balcarce, independiente de otras localidades."""

from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import pickle

import numpy as np
import pandas as pd


LOCAL_2025_NAME = "emererel2025 balcarce.xlsx"
EXCLUDED_YEARS = ("2008", "2009", "2010", "2011", "2012", "2013", "2014", "2015", "2023", "2024")


def load_seasonal_reference(
    source: str | Path,
    excluded_years: tuple[str, ...] = EXCLUDED_YEARS,
    include_patterns: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Carga exclusivamente la campaña identificada como Balcarce 2025.

    La lista positiva impide que nuevas campañas, nombres ambiguos o la
    desactivación del filtro de años incorporen curvas ajenas al sitio.
    Los filtros opcionales sólo pueden restringir esta selección.
    """
    with Path(source).open("rb") as handle:
        payload = pickle.load(handle)
    days = np.asarray(payload.get("JD_common", payload.get("JD_COMMON")), dtype=float)
    curves = np.asarray(payload.get("curves_interp", payload.get("curves")), dtype=float)
    names = [str(value) for value in payload.get("names", payload.get("files", []))]
    if (days.ndim != 1 or len(days) < 2 or not np.isfinite(days).all()
            or (np.diff(days) <= 0).any() or curves.ndim != 2
            or curves.shape[1] != len(days)):
        raise ValueError("La referencia histórica no contiene curvas y días compatibles.")
    if len(names) != len(curves) or any(not name.strip() for name in names):
        raise ValueError("La referencia requiere un nombre por curva para filtrar campañas.")
    normalized = [" ".join(name.casefold().split()) for name in names]
    patterns = tuple(" ".join(str(value).casefold().split()) for value in (include_patterns or ()))
    selected = [i for i, name in enumerate(normalized)
                if name == LOCAL_2025_NAME
                and not any(year in name for year in excluded_years)
                and (not patterns or any(pattern in name for pattern in patterns))]
    if len(selected) != 1:
        raise ValueError("Se requiere una única referencia local de Balcarce 2025.")
    index = selected[0]
    flow = curves[index]
    if not np.isfinite(flow).all() or (flow < 0).any() or flow.sum() <= 1e-12:
        raise ValueError("La referencia Balcarce 2025 no contiene flujos válidos positivos.")
    progress = np.cumsum(flow) / flow.sum()
    return pd.DataFrame({
        "Julian_days": days,
        "Progreso_P10": progress, "Progreso_Mediano": progress, "Progreso_P90": progress,
        "N_Campanas": 1, "N_Campanas_Dia": 1,
        "Campanas": names[index],
        "Campanas_Excluidas": ", ".join(name for i, name in enumerate(names) if i != index),
        "Campanas_Anos": "2025", "Progreso_2025": progress,
    })


def load_local_seasonal_reference(root: str | Path, as_of=None) -> pd.DataFrame:
    """Combina Balcarce 2025 con el período registrado de 2026.

    El total 2026 sólo está disponible desde el último conteo. Antes de esa
    fecha se utiliza exclusivamente 2025, también en evaluaciones temporales.
    Se interpola el acumulado entre visitas, conservando la masa de cada
    intervalo. No se atribuyen conteos diarios ni ceros anteriores al inicio.
    Cada campaña disponible tiene igual peso, independientemente de su densidad.
    """
    root = Path(root)
    reference = load_seasonal_reference(
        root / "models/modelo_clusters_k3.pkl",
        include_patterns=("balcarce",),
    )
    if (not reference["N_Campanas"].eq(1).all()
            or not reference["Campanas"].eq("emererel2025 balcarce.xlsx").all()):
        raise ValueError("Se requiere una única referencia local de Balcarce 2025.")

    counts_path = root / "data/calibration/balcarce_2026_counts.csv"
    counts = pd.read_csv(counts_path)
    if not {"FECHA", "PLM2"}.issubset(counts.columns) or len(counts) < 2:
        raise ValueError("La referencia 2026 requiere FECHA y PLM2 y al menos dos visitas.")
    dates = pd.to_datetime(counts["FECHA"], errors="raise").dt.normalize()
    flows = pd.to_numeric(counts["PLM2"], errors="raise").to_numpy(float)
    if (dates.isna().any() or dates.duplicated().any()
            or not dates.is_monotonic_increasing or not dates.dt.year.eq(2026).all()
            or not np.isfinite(flows).all() or (flows < 0).any()
            or flows.sum() <= 0 or flows[0] != 0):
        raise ValueError("Conteos 2026 inválidos o sin cero inicial delimitador.")
    available_from = dates.iloc[-1]
    cutoff = pd.Timestamp(as_of).tz_localize(None).normalize() if as_of is not None else None
    if cutoff is not None and pd.isna(cutoff):
        raise ValueError("Fecha de corte de la referencia inválida.")
    use_2026 = cutoff is None or cutoff >= available_from
    reference["Progreso_2025"] = reference["Progreso_Mediano"]
    reference["Campanas_Anos"] = "2025"
    reference["N_Campanas_Dia"] = 1
    reference["Referencia_2026_Desde"] = available_from.date().isoformat()
    reference.attrs["source_2026"] = {
        "path": "data/calibration/balcarce_2026_counts.csv",
        "sha256": sha256(counts_path.read_bytes()).hexdigest(),
        "start": dates.iloc[0].date().isoformat(),
        "end": available_from.date().isoformat(),
        "sample_count": len(counts),
        "window_total_plm2": float(flows.sum()),
        "used": use_2026,
        "processing": "acumulado / total registrado; interpolación lineal entre visitas",
        "scope": "ventana registrada; no certifica el cierre biológico de la campaña",
    }
    if not use_2026:
        reference["Campanas_Excluidas"] += (
            f", {counts_path.name} (disponible desde {available_from:%d/%m/%Y})"
        )
        return reference

    progress_2026 = np.cumsum(flows) / flows.sum()
    reference["Progreso_2026"] = np.interp(
        reference["Julian_days"], dates.dt.dayofyear, progress_2026,
        left=np.nan, right=1.0,
    )
    campaigns = reference[["Progreso_2025", "Progreso_2026"]]
    reference["N_Campanas_Dia"] = campaigns.notna().sum(axis=1)
    for q, column in [(0.10, "Progreso_P10"), (0.50, "Progreso_Mediano"), (0.90, "Progreso_P90")]:
        empirical = campaigns.quantile(q, axis=1)
        reference[column + "_Empirico"] = empirical
        # Al comenzar la ventana 2026 cambia el número de curvas disponibles.
        # Ese cambio puede bajar el resumen aunque cada campaña sea creciente.
        # La envolvente acumulativa conserva el avance previo del ancla. Los
        # cuantiles originales y ambas curvas quedan visibles para auditoría.
        reference[column] = empirical.cummax()
    reference["N_Campanas"] = 2
    reference["Campanas_Anos"] = "2025, 2026"
    reference["Campanas"] += f", {counts_path.name}"
    return reference


def reference_progress(
    reference: pd.DataFrame, julian_days
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpola P10, mediana y P90 para uno o varios días julianos."""
    days = np.asarray(julian_days, dtype=float)
    axis = reference["Julian_days"].to_numpy(float)
    values = []
    for column in ("Progreso_P10", "Progreso_Mediano", "Progreso_P90"):
        values.append(
            np.interp(
                days,
                axis,
                reference[column].to_numpy(float),
                left=0.0,
                right=1.0,
            )
        )
    return tuple(values)


def partial_season_normalization(
    trajectory: pd.DataFrame,
    as_of,
    reference: pd.DataFrame,
) -> tuple[float | None, dict]:
    """Estima el total de señal estacional sin usar el fin del pronóstico.

    La señal acumulada de PREDWEEM se ancla, en la fecha del estado, al progreso
    mediano de campañas históricas. Si aún no existe señal positiva, utiliza el
    último día disponible como ancla provisional.
    """
    cutoff = pd.Timestamp(as_of).tz_localize(None).normalize()
    candidates = trajectory.index[trajectory["Fecha"] <= cutoff].tolist()
    anchor_idx = candidates[-1] if candidates else 0
    p10, median, p90 = reference_progress(
        reference, trajectory["Julian_days"].to_numpy(float)
    )
    raw_cumulative = trajectory["EMERAC"].to_numpy(float)

    if raw_cumulative[anchor_idx] <= 1e-12 or median[anchor_idx] <= 0.01:
        valid = np.flatnonzero((raw_cumulative > 1e-12) & (median > 0.01))
        if not len(valid):
            return None, {
                "mode": "sin señal suficiente",
                "anchor_date": trajectory.at[anchor_idx, "Fecha"],
                "reference_progress": float(median[anchor_idx]),
            }
        anchor_idx = int(valid[0])

    seasonal_total = float(raw_cumulative[anchor_idx] / median[anchor_idx])
    if not np.isfinite(seasonal_total) or seasonal_total <= 1e-12:
        return None, {"mode": "sin señal suficiente"}
    return seasonal_total, {
        "mode": "referencia estacional histórica",
        "anchor_date": trajectory.at[anchor_idx, "Fecha"],
        "reference_progress": float(median[anchor_idx]),
        "reference_p10": float(p10[anchor_idx]),
        "reference_p90": float(p90[anchor_idx]),
        "seasonal_signal_total": seasonal_total,
    }
