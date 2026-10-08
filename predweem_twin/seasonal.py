"""Pool histórico local de Balcarce, independiente de otras localidades."""

from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import json
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


LOCAL_2014 = {
    "counts": "data/reference/balcarce_2014_weekly.csv",
    "source": "data/reference/balcarce_2014_source.json",
    "name": "balcarce_2014_weekly.csv",
}


def _load_2014(root: Path) -> tuple[pd.Series, dict]:
    """Carga la serie semanal 2014 de *Lolium multiflorum* en EEA Balcarce.

    Es una digitalización del panel de Lolium (no de Avena fatua) de un trabajo
    publicado. Se valida la procedencia, el hash y la forma de la serie para
    que no se pueda reemplazar por la de otra especie o localidad.
    """
    source_path = root / LOCAL_2014["source"]
    counts_path = root / LOCAL_2014["counts"]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if (source.get("site") != "Balcarce" or source.get("species") != "Lolium multiflorum"
            or source.get("campaign") != 2014):
        raise ValueError("La referencia 2014 debe ser Lolium multiflorum de Balcarce.")
    if sha256(counts_path.read_bytes()).hexdigest() != source["digitization"]["sha256"]:
        raise ValueError("La serie Balcarce 2014 no coincide con su procedencia.")
    pdf_path = source_path.parent / source["reference"]["pdf"]
    if sha256(pdf_path.read_bytes()).hexdigest() != source["reference"]["pdf_sha256"]:
        raise ValueError("El PDF de procedencia de Balcarce 2014 no coincide con su hash.")
    frame = pd.read_csv(counts_path)
    if list(frame.columns) != ["FECHA", "PORC_SEMANAL"]:
        raise ValueError("La serie Balcarce 2014 requiere FECHA y PORC_SEMANAL.")
    dates = pd.to_datetime(frame["FECHA"], errors="raise").dt.normalize()
    values = pd.to_numeric(frame["PORC_SEMANAL"], errors="raise").to_numpy(float)
    if (dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing
            or not dates.dt.year.eq(2014).all() or len(frame) < 10
            or not np.isfinite(values).all() or (values < 0).any()
            or not 99.0 <= values.sum() <= 101.0):
        raise ValueError("Serie Balcarce 2014 inválida: debe sumar ~100 % semanal.")
    # Verificación de especie con las cifras del propio trabajo: Lolium concentró
    # más del 80 % en marzo–abril y casi nada en agosto–septiembre; Avena fatua
    # tuvo ~70 % y un flujo secundario agosto–septiembre.
    series = pd.Series(values, index=dates)
    share_spring = series[:"2014-04-30"].sum() / values.sum()
    share_late = series["2014-08-01":"2014-09-30"].sum() / values.sum()
    if share_spring <= 0.80 or share_late >= 0.03:
        raise ValueError("La serie Balcarce 2014 no corresponde a Lolium multiflorum.")
    return series, source


def load_local_seasonal_reference(root: str | Path, as_of=None) -> pd.DataFrame:
    """Combina Balcarce 2014, 2025 y 2026 en el pool local.

    El total 2026 sólo está disponible desde el último conteo. 2014 desde la
    publicación del trabajo (10/09/2015). Antes de esas fechas se excluyen las
    campañas aún no disponibles, también en evaluaciones temporales. Se
    interpola el acumulado entre visitas, conservando la masa de cada
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

    series_2014, source_2014 = _load_2014(root)
    available_2014 = pd.Timestamp(source_2014["reference"]["available_from"])
    use_2014 = cutoff is None or cutoff >= available_2014

    reference["Progreso_2025"] = reference["Progreso_Mediano"]
    reference["Referencia_2026_Desde"] = available_from.date().isoformat()
    reference["Referencia_2014_Desde"] = available_2014.date().isoformat()
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
    reference.attrs["source_2014"] = {
        "path": LOCAL_2014["counts"],
        "sha256": sha256((root / LOCAL_2014["counts"]).read_bytes()).hexdigest(),
        "provenance": LOCAL_2014["source"],
        "species": source_2014["species"],
        "start": series_2014.index[0].date().isoformat(),
        "end": series_2014.index[-1].date().isoformat(),
        "sample_count": len(series_2014),
        "window_total_percent": float(series_2014.sum()),
        "used": use_2014,
        "kind": "digitalizado de la Figura 2 (panel Lolium multiflorum); % semanal del total anual",
        "processing": "acumulado / total de la serie; interpolación lineal entre muestreos",
        "scope": "sin cero inicial: empieza en el primer muestreo (10/03) y no certifica ausencia previa",
    }
    names = {2014: LOCAL_2014["name"], 2025: "emererel2025 balcarce.xlsx", 2026: counts_path.name}
    used_years = [2025]
    if use_2014:
        progress_2014 = np.cumsum(series_2014.to_numpy()) / series_2014.sum()
        reference["Progreso_2014"] = np.interp(
            reference["Julian_days"], series_2014.index.dayofyear, progress_2014,
            left=np.nan, right=1.0,
        )
        used_years.insert(0, 2014)
    if use_2026:
        progress_2026 = np.cumsum(flows) / flows.sum()
        reference["Progreso_2026"] = np.interp(
            reference["Julian_days"], dates.dt.dayofyear, progress_2026,
            left=np.nan, right=1.0,
        )
        used_years.append(2026)
    pending = [
        f"{names[y]} (disponible desde {d:%d/%m/%Y})"
        for y, d, flag in ((2014, available_2014, use_2014), (2026, available_from, use_2026))
        if not flag
    ]
    reference["Campanas_Excluidas"] += "".join(f", {item}" for item in pending)
    reference["Campanas_Anos"] = ", ".join(str(y) for y in used_years)
    reference["N_Campanas_Dia"] = 1
    if len(used_years) == 1:
        return reference

    campaigns = reference[[f"Progreso_{y}" for y in used_years]]
    reference["N_Campanas_Dia"] = campaigns.notna().sum(axis=1)
    for q, column in [(0.10, "Progreso_P10"), (0.50, "Progreso_Mediano"), (0.90, "Progreso_P90")]:
        empirical = campaigns.quantile(q, axis=1)
        reference[column + "_Empirico"] = empirical
        # Al comenzar la ventana de una campaña cambia el número de curvas
        # disponibles. Ese cambio puede bajar el resumen aunque cada campaña sea
        # creciente. La envolvente acumulativa conserva el avance previo del
        # ancla. Los cuantiles originales y las curvas quedan visibles para auditoría.
        reference[column] = empirical.cummax()
    reference["N_Campanas"] = len(used_years)
    reference["Campanas"] = ", ".join(names[y] for y in used_years)
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
    mediano de campañas históricas, utilizando sólo fechas hasta el corte.
    Sin señal o progreso histórico suficiente, el porcentaje no es estimable.
    """
    cutoff = pd.Timestamp(as_of).tz_localize(None).normalize()
    if pd.isna(cutoff):
        raise ValueError("Fecha de corte de normalización inválida.")
    dates = pd.to_datetime(trajectory["Fecha"]).dt.tz_localize(None).dt.normalize()
    past = trajectory.loc[dates <= cutoff].sort_values("Fecha")
    if past.empty:
        return None, {"mode": "porcentaje aún no estimable", "reason": "Sin historia hasta el corte."}
    anchor = past.iloc[-1]
    p10, median, p90 = reference_progress(
        reference, [float(anchor["Julian_days"])]
    )
    raw_cumulative = float(anchor["EMERAC"])
    metadata = {
        "mode": "porcentaje aún no estimable",
        "anchor_date": anchor["Fecha"],
        "reference_progress": float(median[0]),
    }
    if (not np.isfinite([raw_cumulative, median[0]]).all()
            or raw_cumulative <= 1e-12 or median[0] <= 0.01):
        return None, {**metadata, "reason": "Sin señal acumulada o progreso histórico mayor al 1% hasta el corte."}

    seasonal_total = float(raw_cumulative / median[0])
    if not np.isfinite(seasonal_total) or seasonal_total <= 1e-12:
        return None, {**metadata, "reason": "Denominador estacional no válido."}
    return seasonal_total, {
        **metadata,
        "mode": "referencia estacional histórica",
        "reference_p10": float(p10[0]),
        "reference_p90": float(p90[0]),
        "seasonal_signal_total": seasonal_total,
    }
