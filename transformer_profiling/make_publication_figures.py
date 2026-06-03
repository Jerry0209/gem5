#!/usr/bin/env python3
"""Generate IEEE-style figures for the Transformer SVE profiling study.

The script uses the consolidated `final_all_experiments.tsv` as the measured
data source and optionally enriches it with the experiment-settings workbook.
It saves each requested figure as PDF, SVG, and high-DPI PNG.

If your Excel workbook uses different column names, adapt CANONICAL_ALIASES
below. The aliases are normalized first, so names such as "N LEARNERS",
"N_LEARNERS", and "n-learners" all become "n_learners".
"""

from __future__ import annotations

import argparse
import re
import sys
import warnings
from pathlib import Path


DEFAULT_RESULTS = Path(
    "/home/thu/TiC-SAT/transformer_profiling/final/final_all_experiments.tsv"
)
DEFAULT_EXCEL_NAME = "Transformer Experiment Settings.xlsx"

LEARNERS = [1, 2, 4]
SVE_BITS = [128, 256, 512]
CODEBOOK_SIZES = [4, 8, 16]
FIG_EXTENSIONS = ("pdf", "svg", "png")

BASELINE_COLOR = "#cf6f5b"
SVE128_COLOR = "#8c3f16"
SVE256_COLOR = "#c86f28"
SVE512_COLOR = "#e6b36a"
CACHE_LINE_COLOR = "#4f3b78"

CONFIG_COLORS = {
    "Dense baseline": BASELINE_COLOR,
    "SVE-128": SVE128_COLOR,
    "SVE-256": SVE256_COLOR,
    "SVE-512": SVE512_COLOR,
}
SVE_COLORS = {128: SVE128_COLOR, 256: SVE256_COLOR, 512: SVE512_COLOR}
CB_COLORS = {4: SVE128_COLOR, 8: SVE256_COLOR, 16: SVE512_COLOR}
MARKERS = {128: "o", 256: "^", 512: "s", 4: "o", 8: "^", 16: "s"}
HATCHES = {
    "Dense baseline": "",
    "SVE-128": "///",
    "SVE-256": "\\\\\\",
    "SVE-512": "...",
    128: "///",
    256: "xxx",
    512: "...",
    4: "///",
    8: "\\\\\\",
    16: "...",
}

STAGE_ORDER = [
    "MHA",
    "Projection",
    "non_GEMM_after_projection",
    "FF1",
    "FF2",
    "non_GEMM_after_ff2",
]
STAGE_LABELS = {
    "MHA": "MHA",
    "Projection": "Projection",
    "non_GEMM_after_projection": "Post projection",
    "FF1": "FF1",
    "FF2": "FF2",
    "non_GEMM_after_ff2": "Post FF2",
}
STAGE_COLORS = {
    "MHA": "#4e79a7",
    "Projection": "#f28e2b",
    "non_GEMM_after_projection": "#e15759",
    "FF1": "#f1ce63",
    "FF2": "#76b7b2",
    "non_GEMM_after_ff2": "#59a14f",
}
STAGE_HATCHES = {
    "MHA": "",
    "Projection": "///",
    "non_GEMM_after_projection": "\\\\\\",
    "FF1": "...",
    "FF2": "xxx",
    "non_GEMM_after_ff2": "++",
}

# Add or adjust entries here if the workbook uses another spelling.
CANONICAL_ALIASES = {
    "exp_id": (
        "exp_id",
        "experiment",
        "experiment_id",
        "experiment_no",
        "experiment_number",
        "exp",
        "id",
    ),
    "study": ("study", "sweep", "experiment_type", "experiment_group"),
    "model": ("model", "benchmark", "network", "transformer_model", "bert_model"),
    "implementation": ("implementation", "impl", "kernel", "variant", "config"),
    "n_learners": (
        "n_learners",
        "nlearners",
        "num_learners",
        "number_of_learners",
        "learners",
        "n_learner",
        "ensemble_size",
    ),
    "codebook_size": (
        "codebook_size",
        "codebook",
        "cb",
        "cb_size",
        "codebook_entries",
    ),
    "sve_bits": (
        "sve_bits",
        "sve",
        "sve_width",
        "sve_vector_bits",
        "vector_bits",
        "vr_bits",
        "vr",
        "vector_register_bits",
    ),
    "row_kind": ("row_kind", "row_type", "kind"),
    "execution_time": (
        "execution_time",
        "sim_seconds",
        "simseconds",
        "runtime",
        "runtime_s",
        "time_s",
        "seconds",
    ),
    "instructions": (
        "instructions",
        "sim_insts",
        "siminsts",
        "sim_instructions",
        "instruction_count",
    ),
    "ops": ("ops", "sim_ops", "simops"),
    "cpu_cycles": ("cpu_cycles", "cycles", "num_cycles"),
    "l1d_cache_misses": (
        "l1d_cache_misses",
        "l1d_misses",
        "l1_data_misses",
        "dcache_demand_misses",
        "dcache_misses",
        "d_cache_misses",
    ),
    "l1d_cache_accesses": (
        "l1d_cache_accesses",
        "l1d_accesses",
        "dcache_demand_accesses",
        "dcache_accesses",
    ),
    "l1i_cache_misses": (
        "l1i_cache_misses",
        "l1i_misses",
        "l1_instruction_misses",
        "icache_demand_misses",
        "icache_misses",
        "i_cache_misses",
    ),
    "l1i_cache_accesses": (
        "l1i_cache_accesses",
        "l1i_accesses",
        "icache_demand_accesses",
        "icache_accesses",
    ),
    "l2_cache_misses": (
        "l2_cache_misses",
        "l2_misses",
        "l2_demand_misses",
        "l2cache_misses",
    ),
    "l2_cache_accesses": (
        "l2_cache_accesses",
        "l2_accesses",
        "l2_demand_accesses",
        "l2cache_accesses",
    ),
}

pd = None
np = None
mpl = None
plt = None


def import_plot_stack():
    """Import plotting dependencies lazily to provide a clear error message."""

    try:
        import numpy as numpy_module
        import pandas as pandas_module
        import matplotlib as matplotlib_module

        matplotlib_module.use("Agg")
        import matplotlib.pyplot as pyplot_module
    except ImportError as exc:
        raise SystemExit(
            "Missing plotting dependency. Install pandas, matplotlib, numpy, "
            "and openpyxl, for example:\n"
            "  conda install pandas matplotlib numpy openpyxl\n"
            "or\n"
            "  pip install pandas matplotlib numpy openpyxl"
        ) from exc

    return pandas_module, numpy_module, matplotlib_module, pyplot_module


def warn(message: str) -> None:
    warnings.warn(message, stacklevel=2)


def normalize_column_name(name: object) -> str:
    text = str(name).strip()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = text.lower().replace("%", "pct")
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def normalize_columns(frame):
    frame = frame.copy()
    seen = {}
    columns = []
    for column in frame.columns:
        base = normalize_column_name(column)
        if base in seen:
            seen[base] += 1
            base = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        columns.append(base)
    frame.columns = columns
    return frame


def canonicalize_columns(frame):
    """Normalize names and add canonical aliases without dropping originals."""

    frame = normalize_columns(frame)
    for canonical, aliases in CANONICAL_ALIASES.items():
        if canonical in frame.columns:
            continue
        for alias in aliases:
            if alias in frame.columns:
                frame[canonical] = frame[alias]
                break
    return frame


def extract_exp_id(values):
    text = values.astype(str)
    extracted = text.str.extract(r"\b[Ee]\s*0?([1-9]|[1-3][0-9])\b", expand=False)
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric.where(numeric.between(1, 36))
    extracted = extracted.fillna(numeric)
    return extracted.dropna().astype(int).map(lambda value: f"E{value:02d}").reindex(values.index)


def ensure_exp_id(frame, source_name: str):
    if "exp_id" in frame.columns:
        frame = frame.copy()
        frame["exp_id"] = extract_exp_id(frame["exp_id"])
        return frame

    best_column = None
    best_count = 0
    for column in frame.columns:
        if frame[column].dtype.kind not in {"O", "U", "S"}:
            continue
        extracted = extract_exp_id(frame[column])
        count = int(extracted.notna().sum())
        if count > best_count:
            best_column = column
            best_count = count

    if best_column is None or best_count == 0:
        warn(f"{source_name}: could not identify an experiment-id column.")
        return frame

    frame = frame.copy()
    frame["exp_id"] = extract_exp_id(frame[best_column])
    print(f"[info] {source_name}: inferred exp_id from column '{best_column}'.")
    return frame


def resolve_results_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_dir():
        path = path / "final_all_experiments.tsv"
    if not path.exists():
        raise FileNotFoundError(f"Results table not found: {path}")
    return path


def resolve_excel_path(raw_path: str | None, results_path: Path) -> Path | None:
    if raw_path:
        path = Path(raw_path).expanduser()
        if path.exists():
            return path
        warn(f"Excel settings workbook not found at {path}; continuing with TSV metadata.")
        return None

    script_dir = Path(__file__).resolve().parent
    candidates = [
        Path.cwd() / DEFAULT_EXCEL_NAME,
        script_dir / DEFAULT_EXCEL_NAME,
        results_path.parent / DEFAULT_EXCEL_NAME,
        results_path.parent.parent / DEFAULT_EXCEL_NAME,
        Path("/home/thu/gem5/transformer_profiling") / DEFAULT_EXCEL_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    warn(
        f"Could not find '{DEFAULT_EXCEL_NAME}' in the usual locations; "
        "continuing with TSV metadata. Pass --excel /path/to/workbook.xlsx if needed."
    )
    return None


def load_results(results_path: Path):
    frame = pd.read_csv(results_path, sep="\t")
    frame = canonicalize_columns(frame)
    frame = ensure_exp_id(frame, str(results_path))
    print(f"[info] Loaded results: {results_path}")
    print(f"[info] Normalized result columns: {', '.join(frame.columns)}")
    return frame


def load_excel_settings(excel_path: Path | None):
    if excel_path is None:
        return pd.DataFrame()

    try:
        sheets = pd.read_excel(excel_path, sheet_name=None)
    except Exception as exc:
        warn(f"Could not read Excel workbook {excel_path}: {exc}; continuing with TSV metadata.")
        return pd.DataFrame()

    frames = []
    for sheet_name, sheet in sheets.items():
        if sheet is None or sheet.empty:
            continue
        sheet = canonicalize_columns(sheet)
        sheet = ensure_exp_id(sheet, f"{excel_path.name}:{sheet_name}")
        if "exp_id" not in sheet.columns:
            continue
        sheet = sheet[sheet["exp_id"].notna()].copy()
        if sheet.empty:
            continue
        sheet["settings_sheet"] = sheet_name
        frames.append(sheet)

    if not frames:
        warn(f"Excel workbook {excel_path} did not contain identifiable E01-E36 rows.")
        return pd.DataFrame()

    settings = pd.concat(frames, ignore_index=True, sort=False)
    settings = settings.sort_values("exp_id").groupby("exp_id", as_index=False).first()
    print(f"[info] Read Excel settings: {excel_path} ({len(settings)} experiment rows)")
    print(f"[info] Normalized Excel columns: {', '.join(settings.columns)}")
    return settings


def merge_settings(results, settings):
    if settings.empty:
        return results

    merged = results.merge(settings, on="exp_id", how="left", suffixes=("", "_settings"))
    for column in ("study", "model", "implementation", "n_learners", "codebook_size", "sve_bits"):
        settings_column = f"{column}_settings"
        if settings_column not in merged.columns:
            continue
        if column not in merged.columns:
            merged[column] = merged[settings_column]
            continue
        missing = merged[column].isna() | merged[column].astype(str).str.strip().eq("")
        merged.loc[missing, column] = merged.loc[missing, settings_column]
    return merged


def coerce_numeric_columns(frame, columns):
    frame = frame.copy()
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(
                frame[column].replace({"NA": pd.NA, "na": pd.NA, "": pd.NA}),
                errors="coerce",
            )
    return frame


def select_topline_rows(frame):
    frame = frame.copy()
    if "row_kind" in frame.columns:
        row_kind = frame["row_kind"].astype(str).str.lower()
        final_rows = frame[row_kind.eq("final_total")].copy()
        if not final_rows.empty:
            return final_rows
        warn("No row_kind == 'final_total' rows found; using the last row per experiment.")
    else:
        warn("No row_kind column found; using the last row per experiment.")

    if "row_index" in frame.columns:
        frame = coerce_numeric_columns(frame, ["row_index"])
        frame = frame.sort_values(["exp_id", "row_index"])
    return frame.groupby("exp_id", as_index=False).tail(1).copy()


def prepare_topline(frame):
    top = select_topline_rows(frame)
    top = coerce_numeric_columns(
        top,
        [
            "n_learners",
            "codebook_size",
            "sve_bits",
            "execution_time",
            "instructions",
            "ops",
            "cpu_cycles",
            "l1d_cache_misses",
            "l1d_cache_accesses",
            "l1i_cache_misses",
            "l1i_cache_accesses",
            "l2_cache_misses",
            "l2_cache_accesses",
        ],
    )

    if "model" not in top.columns:
        warn("No model/benchmark column found; using a single generic model label.")
        top["model"] = "model"
    top["model"] = top["model"].astype(str)

    if "exp_id" not in top.columns:
        raise ValueError("Could not identify E01-E36 experiment IDs.")

    top["exp_num"] = top["exp_id"].str.extract(r"E(\d{2})", expand=False).astype(float)
    top = top[top["exp_num"].between(1, 36)].copy()
    present = {int(value) for value in top["exp_num"].dropna().tolist()}
    missing = sorted(set(range(1, 37)) - present)
    if missing:
        warn("Missing final-total rows for experiments: " + ", ".join(f"E{x:02d}" for x in missing))
    print(f"[info] Identified {len(present)} experiments in E01-E36.")

    study = top["study"].astype(str) if "study" in top.columns else ""
    impl = top["implementation"].astype(str) if "implementation" in top.columns else ""
    codebook_missing = top["codebook_size"].isna() if "codebook_size" in top.columns else False
    top["is_dense_baseline"] = (
        pd.Series(study, index=top.index).str.contains("dense", case=False, na=False)
        | pd.Series(impl, index=top.index).str.contains("dense", case=False, na=False)
        | codebook_missing
    )
    top["config_label"] = top.apply(config_label, axis=1)
    return top


def prepare_stage_rows(frame):
    stages = frame.copy()
    if "row_kind" not in stages.columns:
        warn("Figure 2c skipped: no row_kind column found for stage breakdown.")
        return pd.DataFrame()
    if "interval" not in stages.columns:
        warn("Figure 2c skipped: no interval/stage column found.")
        return pd.DataFrame()

    stages = stages[stages["row_kind"].astype(str).str.lower().eq("interval_delta")].copy()
    if stages.empty:
        warn("Figure 2c skipped: no interval_delta rows found.")
        return pd.DataFrame()

    stages = coerce_numeric_columns(
        stages,
        [
            "n_learners",
            "codebook_size",
            "sve_bits",
            "execution_time",
        ],
    )
    if "model" not in stages.columns:
        stages["model"] = "model"
    stages["model"] = stages["model"].astype(str)

    study = stages["study"].astype(str) if "study" in stages.columns else ""
    impl = stages["implementation"].astype(str) if "implementation" in stages.columns else ""
    codebook_missing = stages["codebook_size"].isna() if "codebook_size" in stages.columns else False
    stages["is_dense_baseline"] = (
        pd.Series(study, index=stages.index).str.contains("dense", case=False, na=False)
        | pd.Series(impl, index=stages.index).str.contains("dense", case=False, na=False)
        | codebook_missing
    )
    stages["interval"] = stages["interval"].astype(str)

    if "exp_id" in stages.columns:
        final_rows = select_topline_rows(frame)
        final_rows = coerce_numeric_columns(final_rows, ["execution_time"])
        if "execution_time" in final_rows.columns:
            final_times = final_rows[["exp_id", "execution_time"]].rename(
                columns={"execution_time": "final_execution_time"}
            )
            stages = stages.merge(final_times, on="exp_id", how="left")
    return stages


def config_label(row) -> str:
    if bool(row.get("is_dense_baseline", False)):
        return "Dense baseline"
    sve = row.get("sve_bits")
    if pd.notna(sve):
        return f"SVE-{int(sve)}"
    return "SVE"


def compute_derived_metrics(top):
    required = ["model", "n_learners", "execution_time"]
    missing = [column for column in required if column not in top.columns]
    if missing:
        raise ValueError("Cannot compute speedups; missing columns: " + ", ".join(missing))

    top = top.copy()
    baseline_rows = top[top["is_dense_baseline"] & top["execution_time"].notna()].copy()
    if baseline_rows.empty:
        raise ValueError("No dense baseline rows found.")

    duplicated = baseline_rows.duplicated(["model", "n_learners"], keep=False)
    if duplicated.any():
        warn("Multiple dense baselines found for the same model/N_LEARNERS; averaging metrics.")

    metric_columns = [
        column
        for column in (
            "execution_time",
            "instructions",
            "l1d_cache_misses",
            "l1i_cache_misses",
            "l2_cache_misses",
            "l1d_cache_accesses",
            "l1i_cache_accesses",
            "l2_cache_accesses",
        )
        if column in top.columns
    ]
    baseline = (
        baseline_rows.groupby(["model", "n_learners"], as_index=False)[metric_columns]
        .mean(numeric_only=True)
        .rename(columns={column: f"baseline_{column}" for column in metric_columns})
    )
    data = top.merge(baseline, on=["model", "n_learners"], how="left")
    data["speedup"] = data["baseline_execution_time"] / data["execution_time"]

    for cache_column, output_column in (
        ("l1d_cache_misses", "normalized_l1d_cache_misses"),
        ("l1i_cache_misses", "normalized_l1i_cache_misses"),
        ("l2_cache_misses", "normalized_l2_cache_misses"),
    ):
        baseline_column = f"baseline_{cache_column}"
        if cache_column in data.columns and baseline_column in data.columns:
            denom = data[baseline_column].replace(0, np.nan)
            data[output_column] = data[cache_column] / denom
        else:
            warn(f"Skipping normalized cache metric; missing {cache_column}.")

    if "instructions" in data.columns:
        denom = (data["instructions"] / 1000.0).replace(0, np.nan)
        if "l1d_cache_misses" in data.columns:
            data["l1d_mpki"] = data["l1d_cache_misses"] / denom
        else:
            warn("Skipping L1D MPKI; missing L1D cache miss column.")
        if "l1i_cache_misses" in data.columns:
            data["l1i_mpki"] = data["l1i_cache_misses"] / denom
        else:
            warn("Skipping L1I MPKI; missing L1I cache miss column.")
        if "l2_cache_misses" in data.columns:
            data["l2_mpki"] = data["l2_cache_misses"] / denom
        else:
            warn("Skipping L2 MPKI; missing L2 cache miss column.")
    else:
        warn("Skipping MPKI metrics; missing instruction count column.")

    return data


def set_ieee_style():
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "axes.linewidth": 0.6,
            "axes.edgecolor": "black",
            "axes.labelsize": 7,
            "axes.titlesize": 7,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.5,
            "figure.titlesize": 8,
            "figure.dpi": 150,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": "#d9d9d9",
            "grid.linewidth": 0.45,
            "grid.linestyle": "-",
        }
    )


def model_order(models) -> list[str]:
    def key(model: str):
        lower = str(model).lower()
        if "mini" in lower:
            size = 0
        elif "base" in lower:
            size = 1
        else:
            size = 2
        return size, str(model)

    return sorted([str(model) for model in models if str(model) != "nan"], key=key)


def compact_tick(value, _position=None) -> str:
    if not np.isfinite(value):
        return ""
    abs_value = abs(value)
    if abs_value >= 1e9:
        return f"{value / 1e9:.1f}G"
    if abs_value >= 1e6:
        return f"{value / 1e6:.1f}M"
    if abs_value >= 1e3:
        return f"{value / 1e3:.1f}k"
    if abs_value >= 10:
        return f"{value:.0f}"
    if abs_value >= 1:
        return f"{value:.1f}"
    if abs_value == 0:
        return "0"
    return f"{value:.2g}"


def format_bar_label(value: float, unit: str = "") -> str:
    if not np.isfinite(value):
        return ""
    if abs(value) >= 100:
        text = f"{value:.0f}"
    elif abs(value) >= 10:
        text = f"{value:.1f}"
    else:
        text = f"{value:.2f}"
    return f"{text}{unit}"


def set_axes_common(ax, horizontal_grid: bool = True):
    ax.tick_params(axis="both", width=0.55, length=2.5, pad=1.5)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    if horizontal_grid:
        ax.grid(True, axis="y")
        ax.grid(False, axis="x")
    else:
        ax.grid(False)


def first_metric(data, mask, column: str) -> float:
    if column not in data.columns:
        return np.nan
    values = pd.to_numeric(data.loc[mask, column], errors="coerce").dropna()
    if values.empty:
        return np.nan
    return float(values.iloc[0])


def finite_bar(ax, x_values, heights, **kwargs):
    x_values = np.asarray(x_values, dtype=float)
    heights = np.asarray(heights, dtype=float)
    mask = np.isfinite(heights)
    if not mask.any():
        return None
    return ax.bar(x_values[mask], heights[mask], **kwargs)


def finite_line(ax, x_values, y_values, **kwargs):
    x_values = np.asarray(x_values, dtype=float)
    y_values = np.asarray(y_values, dtype=float)
    mask = np.isfinite(y_values)
    if not mask.any():
        return None
    return ax.plot(x_values[mask], y_values[mask], **kwargs)


def add_line_halo(lines, linewidth: float = 2.2, color: str = "white"):
    if lines is None:
        return
    from matplotlib import patheffects as pe

    for line in lines:
        line.set_path_effects([pe.Stroke(linewidth=linewidth, foreground=color), pe.Normal()])


def choose_cache_metric(data, level: str, prefer_normalized: bool = True):
    level = level.lower()
    options = []
    if prefer_normalized:
        options.extend(
            [
                (f"normalized_{level}_cache_misses", f"Norm. {level.upper()} misses"),
                (f"{level}_mpki", f"{level.upper()} MPKI"),
            ]
        )
    else:
        options.extend(
            [
                (f"{level}_mpki", f"{level.upper()} MPKI"),
                (f"{level}_cache_misses", f"{level.upper()} misses"),
            ]
        )
    for column, label in options:
        if column in data.columns and pd.to_numeric(data[column], errors="coerce").notna().any():
            return column, label
    warn(f"No usable {level.upper()} cache metric found; cache overlay/subplot will be skipped.")
    return None, None


def save_figure(fig, outdir: Path, stem: str, dpi: int):
    outdir.mkdir(parents=True, exist_ok=True)
    for extension in FIG_EXTENSIONS:
        path = outdir / f"{stem}.{extension}"
        if extension == "png":
            fig.savefig(path, dpi=dpi)
        else:
            fig.savefig(path)
        print(f"[saved] {path}")
    plt.close(fig)


def legend_handles_for_configs(use_hatches: bool = False):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=SVE_COLORS[bits],
            edgecolor="black",
            linewidth=0.35,
            hatch=HATCHES[bits] if use_hatches else "",
            label=f"SVE-{bits}",
        )
        for bits in SVE_BITS
    ]
    handles.append(
        Line2D(
            [0],
            [0],
            color=CACHE_LINE_COLOR,
            linewidth=0.8,
            marker="o",
            markersize=3,
            label="cache",
        )
    )
    return handles


def plot_fig1_speedup_cache_grid(data, outdir: Path, dpi: int, use_hatches: bool):
    cache_column, cache_label = choose_cache_metric(data, "l2", prefer_normalized=True)
    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 1 skipped: no models found.")
        return

    nrows = len(models)
    ncols = len(CODEBOOK_SIZES)
    fig_width = 7.15
    fig_height = max(2.1, 1.55 * nrows + 0.85)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(fig_width, fig_height),
        sharex=True,
        sharey="row",
        constrained_layout=True,
    )
    axes = np.asarray(axes).reshape(nrows, ncols)

    x = np.arange(len(LEARNERS))
    width = 0.22
    offsets = (np.arange(len(SVE_BITS)) - 1) * width

    for row, model in enumerate(models):
        for col, cb_size in enumerate(CODEBOOK_SIZES):
            ax = axes[row, col]
            ax2 = ax.twinx() if cache_column else None
            if ax2 is not None:
                set_axes_common(ax2, horizontal_grid=False)

            for sve_index, bits in enumerate(SVE_BITS):
                mask_base = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["codebook_size"].eq(cb_size)
                    & data["sve_bits"].eq(bits)
                )
                heights = [
                    first_metric(data, mask_base & data["n_learners"].eq(n), "speedup")
                    for n in LEARNERS
                ]
                finite_bar(
                    ax,
                    x + offsets[sve_index],
                    heights,
                    width=width,
                    color=SVE_COLORS[bits],
                    edgecolor="black",
                    linewidth=0.35,
                    hatch=HATCHES[bits] if use_hatches else "",
                )

                if ax2 is not None:
                    cache_values = [
                        first_metric(data, mask_base & data["n_learners"].eq(n), cache_column)
                        for n in LEARNERS
                    ]
                    finite_line(
                        ax2,
                        x + offsets[sve_index],
                        cache_values,
                        color=CACHE_LINE_COLOR,
                        marker=MARKERS[bits],
                        markersize=3.0,
                        linewidth=0.75,
                        linestyle="--",
                    )

            ax.axhline(1.0, color="black", linewidth=0.65, linestyle=(0, (3, 2)))
            ax.set_xticks(x)
            ax.set_xticklabels([str(n) for n in LEARNERS])
            ax.set_title(f"CB={cb_size}" if row == 0 else "")
            if col == 0:
                ax.set_ylabel(f"{model}\nSpeedup")
            if row == nrows - 1:
                ax.set_xlabel("N_LEARNERS")
            set_axes_common(ax)

            if ax2 is not None:
                if col == ncols - 1:
                    ax2.set_ylabel(cache_label)
                else:
                    ax2.set_yticklabels([])

    handles = legend_handles_for_configs(use_hatches)
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=len(handles),
        frameon=False,
        bbox_to_anchor=(0.5, 1.08),
        columnspacing=1.0,
        handlelength=1.4,
    )
    fig.suptitle("Speedup and cache behavior under learner and codebook scaling.", y=1.02)
    save_figure(fig, outdir, "fig1_speedup_cache_grid", dpi)


def plot_fig2_execution_time_cb8(data, outdir: Path, dpi: int, use_hatches: bool):
    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 2 skipped: no models found.")
        return

    subset = data[data["is_dense_baseline"] | data["codebook_size"].eq(8)].copy()
    if subset.empty:
        warn("Figure 2 skipped: no CB=8 or dense baseline data found.")
        return

    medians = subset.groupby("model")["execution_time"].median().dropna()
    use_log = len(medians) > 1 and (medians.max() / max(medians.min(), 1e-30) > 8.0)
    ncols = len(models)
    fig, axes = plt.subplots(
        1,
        ncols,
        figsize=(7.15, 2.45),
        sharey=use_log,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    categories = [
        ("Dense baseline", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]
    x = np.arange(len(LEARNERS))
    width = 0.18
    offsets = (np.arange(len(categories)) - 1.5) * width
    label_values = (not use_log) and (len(models) * len(LEARNERS) * len(categories) <= 24)

    for ax, model in zip(axes, models):
        for index, (label, bits) in enumerate(categories):
            if bits is None:
                mask_base = data["model"].eq(model) & data["is_dense_baseline"]
            else:
                mask_base = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["codebook_size"].eq(8)
                    & data["sve_bits"].eq(bits)
                )
            heights = [
                first_metric(data, mask_base & data["n_learners"].eq(n), "execution_time")
                for n in LEARNERS
            ]
            bars = finite_bar(
                ax,
                x + offsets[index],
                heights,
                width=width,
                color=CONFIG_COLORS[label],
                edgecolor="black",
                linewidth=0.35,
                hatch=HATCHES[label] if use_hatches else "",
            )
            if bars is not None and label_values:
                for bar in bars:
                    value = bar.get_height()
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        value,
                        format_bar_label(value),
                        ha="center",
                        va="bottom",
                        fontsize=5.4,
                        rotation=90,
                    )

        if use_log:
            ax.set_yscale("log")
        ax.set_title(model)
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in LEARNERS])
        ax.set_xlabel("N_LEARNERS")
        ax.set_ylabel("Execution time [s]")
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        set_axes_common(ax)

    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=CONFIG_COLORS[label],
            edgecolor="black",
            linewidth=0.35,
            hatch=HATCHES[label] if use_hatches else "",
            label=("Dense" if label == "Dense baseline" else label),
        )
        for label, _bits in categories
    ]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.08))
    save_figure(fig, outdir, "fig2_execution_time_cb8", dpi)


def plot_fig2b_execution_time_cb_sweep_speedup(
    data,
    outdir: Path,
    dpi: int,
    use_hatches: bool,
):
    # First two x positions use CB=8; last three show the N=4 codebook sweep.
    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 2b skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]
    categories = [
        ("Dense baseline", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]
    relevant = []
    for model in models:
        for _tick, learners, cb_size in x_specs:
            relevant.append(
                data[
                    data["model"].eq(model)
                    & data["n_learners"].eq(learners)
                    & (
                        data["is_dense_baseline"]
                        | ((~data["is_dense_baseline"]) & data["codebook_size"].eq(cb_size))
                    )
                ]
            )
    subset = pd.concat(relevant, ignore_index=True) if relevant else pd.DataFrame()
    if subset.empty:
        warn("Figure 2b skipped: no matching CB sweep data found.")
        return

    medians = subset.groupby("model")["execution_time"].median().dropna()
    use_log = len(medians) > 1 and (medians.max() / max(medians.min(), 1e-30) > 8.0)
    fig, axes = plt.subplots(
        1,
        len(models),
        figsize=(7.15, 2.65),
        sharey=use_log,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    x = np.arange(len(x_specs))
    width = 0.16
    offsets = (np.arange(len(categories)) - 1.5) * width

    for ax, model in zip(axes, models):
        ax2 = ax.twinx()
        set_axes_common(ax2, horizontal_grid=False)

        for index, (label, bits) in enumerate(categories):
            heights = []
            for _tick, learners, cb_size in x_specs:
                if bits is None:
                    mask = (
                        data["model"].eq(model)
                        & data["is_dense_baseline"]
                        & data["n_learners"].eq(learners)
                    )
                else:
                    mask = (
                        data["model"].eq(model)
                        & (~data["is_dense_baseline"])
                        & data["n_learners"].eq(learners)
                        & data["codebook_size"].eq(cb_size)
                        & data["sve_bits"].eq(bits)
                    )
                heights.append(first_metric(data, mask, "execution_time"))

            finite_bar(
                ax,
                x + offsets[index],
                heights,
                width=width,
                color=CONFIG_COLORS[label],
                edgecolor="black",
                linewidth=0.35,
                hatch=HATCHES[label] if use_hatches else "",
            )

        for bits in SVE_BITS:
            speedups = []
            for _tick, learners, cb_size in x_specs:
                mask = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["n_learners"].eq(learners)
                    & data["codebook_size"].eq(cb_size)
                    & data["sve_bits"].eq(bits)
                )
                speedups.append(first_metric(data, mask, "speedup"))
            finite_line(
                ax2,
                x,
                speedups,
                color=SVE_COLORS[bits],
                marker=MARKERS[bits],
                markersize=3.2,
                linewidth=0.9,
                linestyle="-",
            )

        ax2.axhline(1.0, color="0.25", linewidth=0.6, linestyle=(0, (3, 2)))
        ax2.set_ylabel("Speedup")
        ax2.grid(False)

        if use_log:
            ax.set_yscale("log")
        ax.set_title(model)
        ax.set_xticks(x)
        ax.set_xticklabels([tick for tick, _learners, _cb in x_specs])
        ax.set_xlabel("N_LEARNERS / CODEBOOK_SIZE")
        ax.set_ylabel("Execution time [s]")
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        set_axes_common(ax)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    bar_handles = [
        Patch(
            facecolor=CONFIG_COLORS[label],
            edgecolor="black",
            linewidth=0.35,
            hatch=HATCHES[label] if use_hatches else "",
            label=("Dense" if label == "Dense baseline" else label),
        )
        for label, _bits in categories
    ]
    line_handles = [
        Line2D(
            [0],
            [0],
            color=SVE_COLORS[bits],
            marker=MARKERS[bits],
            linewidth=0.9,
            markersize=3.2,
            label=f"{bits} speedup",
        )
        for bits in SVE_BITS
    ]
    fig.legend(
        handles=bar_handles + line_handles,
        loc="upper center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 1.12),
        columnspacing=0.9,
        handlelength=1.4,
    )
    save_figure(fig, outdir, "fig2b_execution_time_cb_sweep_speedup", dpi)


def plot_fig2b_stack_vertical_execution_time_cb_sweep_speedup(
    data,
    outdir: Path,
    dpi: int,
    use_hatches: bool,
):
    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 2b vertical skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]
    categories = [
        ("Dense baseline", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]
    fig, axes = plt.subplots(
        len(models),
        1,
        figsize=(4.2, 2.55 * len(models) + 0.75),
        sharex=False,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    x = np.arange(len(x_specs))
    width = 0.16
    offsets = (np.arange(len(categories)) - 1.5) * width

    for ax, model in zip(axes, models):
        ax2 = ax.twinx()
        set_axes_common(ax2, horizontal_grid=False)
        ax2.patch.set_visible(False)

        for index, (label, bits) in enumerate(categories):
            heights = []
            for _tick, learners, cb_size in x_specs:
                if bits is None:
                    mask = (
                        data["model"].eq(model)
                        & data["is_dense_baseline"]
                        & data["n_learners"].eq(learners)
                    )
                else:
                    mask = (
                        data["model"].eq(model)
                        & (~data["is_dense_baseline"])
                        & data["n_learners"].eq(learners)
                        & data["codebook_size"].eq(cb_size)
                        & data["sve_bits"].eq(bits)
                    )
                heights.append(first_metric(data, mask, "execution_time"))

            finite_bar(
                ax,
                x + offsets[index],
                heights,
                width=width,
                color=CONFIG_COLORS[label],
                edgecolor="black",
                linewidth=0.35,
                hatch=HATCHES[label] if use_hatches else "",
                alpha=0.88,
                zorder=1,
            )

        for bits in SVE_BITS:
            speedups = []
            for _tick, learners, cb_size in x_specs:
                mask = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["n_learners"].eq(learners)
                    & data["codebook_size"].eq(cb_size)
                    & data["sve_bits"].eq(bits)
                )
                speedups.append(first_metric(data, mask, "speedup"))
            lines = finite_line(
                ax2,
                x,
                speedups,
                color=SVE_COLORS[bits],
                marker=MARKERS[bits],
                markersize=3.6,
                linewidth=1.05,
                linestyle="-",
                markeredgecolor="white",
                markeredgewidth=0.55,
                zorder=5,
            )
            add_line_halo(lines, linewidth=2.45, color="white")

        ax2.axhline(1.0, color="0.25", linewidth=0.6, linestyle=(0, (3, 2)), zorder=0)
        ax2.set_ylabel("Speedup")
        ax2.grid(False)

        ax.set_yscale("log")
        ax.set_title(model)
        ax.set_xticks(x)
        ax.set_xticklabels([tick for tick, _learners, _cb in x_specs])
        ax.set_xlabel("N_LEARNERS / CODEBOOK_SIZE")
        ax.set_ylabel("Execution time [s]")
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        set_axes_common(ax)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    bar_handles = [
        Patch(
            facecolor=CONFIG_COLORS[label],
            edgecolor="black",
            linewidth=0.35,
            hatch=HATCHES[label] if use_hatches else "",
            label=("Dense" if label == "Dense baseline" else label),
        )
        for label, _bits in categories
    ]
    line_handles = [
        Line2D(
            [0],
            [0],
            color=SVE_COLORS[bits],
            marker=MARKERS[bits],
            linewidth=1.05,
            markersize=3.6,
            markeredgecolor="white",
            markeredgewidth=0.55,
            label=f"{bits} speedup",
        )
        for bits in SVE_BITS
    ]
    for handle in line_handles:
        add_line_halo([handle], linewidth=2.45, color="white")
    fig.legend(
        handles=bar_handles + line_handles,
        loc="upper center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 1.06),
        columnspacing=0.9,
        handlelength=1.4,
    )
    save_figure(fig, outdir, "fig2b_stack_vertical_execution_time_cb_sweep_speedup", dpi)



def plot_fig2_cache_miss_overlay(
    data,
    outdir: Path,
    dpi: int,
    use_hatches: bool,
    metric_column: str,
    metric_label: str,
    output_stem: str,
):
    if metric_column not in data.columns:
        warn(f"{output_stem} skipped: missing {metric_column}.")
        return

    models = model_order(data["model"].dropna().unique())
    if not models:
        warn(f"{output_stem} skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]
    categories = [
        ("Dense baseline", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]

    relevant = []
    for model in models:
        for _tick, learners, cb_size in x_specs:
            relevant.append(
                data[
                    data["model"].eq(model)
                    & data["n_learners"].eq(learners)
                    & (
                        data["is_dense_baseline"]
                        | ((~data["is_dense_baseline"]) & data["codebook_size"].eq(cb_size))
                    )
                ]
            )
    subset = pd.concat(relevant, ignore_index=True) if relevant else pd.DataFrame()
    if subset.empty or subset[metric_column].dropna().empty:
        warn(f"{output_stem} skipped: no matching cache-miss data found.")
        return

    medians = subset.groupby("model")["execution_time"].median().dropna()
    use_log = len(medians) > 1 and (medians.max() / max(medians.min(), 1e-30) > 8.0)
    fig, axes = plt.subplots(
        1,
        len(models),
        figsize=(7.15, 2.65),
        sharey=use_log,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    x = np.arange(len(x_specs))
    width = 0.16
    offsets = (np.arange(len(categories)) - 1.5) * width

    for ax, model in zip(axes, models):
        ax2 = ax.twinx()
        set_axes_common(ax2, horizontal_grid=False)

        for index, (label, bits) in enumerate(categories):
            heights = []
            for _tick, learners, cb_size in x_specs:
                if bits is None:
                    mask = (
                        data["model"].eq(model)
                        & data["is_dense_baseline"]
                        & data["n_learners"].eq(learners)
                    )
                else:
                    mask = (
                        data["model"].eq(model)
                        & (~data["is_dense_baseline"])
                        & data["n_learners"].eq(learners)
                        & data["codebook_size"].eq(cb_size)
                        & data["sve_bits"].eq(bits)
                    )
                heights.append(first_metric(data, mask, "execution_time"))

            finite_bar(
                ax,
                x + offsets[index],
                heights,
                width=width,
                color=CONFIG_COLORS[label],
                edgecolor="black",
                linewidth=0.35,
                hatch=HATCHES[label] if use_hatches else "",
                alpha=0.86,
            )

        for bits in SVE_BITS:
            misses = []
            for _tick, learners, cb_size in x_specs:
                mask = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["n_learners"].eq(learners)
                    & data["codebook_size"].eq(cb_size)
                    & data["sve_bits"].eq(bits)
                )
                misses.append(first_metric(data, mask, metric_column))
            finite_line(
                ax2,
                x,
                misses,
                color=SVE_COLORS[bits],
                marker=MARKERS[bits],
                markersize=3.2,
                linewidth=0.95,
                linestyle="-",
            )

        ax2.set_ylabel(metric_label)
        ax2.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        ax2.grid(False)

        if use_log:
            ax.set_yscale("log")
        ax.set_title(model)
        ax.set_xticks(x)
        ax.set_xticklabels([tick for tick, _learners, _cb in x_specs])
        ax.set_xlabel("Within each group: Dense, 128, 256, 512")
        ax.set_ylabel("Execution time [s]")
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        set_axes_common(ax)

    from matplotlib.lines import Line2D

    line_handles = [
        Line2D(
            [0],
            [0],
            color=SVE_COLORS[bits],
            marker=MARKERS[bits],
            linewidth=0.95,
            markersize=3.2,
            label=f"SVE-{bits}",
        )
        for bits in SVE_BITS
    ]
    fig.legend(
        handles=line_handles,
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 1.08),
        columnspacing=0.9,
        handlelength=1.4,
    )
    save_figure(fig, outdir, output_stem, dpi)


def plot_fig2g_cache_misses_grid(data, outdir: Path, dpi: int):
    plot_cache_misses_grid(
        data,
        outdir,
        dpi,
        output_stem="fig2g_cache_misses_grid",
        include_dense_baseline=False,
    )


def plot_fig2g_v2_cache_misses_grid_with_dense(data, outdir: Path, dpi: int):
    plot_cache_misses_grid(
        data,
        outdir,
        dpi,
        output_stem="fig2g_v2_cache_misses_grid_with_dense",
        include_dense_baseline=True,
    )


def plot_cache_misses_grid(
    data,
    outdir: Path,
    dpi: int,
    output_stem: str,
    include_dense_baseline: bool,
):
    metrics = [
        ("l1d_cache_misses", "L1D misses"),
        ("l1i_cache_misses", "L1I misses"),
        ("l2_cache_misses", "L2 misses"),
    ]
    available_metrics = [
        (column, label)
        for column, label in metrics
        if column in data.columns and data[column].dropna().any()
    ]
    if len(available_metrics) != len(metrics):
        missing = [label for column, label in metrics if column not in data.columns or data[column].dropna().empty]
        warn("Figure 2g: missing cache metrics skipped: " + ", ".join(missing))
    if not available_metrics:
        warn("Figure 2g skipped: no cache-miss metrics available.")
        return

    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 2g skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]

    fig, axes = plt.subplots(
        len(available_metrics),
        len(models),
        figsize=(7.15, 4.85),
        sharex=True,
        constrained_layout=True,
    )
    axes = np.asarray(axes).reshape(len(available_metrics), len(models))
    x = np.arange(len(x_specs))

    for row, (metric_column, metric_label) in enumerate(available_metrics):
        for col, model in enumerate(models):
            ax = axes[row, col]
            if include_dense_baseline:
                dense_values = []
                for _tick, learners, _cb_size in x_specs:
                    mask = (
                        data["model"].eq(model)
                        & data["is_dense_baseline"]
                        & data["n_learners"].eq(learners)
                    )
                    dense_values.append(first_metric(data, mask, metric_column))
                finite_line(
                    ax,
                    x,
                    dense_values,
                    color=BASELINE_COLOR,
                    marker="D",
                    markersize=2.9,
                    linewidth=0.9,
                    linestyle=(0, (3, 2)),
                )

            for bits in SVE_BITS:
                values = []
                for _tick, learners, cb_size in x_specs:
                    mask = (
                        data["model"].eq(model)
                        & (~data["is_dense_baseline"])
                        & data["n_learners"].eq(learners)
                        & data["codebook_size"].eq(cb_size)
                        & data["sve_bits"].eq(bits)
                    )
                    values.append(first_metric(data, mask, metric_column))
                finite_line(
                    ax,
                    x,
                    values,
                    color=SVE_COLORS[bits],
                    marker=MARKERS[bits],
                    markersize=3.0,
                    linewidth=0.95,
                    linestyle="-",
                )

            if row == 0:
                ax.set_title(model)
            if col == 0:
                ax.set_ylabel(metric_label)
            ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
            ax.set_xticks(x)
            if row == len(available_metrics) - 1:
                ax.set_xticklabels([tick for tick, _learners, _cb in x_specs])
                ax.set_xlabel("N_LEARNERS / CODEBOOK_SIZE")
            else:
                ax.set_xticklabels([])
            set_axes_common(ax)

    from matplotlib.lines import Line2D

    handles = [
        Line2D(
            [0],
            [0],
            color=BASELINE_COLOR,
            marker="D",
            linewidth=0.9,
            markersize=2.9,
            linestyle=(0, (3, 2)),
            label="Dense baseline",
        )
    ] if include_dense_baseline else []
    handles += [
        Line2D(
            [0],
            [0],
            color=SVE_COLORS[bits],
            marker=MARKERS[bits],
            linewidth=0.95,
            markersize=3.0,
            label=f"SVE-{bits}",
        )
        for bits in SVE_BITS
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=4 if include_dense_baseline else 3,
        frameon=False,
        bbox_to_anchor=(0.5, 1.05),
        columnspacing=1.0,
        handlelength=1.5,
    )
    save_figure(fig, outdir, output_stem, dpi)


def plot_fig2g_v2_split_cache_misses_for_model(
    data,
    outdir: Path,
    dpi: int,
    model: str,
    output_stem: str,
):
    metrics = [
        ("l1d_cache_misses", "L1D misses"),
        ("l1i_cache_misses", "L1I misses"),
        ("l2_cache_misses", "L2 misses"),
    ]
    available_metrics = [
        (column, label)
        for column, label in metrics
        if column in data.columns and data[column].dropna().any()
    ]
    if not available_metrics:
        warn(f"{output_stem} skipped: no cache-miss metrics available.")
        return

    models = model_order(data["model"].dropna().unique())
    matches = [name for name in models if name.lower() == model.lower()]
    if not matches:
        warn(f"{output_stem} skipped: model {model} not found.")
        return
    model = matches[0]

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]

    fig, axes = plt.subplots(
        len(available_metrics),
        1,
        figsize=(4.2, 1.75 * len(available_metrics) + 0.85),
        sharex=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    x = np.arange(len(x_specs))

    for row, (metric_column, metric_label) in enumerate(available_metrics):
        ax = axes[row]
        dense_values = []
        for _tick, learners, _cb_size in x_specs:
            mask = (
                data["model"].eq(model)
                & data["is_dense_baseline"]
                & data["n_learners"].eq(learners)
            )
            dense_values.append(first_metric(data, mask, metric_column))
        finite_line(
            ax,
            x,
            dense_values,
            color=BASELINE_COLOR,
            marker="D",
            markersize=3.0,
            linewidth=0.9,
            linestyle=(0, (3, 2)),
        )

        for bits in SVE_BITS:
            values = []
            for _tick, learners, cb_size in x_specs:
                mask = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["n_learners"].eq(learners)
                    & data["codebook_size"].eq(cb_size)
                    & data["sve_bits"].eq(bits)
                )
                values.append(first_metric(data, mask, metric_column))
            finite_line(
                ax,
                x,
                values,
                color=SVE_COLORS[bits],
                marker=MARKERS[bits],
                markersize=3.1,
                linewidth=1.0,
                linestyle="-",
            )

        ax.set_ylabel(metric_label)
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        ax.set_xticks(x)
        if row == len(available_metrics) - 1:
            ax.set_xticklabels([tick for tick, _learners, _cb in x_specs])
            ax.set_xlabel("N_LEARNERS / CODEBOOK_SIZE")
        else:
            ax.set_xticklabels([])
        if row == 0:
            ax.set_title(model)
        set_axes_common(ax)

    from matplotlib.lines import Line2D

    handles = [
        Line2D(
            [0],
            [0],
            color=BASELINE_COLOR,
            marker="D",
            linewidth=0.9,
            markersize=3.0,
            linestyle=(0, (3, 2)),
            label="Dense baseline",
        )
    ]
    handles += [
        Line2D(
            [0],
            [0],
            color=SVE_COLORS[bits],
            marker=MARKERS[bits],
            linewidth=1.0,
            markersize=3.1,
            label=f"SVE-{bits}",
        )
        for bits in SVE_BITS
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 1.07),
        columnspacing=1.0,
        handlelength=1.5,
    )
    save_figure(fig, outdir, output_stem, dpi)


def plot_fig2g_v2_split_cache_misses_by_model(data, outdir: Path, dpi: int):
    plot_fig2g_v2_split_cache_misses_for_model(
        data,
        outdir,
        dpi,
        "BERT-mini",
        "fig2g_v2_bert_mini_cache_misses_with_dense",
    )
    plot_fig2g_v2_split_cache_misses_for_model(
        data,
        outdir,
        dpi,
        "BERT-base",
        "fig2g_v2_bert_base_cache_misses_with_dense",
    )



def plot_fig2g_v2_stack_vertical_cache_misses_grid_with_dense(data, outdir: Path, dpi: int):
    metrics = [
        ("l1d_cache_misses", "L1D misses"),
        ("l1i_cache_misses", "L1I misses"),
        ("l2_cache_misses", "L2 misses"),
    ]
    available_metrics = [
        (column, label)
        for column, label in metrics
        if column in data.columns and data[column].dropna().any()
    ]
    if not available_metrics:
        warn("Figure 2g v2 vertical skipped: no cache-miss metrics available.")
        return

    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 2g v2 vertical skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]

    nrows = len(models) * len(available_metrics)
    fig, axes = plt.subplots(
        nrows,
        1,
        figsize=(4.2, 1.45 * nrows + 0.9),
        sharex=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    x = np.arange(len(x_specs))

    row_index = 0
    for model in models:
        for metric_column, metric_label in available_metrics:
            ax = axes[row_index]
            dense_values = []
            for _tick, learners, _cb_size in x_specs:
                mask = (
                    data["model"].eq(model)
                    & data["is_dense_baseline"]
                    & data["n_learners"].eq(learners)
                )
                dense_values.append(first_metric(data, mask, metric_column))
            finite_line(
                ax,
                x,
                dense_values,
                color=BASELINE_COLOR,
                marker="D",
                markersize=2.8,
                linewidth=0.9,
                linestyle=(0, (3, 2)),
            )

            for bits in SVE_BITS:
                values = []
                for _tick, learners, cb_size in x_specs:
                    mask = (
                        data["model"].eq(model)
                        & (~data["is_dense_baseline"])
                        & data["n_learners"].eq(learners)
                        & data["codebook_size"].eq(cb_size)
                        & data["sve_bits"].eq(bits)
                    )
                    values.append(first_metric(data, mask, metric_column))
                finite_line(
                    ax,
                    x,
                    values,
                    color=SVE_COLORS[bits],
                    marker=MARKERS[bits],
                    markersize=2.9,
                    linewidth=0.95,
                    linestyle="-",
                )

            ax.set_ylabel(f"{model}\n{metric_label}" if metric_column == available_metrics[0][0] else metric_label)
            ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
            ax.set_xticks(x)
            if row_index == nrows - 1:
                ax.set_xticklabels([tick for tick, _learners, _cb in x_specs])
                ax.set_xlabel("N_LEARNERS / CODEBOOK_SIZE")
            else:
                ax.set_xticklabels([])
            set_axes_common(ax)
            row_index += 1

    from matplotlib.lines import Line2D

    handles = [
        Line2D(
            [0],
            [0],
            color=BASELINE_COLOR,
            marker="D",
            linewidth=0.9,
            markersize=2.8,
            linestyle=(0, (3, 2)),
            label="Dense baseline",
        )
    ]
    handles += [
        Line2D(
            [0],
            [0],
            color=SVE_COLORS[bits],
            marker=MARKERS[bits],
            linewidth=0.95,
            markersize=2.9,
            label=f"SVE-{bits}",
        )
        for bits in SVE_BITS
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 1.04),
        columnspacing=1.0,
        handlelength=1.5,
    )
    save_figure(fig, outdir, "fig2g_v2_stack_vertical_cache_misses_grid_with_dense", dpi)



def valid_stage_vector(vector, final_time=None) -> bool:
    if final_time is None:
        final_time = np.nan
    values = np.asarray(vector, dtype=float)
    finite = np.isfinite(values)
    if not finite.any() or np.any(values[finite] < 0):
        return False
    total = np.nansum(values)
    if total <= 0:
        return False
    if np.isfinite(final_time) and final_time > 0:
        return abs(total - final_time) / final_time <= 0.05
    return True


def fallback_stage_stack(stage_data, subset, final_time):
    if subset.empty or not np.isfinite(final_time) or final_time <= 0:
        return None

    row = subset.iloc[0]
    current_exp = row.get("exp_id")
    mask = stage_data["model"].eq(row["model"])
    if pd.notna(current_exp) and "exp_id" in stage_data.columns:
        mask &= ~stage_data["exp_id"].eq(current_exp)

    if bool(row.get("is_dense_baseline", False)):
        mask &= stage_data["is_dense_baseline"]
    else:
        mask &= (
            (~stage_data["is_dense_baseline"])
            & stage_data["codebook_size"].eq(row["codebook_size"])
            & stage_data["sve_bits"].eq(row["sve_bits"])
        )

    ratios = []
    for _exp_id, candidate in stage_data[mask].groupby("exp_id"):
        values = candidate.groupby("interval")["execution_time"].sum()
        vector = np.asarray([float(values.get(stage, np.nan)) for stage in STAGE_ORDER])
        candidate_final = first_metric(candidate, candidate.index == candidate.index, "final_execution_time")
        if valid_stage_vector(vector, candidate_final):
            ratios.append(vector / np.nansum(vector))

    if not ratios:
        return None
    return (np.nanmean(np.vstack(ratios), axis=0) * final_time).tolist()


def stage_stack_values(stage_data, model: str, learners: int, cb_size: int, bits: int | None):
    if bits is None:
        mask = (
            stage_data["model"].eq(model)
            & stage_data["is_dense_baseline"]
            & stage_data["n_learners"].eq(learners)
        )
    else:
        mask = (
            stage_data["model"].eq(model)
            & (~stage_data["is_dense_baseline"])
            & stage_data["n_learners"].eq(learners)
            & stage_data["codebook_size"].eq(cb_size)
            & stage_data["sve_bits"].eq(bits)
        )
    subset = stage_data[mask]
    if subset.empty:
        return [np.nan for _stage in STAGE_ORDER]

    values = subset.groupby("interval")["execution_time"].sum()
    stack = [float(values.get(stage, np.nan)) for stage in STAGE_ORDER]
    final_time = first_metric(
        subset,
        pd.Series(True, index=subset.index),
        "final_execution_time",
    )
    if not valid_stage_vector(stack, final_time):
        fallback = fallback_stage_stack(stage_data, subset, final_time)
        if fallback is not None:
            return fallback
        warn(
            "Using clipped stage times because no valid fallback proportions were found "
            f"for {model}, N={learners}, CB={cb_size}, SVE={bits}."
        )
        clipped = np.clip(np.asarray(stack, dtype=float), 0, None)
        total = np.nansum(clipped)
        if np.isfinite(final_time) and final_time > 0 and total > 0:
            clipped = clipped / total * final_time
        return clipped.tolist()
    return stack


def plot_fig2c_execution_time_stage_breakdown(
    stage_data,
    outdir: Path,
    dpi: int,
    use_hatches: bool,
):
    if stage_data.empty:
        warn("Figure 2c skipped: no stage data available.")
        return

    models = model_order(stage_data["model"].dropna().unique())
    if not models:
        warn("Figure 2c skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]
    categories = [
        ("Dense", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]

    fig, axes = plt.subplots(
        1,
        len(models),
        figsize=(7.15, 2.9),
        sharey=False,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    n_categories = len(categories)
    group_gap = 0.72
    bar_width = 0.17
    group_width = n_categories * bar_width + group_gap
    category_offsets = (np.arange(n_categories) - (n_categories - 1) / 2.0) * bar_width
    group_centers = np.arange(len(x_specs)) * group_width

    for ax, model in zip(axes, models):
        ymax = 0.0

        for group_index, (_tick, learners, cb_size) in enumerate(x_specs):
            center = group_centers[group_index]
            for category_index, (category_label, bits) in enumerate(categories):
                xpos = center + category_offsets[category_index]
                stack = stage_stack_values(stage_data, model, learners, cb_size, bits)
                stack_values = np.asarray(stack, dtype=float)
                if not np.isfinite(stack_values).any():
                    continue

                bottom = 0.0
                for stage, value in zip(STAGE_ORDER, stack_values):
                    if not np.isfinite(value) or value <= 0:
                        continue
                    ax.bar(
                        xpos,
                        value,
                        width=bar_width * 0.92,
                        bottom=bottom,
                        color=STAGE_COLORS[stage],
                        edgecolor="black",
                        linewidth=0.25,
                        hatch=STAGE_HATCHES[stage] if use_hatches else "",
                    )
                    bottom += value

                ymax = max(ymax, bottom)

        ax.set_title(model)
        ax.set_ylabel("Execution time [s]")
        ax.set_xticks(group_centers)
        ax.set_xticklabels([tick for tick, _learners, _cb in x_specs], rotation=0)
        ax.set_xlabel("Within each group: Dense, 128, 256, 512")
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        if ymax > 0:
            ax.set_ylim(0, ymax * 1.08)
        set_axes_common(ax)

    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=STAGE_COLORS[stage],
            edgecolor="black",
            linewidth=0.25,
            hatch=STAGE_HATCHES[stage] if use_hatches else "",
            label=STAGE_LABELS[stage],
        )
        for stage in STAGE_ORDER
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 1.13),
        columnspacing=1.0,
        handlelength=1.4,
    )
    save_figure(fig, outdir, "fig2c_execution_time_stage_breakdown", dpi)



def plot_fig2c_stack_vertical_execution_time_stage_breakdown(
    stage_data,
    outdir: Path,
    dpi: int,
    use_hatches: bool,
):
    if stage_data.empty:
        warn("Figure 2c vertical skipped: no stage data available.")
        return

    models = model_order(stage_data["model"].dropna().unique())
    if not models:
        warn("Figure 2c vertical skipped: no models found.")
        return

    x_specs = [
        ("1\nCB=8", 1, 8),
        ("2\nCB=8", 2, 8),
        ("4\nCB=4", 4, 4),
        ("4\nCB=8", 4, 8),
        ("4\nCB=16", 4, 16),
    ]
    categories = [
        ("Dense", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]

    fig, axes = plt.subplots(
        len(models),
        1,
        figsize=(4.2, 2.65 * len(models) + 0.75),
        sharex=False,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    n_categories = len(categories)
    group_gap = 0.72
    bar_width = 0.17
    group_width = n_categories * bar_width + group_gap
    category_offsets = (np.arange(n_categories) - (n_categories - 1) / 2.0) * bar_width
    group_centers = np.arange(len(x_specs)) * group_width

    for ax, model in zip(axes, models):
        ymax = 0.0
        for group_index, (_tick, learners, cb_size) in enumerate(x_specs):
            center = group_centers[group_index]
            for category_index, (_category_label, bits) in enumerate(categories):
                xpos = center + category_offsets[category_index]
                stack = stage_stack_values(stage_data, model, learners, cb_size, bits)
                stack_values = np.asarray(stack, dtype=float)
                if not np.isfinite(stack_values).any():
                    continue

                bottom = 0.0
                for stage, value in zip(STAGE_ORDER, stack_values):
                    if not np.isfinite(value) or value <= 0:
                        continue
                    ax.bar(
                        xpos,
                        value,
                        width=bar_width * 0.92,
                        bottom=bottom,
                        color=STAGE_COLORS[stage],
                        edgecolor="black",
                        linewidth=0.25,
                        hatch=STAGE_HATCHES[stage] if use_hatches else "",
                    )
                    bottom += value
                ymax = max(ymax, bottom)

        ax.set_title(model)
        ax.set_ylabel("Execution time [s]")
        ax.set_xticks(group_centers)
        ax.set_xticklabels([tick for tick, _learners, _cb in x_specs], rotation=0)
        ax.set_xlabel("Within each group: Dense, 128, 256, 512")
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        if ymax > 0:
            ax.set_ylim(0, ymax * 1.08)
        set_axes_common(ax)

    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=STAGE_COLORS[stage],
            edgecolor="black",
            linewidth=0.25,
            hatch=STAGE_HATCHES[stage] if use_hatches else "",
            label=STAGE_LABELS[stage],
        )
        for stage in STAGE_ORDER
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 1.08),
        columnspacing=1.0,
        handlelength=1.4,
    )
    save_figure(fig, outdir, "fig2c_stack_vertical_execution_time_stage_breakdown", dpi)



def plot_fig3_codebook_scaling(data, outdir: Path, dpi: int, use_hatches: bool):
    cache_column, cache_label = choose_cache_metric(data, "l2", prefer_normalized=True)
    subset = data[(~data["is_dense_baseline"]) & data["n_learners"].eq(4)].copy()
    if subset.empty:
        warn("Figure 3 skipped: no N_LEARNERS=4 codebook data found.")
        return

    models = model_order(subset["model"].dropna().unique())
    fig, axes = plt.subplots(
        1,
        len(models),
        figsize=(7.15, 2.45),
        sharey=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)

    x = np.arange(len(SVE_BITS))
    width = 0.22
    offsets = (np.arange(len(CODEBOOK_SIZES)) - 1) * width

    for ax, model in zip(axes, models):
        ax2 = ax.twinx() if cache_column else None
        if ax2 is not None:
            set_axes_common(ax2, horizontal_grid=False)

        for index, cb_size in enumerate(CODEBOOK_SIZES):
            mask_base = (
                subset["model"].eq(model)
                & subset["codebook_size"].eq(cb_size)
            )
            heights = [
                first_metric(subset, mask_base & subset["sve_bits"].eq(bits), "speedup")
                for bits in SVE_BITS
            ]
            finite_bar(
                ax,
                x + offsets[index],
                heights,
                width=width,
                color=CB_COLORS[cb_size],
                edgecolor="black",
                linewidth=0.35,
                hatch=HATCHES[cb_size] if use_hatches else "",
            )
            if ax2 is not None:
                cache_values = [
                    first_metric(subset, mask_base & subset["sve_bits"].eq(bits), cache_column)
                    for bits in SVE_BITS
                ]
                finite_line(
                    ax2,
                    x + offsets[index],
                    cache_values,
                    color=CACHE_LINE_COLOR,
                    marker=MARKERS[cb_size],
                    markersize=3.0,
                    linewidth=0.75,
                    linestyle="--",
                )

        ax.axhline(1.0, color="black", linewidth=0.65, linestyle=(0, (3, 2)))
        ax.set_title(model)
        ax.set_xticks(x)
        ax.set_xticklabels([str(bits) for bits in SVE_BITS])
        ax.set_xlabel("SVE_BITS")
        ax.set_ylabel("Speedup")
        set_axes_common(ax)
        if ax2 is not None:
            ax2.set_ylabel(cache_label)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=CB_COLORS[cb],
            edgecolor="black",
            linewidth=0.35,
            hatch=HATCHES[cb] if use_hatches else "",
            label=f"CB={cb}",
        )
        for cb in CODEBOOK_SIZES
    ]
    if cache_column:
        handles.append(
            Line2D(
                [0],
                [0],
                color=CACHE_LINE_COLOR,
                linewidth=0.8,
                marker="o",
                markersize=3,
                label="cache",
            )
        )
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False, bbox_to_anchor=(0.5, 1.08))
    save_figure(fig, outdir, "fig3_codebook_scaling", dpi)


def choose_summary_model(data, requested_model: str | None) -> str | None:
    models = model_order(data["model"].dropna().unique())
    if not models:
        return None
    if requested_model:
        matches = [model for model in models if model.lower() == requested_model.lower()]
        if matches:
            return matches[0]
        warn(f"Requested summary model '{requested_model}' not found; using an available model.")

    best_model = None
    best_count = -1
    for model in models:
        count = int(
            (
                data["model"].eq(model)
                & data["n_learners"].eq(4)
                & (data["is_dense_baseline"] | data["codebook_size"].eq(8))
            ).sum()
        )
        if count > best_count:
            best_model = model
            best_count = count
    return best_model or models[0]


def summary_values(data, model: str, metric: str):
    categories = [
        ("Dense baseline", None),
        ("SVE-128", 128),
        ("SVE-256", 256),
        ("SVE-512", 512),
    ]
    values = []
    for _label, bits in categories:
        if bits is None:
            mask = data["model"].eq(model) & data["is_dense_baseline"] & data["n_learners"].eq(4)
        else:
            mask = (
                data["model"].eq(model)
                & (~data["is_dense_baseline"])
                & data["n_learners"].eq(4)
                & data["codebook_size"].eq(8)
                & data["sve_bits"].eq(bits)
            )
        values.append(first_metric(data, mask, metric))
    return categories, values


def plot_fig4_summary_runtime_cache(
    data,
    outdir: Path,
    dpi: int,
    use_hatches: bool,
    requested_model: str | None,
):
    model = choose_summary_model(data, requested_model)
    if model is None:
        warn("Figure 4 skipped: no models found.")
        return

    l1_column, l1_label = choose_cache_metric(data, "l1d", prefer_normalized=False)
    l2_column, l2_label = choose_cache_metric(data, "l2", prefer_normalized=False)
    panels = [("execution_time", "Execution time [s]", "(a) Execution time")]
    if l1_column:
        panels.append((l1_column, l1_label, "(b) L1D cache"))
    if l2_column:
        panels.append((l2_column, l2_label, "(c) L2 cache"))
    if len(panels) < 3:
        warn("Figure 4 will contain fewer than three panels because cache metrics are missing.")

    fig, axes = plt.subplots(1, len(panels), figsize=(7.15, 2.0), constrained_layout=True)
    axes = np.atleast_1d(axes)
    tick_labels = ["Dense", "128", "256", "512"]

    for ax, (metric, ylabel, title) in zip(axes, panels):
        categories, values = summary_values(data, model, metric)
        x = np.arange(len(categories))
        labels = [label for label, _bits in categories]
        for xpos, value, label in zip(x, values, labels):
            if not np.isfinite(value):
                continue
            bars = ax.bar(
                [xpos],
                [value],
                width=0.62,
                color=CONFIG_COLORS[label],
                edgecolor="black",
                linewidth=0.35,
                hatch=HATCHES[label] if use_hatches else "",
            )
            if use_hatches:
                bars[0].set_hatch(HATCHES[label])
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(tick_labels, rotation=0)
        ax.set_ylabel(ylabel)
        ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(compact_tick))
        set_axes_common(ax)

    fig.suptitle(f"{model}, N_LEARNERS=4, CB=8", y=1.04)
    save_figure(fig, outdir, "fig4_summary_runtime_cache", dpi)


def plot_fig5_learner_scaling(data, outdir: Path, dpi: int):
    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 5 skipped: no models found.")
        return

    fig, axes = plt.subplots(
        1,
        len(models),
        figsize=(7.15, 2.35),
        sharey=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    series = [
        ("Dense baseline", None, BASELINE_COLOR, "o"),
        ("SVE-128", 128, SVE128_COLOR, "o"),
        ("SVE-256", 256, SVE256_COLOR, "^"),
        ("SVE-512", 512, SVE512_COLOR, "s"),
    ]

    for ax, model in zip(axes, models):
        for label, bits, color, marker in series:
            if bits is None:
                mask_base = data["model"].eq(model) & data["is_dense_baseline"]
            else:
                mask_base = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["codebook_size"].eq(8)
                    & data["sve_bits"].eq(bits)
                )
            times = [
                first_metric(data, mask_base & data["n_learners"].eq(n), "execution_time")
                for n in LEARNERS
            ]
            base_time = times[0]
            if not np.isfinite(base_time) or base_time == 0:
                warn(f"Figure 5: skipping {model} {label}; no N_LEARNERS=1 runtime.")
                continue
            normalized = [value / base_time if np.isfinite(value) else np.nan for value in times]
            finite_line(
                ax,
                LEARNERS,
                normalized,
                color=color,
                marker=marker,
                markersize=3.0,
                linewidth=0.9,
                label=("Dense" if label == "Dense baseline" else f"{label} (CB=8)"),
            )

        ax.plot(
            LEARNERS,
            LEARNERS,
            color="0.35",
            linewidth=0.75,
            linestyle=(0, (3, 2)),
            label="linear",
        )
        ax.set_title(model)
        ax.set_xticks(LEARNERS)
        ax.set_xlabel("N_LEARNERS")
        ax.set_ylabel("Runtime / runtime at N=1")
        set_axes_common(ax)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.08))
    save_figure(fig, outdir, "fig5_learner_scaling", dpi)


def plot_fig5_stack_vertical_learner_scaling(data, outdir: Path, dpi: int):
    models = model_order(data["model"].dropna().unique())
    if not models:
        warn("Figure 5 vertical skipped: no models found.")
        return

    fig, axes = plt.subplots(
        len(models),
        1,
        figsize=(4.2, 2.2 * len(models) + 0.75),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    axes = np.atleast_1d(axes)
    series = [
        ("Dense baseline", None, BASELINE_COLOR, "o"),
        ("SVE-128", 128, SVE128_COLOR, "o"),
        ("SVE-256", 256, SVE256_COLOR, "^"),
        ("SVE-512", 512, SVE512_COLOR, "s"),
    ]

    for ax, model in zip(axes, models):
        for label, bits, color, marker in series:
            if bits is None:
                mask_base = data["model"].eq(model) & data["is_dense_baseline"]
            else:
                mask_base = (
                    data["model"].eq(model)
                    & (~data["is_dense_baseline"])
                    & data["codebook_size"].eq(8)
                    & data["sve_bits"].eq(bits)
                )
            times = [
                first_metric(data, mask_base & data["n_learners"].eq(n), "execution_time")
                for n in LEARNERS
            ]
            base_time = times[0]
            if not np.isfinite(base_time) or base_time == 0:
                warn(f"Figure 5 vertical: skipping {model} {label}; no N_LEARNERS=1 runtime.")
                continue
            normalized = [value / base_time if np.isfinite(value) else np.nan for value in times]
            finite_line(
                ax,
                LEARNERS,
                normalized,
                color=color,
                marker=marker,
                markersize=3.2,
                linewidth=1.0,
                label=("Dense" if label == "Dense baseline" else f"{label} (CB=8)"),
            )

        ax.plot(
            LEARNERS,
            LEARNERS,
            color="0.35",
            linewidth=0.75,
            linestyle=(0, (3, 2)),
            label="linear",
        )
        ax.set_title(model)
        ax.set_xticks(LEARNERS)
        ax.set_xlabel("N_LEARNERS")
        ax.set_ylabel("Runtime / runtime at N=1")
        set_axes_common(ax)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.08))
    save_figure(fig, outdir, "fig5_stack_vertical_learner_scaling", dpi)



def print_best_speedup_table(data):
    subset = data[(~data["is_dense_baseline"]) & data["speedup"].notna()].copy()
    if subset.empty:
        warn("No non-dense rows with speedup available for the summary table.")
        return
    idx = subset.groupby("model")["speedup"].idxmax()
    best = subset.loc[
        idx,
        [
            "model",
            "exp_id",
            "n_learners",
            "codebook_size",
            "sve_bits",
            "speedup",
            "execution_time",
            "baseline_execution_time",
        ],
    ].copy()
    best = best.rename(
        columns={
            "n_learners": "N",
            "codebook_size": "CB",
            "sve_bits": "SVE",
            "execution_time": "time_s",
            "baseline_execution_time": "dense_time_s",
        }
    )
    best["speedup"] = best["speedup"].map(lambda value: f"{value:.3f}")
    best["time_s"] = best["time_s"].map(lambda value: f"{value:.4g}")
    best["dense_time_s"] = best["dense_time_s"].map(lambda value: f"{value:.4g}")
    print("\nBest speedup per model:")
    print(best.to_string(index=False))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate IEEE-style Transformer SVE profiling figures."
    )
    parser.add_argument(
        "--results",
        default=str(DEFAULT_RESULTS),
        help="Path to final_all_experiments.tsv or its containing directory.",
    )
    parser.add_argument(
        "--excel",
        default=None,
        help=(
            "Path to 'Transformer Experiment Settings.xlsx'. If omitted, the script "
            "searches common project locations and falls back to TSV metadata."
        ),
    )
    parser.add_argument(
        "--outdir",
        default="figures",
        help="Directory for generated PDF/SVG/PNG figures. Default: ./figures",
    )
    parser.add_argument(
        "--summary-model",
        default=None,
        help="Model to use for Figure 4. Default: the most complete N=4, CB=8 model.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=600,
        help="PNG output resolution. Default: 600.",
    )
    parser.add_argument(
        "--hatches",
        action="store_true",
        help="Add hatches for grayscale printing.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    global pd, np, mpl, plt
    pd, np, mpl, plt = import_plot_stack()
    set_ieee_style()

    results_path = resolve_results_path(args.results)
    excel_path = resolve_excel_path(args.excel, results_path)
    outdir = Path(args.outdir).expanduser()

    results = load_results(results_path)
    settings = load_excel_settings(excel_path)
    merged = merge_settings(results, settings)
    top = prepare_topline(merged)
    stage_data = prepare_stage_rows(merged)
    data = compute_derived_metrics(top)

    plot_fig1_speedup_cache_grid(data, outdir, args.dpi, args.hatches)
    plot_fig2_execution_time_cb8(data, outdir, args.dpi, args.hatches)
    plot_fig2b_execution_time_cb_sweep_speedup(data, outdir, args.dpi, args.hatches)
    plot_fig2b_stack_vertical_execution_time_cb_sweep_speedup(data, outdir, args.dpi, args.hatches)
    plot_fig2_cache_miss_overlay(
        data,
        outdir,
        args.dpi,
        args.hatches,
        "l1d_cache_misses",
        "L1D misses",
        "fig2d_execution_time_l1d_misses",
    )
    plot_fig2_cache_miss_overlay(
        data,
        outdir,
        args.dpi,
        args.hatches,
        "l1i_cache_misses",
        "L1I misses",
        "fig2e_execution_time_l1i_misses",
    )
    plot_fig2_cache_miss_overlay(
        data,
        outdir,
        args.dpi,
        args.hatches,
        "l2_cache_misses",
        "L2 misses",
        "fig2f_execution_time_l2_misses",
    )
    plot_fig2g_cache_misses_grid(data, outdir, args.dpi)
    plot_fig2g_v2_cache_misses_grid_with_dense(data, outdir, args.dpi)
    plot_fig2g_v2_split_cache_misses_by_model(data, outdir, args.dpi)
    plot_fig2g_v2_stack_vertical_cache_misses_grid_with_dense(data, outdir, args.dpi)
    plot_fig2c_execution_time_stage_breakdown(stage_data, outdir, args.dpi, args.hatches)
    plot_fig2c_stack_vertical_execution_time_stage_breakdown(stage_data, outdir, args.dpi, args.hatches)
    plot_fig3_codebook_scaling(data, outdir, args.dpi, args.hatches)
    plot_fig4_summary_runtime_cache(data, outdir, args.dpi, args.hatches, args.summary_model)
    plot_fig5_learner_scaling(data, outdir, args.dpi)
    plot_fig5_stack_vertical_learner_scaling(data, outdir, args.dpi)
    print_best_speedup_table(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
