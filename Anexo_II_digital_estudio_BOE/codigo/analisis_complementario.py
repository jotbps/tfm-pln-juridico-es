"""Analisis adicional de las salidas BOE, sin red ni reentrenamiento.
Uso: python analisis_complementario.py carpeta_resultados carpeta_salida
Los rangos por omision de fecha no son intervalos de confianza.
"""
from pathlib import Path
import hashlib
import json
import platform
import sys
import numpy as np
import pandas as pd

MODELS = {"BETO": 512, "RoBERTalex": 512, "MEL": 512, "MrBERT-legal": 8192}
METRICS = {"mediana": 50, "P90": 90, "P95": 95}


def main(source: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    lengths_path = source / "longitudes_por_documento.csv"
    df = pd.read_csv(lengths_path, dtype={"issue_date": str})
    required = {"identifier", "issue_date"} | {"tokens_" + m for m in MODELS}
    if not required.issubset(df.columns) or df.empty:
        raise ValueError("Columnas requeridas ausentes o muestra vacia")
    if df.identifier.duplicated().any() or df[list(required)].isna().any().any():
        raise ValueError("Identificadores duplicados o datos incompletos")
    if (df[["tokens_" + m for m in MODELS]] <= 0).any().any():
        raise ValueError("Todas las longitudes deben ser positivas")
    counts = df.groupby("issue_date").size()
    if len(counts) < 2:
        raise ValueError("Se necesitan al menos dos fechas")
    base = np.percentile(df.tokens_BETO, list(METRICS.values()), method="linear")
    comparisons, coverage, detail = [], [], []
    for model, window in MODELS.items():
        values = df["tokens_" + model].to_numpy()
        full = np.percentile(values, list(METRICS.values()), method="linear")
        item = {"tokenizer": model, "n": len(values)}
        for j, metric in enumerate(METRICS):
            item[metric] = full[j]
            item[metric + "_pct_vs_BETO"] = 100 * (full[j] / base[j] - 1)
        item["P90_over_median"] = full[1] / full[0]
        item["P95_over_median"] = full[2] / full[0]
        tail_n = max(1, int(np.ceil(len(values) * 0.05)))
        item["top_5pct_n"] = tail_n
        item["top_5pct_token_share"] = 100 * np.sort(values)[-tail_n:].sum() / values.sum()
        comparisons.append(item)
        fits = int((values <= window).sum())
        coverage.append({"model": model, "window": window, "n": len(values),
                         "n_fits": fits, "pct_fits": 100 * fits / len(values),
                         "n_exceeds": len(values) - fits,
                         "pct_exceeds": 100 * (len(values) - fits) / len(values)})
        for date in sorted(counts.index):
            subset = df.loc[df.issue_date != date, "tokens_" + model].to_numpy()
            q = np.percentile(subset, list(METRICS.values()), method="linear")
            for j, metric in enumerate(METRICS):
                detail.append({"tokenizer": model, "omitted_issue_date": date,
                               "n_omitted": int(counts[date]), "n_remaining": len(subset),
                               "metric": metric, "full_sample": full[j],
                               "omission_value": q[j],
                               "pct_change": 100 * (q[j] / full[j] - 1)})
    d = pd.DataFrame(detail)
    summary = d.groupby(["tokenizer", "metric"], sort=False).agg(
        full_sample=("full_sample", "first"), minimum=("omission_value", "min"),
        maximum=("omission_value", "max"),
        maximum_abs_pct_change=("pct_change", lambda v: v.abs().max())).reset_index()
    for name, data in [("comparativa_percentiles.csv", pd.DataFrame(comparisons)),
                       ("cobertura_ventanas.csv", pd.DataFrame(coverage)),
                       ("sensibilidad_por_fecha.csv", d),
                       ("sensibilidad_resumen.csv", summary)]:
        data.to_csv(out / name, index=False, encoding="utf-8-sig")
    counts.rename("n_documents").to_csv(out / "distribucion_por_fecha.csv")
    matrix_path = source / "svm_matriz_confusion.csv"
    cm = pd.read_csv(matrix_path, index_col=0)
    cm.index = cm.index.astype(str)
    cm.columns = cm.columns.astype(str)
    support = int(cm.loc["3"].sum())
    tp, predicted = int(cm.loc["3", "3"]), int(cm["3"].sum())
    errors = {"section": "3", "support": support, "correct": tp,
              "false_negatives": support - tp, "false_positives": predicted - tp,
              "recall": tp / support, "precision": tp / predicted,
              "recall_percentage_points_per_document": 100 / support,
              "destinations": {c: int(cm.loc["3", c]) for c in cm.columns if c != "3"}}
    (out / "errores_seccion_III.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    manifest = {"analysis_version": "1.0", "n_documents": len(df), "n_dates": len(counts),
                "percentile_method": "linear", "omission_unit": "issue_date",
                "scope": "descriptive sensitivity, not population confidence intervals",
                "windows_from": "TFM table 7.1", "windows": MODELS,
                "python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "sha256": {}}
    for p in [lengths_path, matrix_path, Path(__file__)]:
        manifest["sha256"][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out / "manifiesto_analisis_complementario.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python analisis_complementario.py resultados salida")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
