#!/usr/bin/env python3
"""Extract final BERT profiling TSVs from curated gem5 statistics files."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path


getcontext().prec = 40


REPO_ROOT = Path("/home/thu/gem5")
DEFAULT_INPUT_ROOT = REPO_ROOT / "transformer_profiling"
DEFAULT_OUTPUT_ROOT = Path("/home/thu/TiC-SAT/transformer_profiling/final")


STAT_FILE_RE = re.compile(
    r"^(e(?P<num>\d{2}))_transformer_(?P<model>BERT_(?:mini|base))"
    r"_int8_noTiling_(?P<learners>\d)D_"
    r"(?:(?P<dense>dense_baseline)|CB_(?P<cb>\d+))"
    r"_SVE_(?P<sve>\d+)_stats_(?P<timestamp>\d{8}_\d{6})\.txt$"
)


REGIONS = [
    ("after_mha", "MHA"),
    ("after_projection", "Projection"),
    ("after_attn_addnorm", "non_GEMM_after_projection"),
    ("after_ff1", "FF1"),
    ("after_ff2", "FF2"),
    ("final_total", "non_GEMM_after_ff2"),
]


ADD_METRICS = [
    ("sim_seconds", "simSeconds", "seconds"),
    ("instructions", "simInsts", "int"),
    ("ops", "simOps", "int"),
    ("cpu_cycles", "system.cpu_cluster.cpus.numCycles", "int"),
    ("memory_references", "system.cpu_cluster.cpus.commitStats0.numMemRefs", "int"),
    ("load_instructions", "system.cpu_cluster.cpus.commitStats0.numLoadInsts", "int"),
    ("store_instructions", "system.cpu_cluster.cpus.commitStats0.numStoreInsts", "int"),
    ("dcache_demand_accesses", "system.cpu_cluster.cpus.dcache.demandAccesses::total", "int"),
    ("dcache_demand_misses", "system.cpu_cluster.cpus.dcache.demandMisses::total", "int"),
    ("icache_demand_accesses", "system.cpu_cluster.cpus.icache.demandAccesses::total", "int"),
    ("icache_demand_misses", "system.cpu_cluster.cpus.icache.demandMisses::total", "int"),
    ("l2_demand_accesses", "system.cpu_cluster.l2.demandAccesses::total", "int"),
    ("l2_demand_misses", "system.cpu_cluster.l2.demandMisses::total", "int"),
    ("committed_branches", "system.cpu_cluster.cpus.branchPred.committed_0::total", "int"),
    ("branch_mispredictions", "system.cpu_cluster.cpus.branchPred.mispredicted_0::total", "int"),
]


RATIO_SOURCES = {
    "btb_hit_ratio": "system.cpu_cluster.cpus.branchPred.BTBHitRatio",
}


OUTPUT_COLUMNS = [
    "exp_id",
    "study",
    "model",
    "d_q",
    "d_seq",
    "d_model",
    "num_head",
    "d_ff",
    "implementation",
    "n_learners",
    "codebook_size",
    "sve_bits",
    "executable",
    "gem5_timestamp",
    "stats_file",
    "row_index",
    "row_kind",
    "dump_index",
    "checkpoint",
    "interval",
    *[name for name, _, _ in ADD_METRICS],
    "ipc",
    "cpi",
    "dcache_demand_miss_rate",
    "icache_demand_miss_rate",
    "l2_demand_miss_rate",
    "branch_misprediction_rate",
    "btb_hit_ratio",
]


MANIFEST_COLUMNS = [
    "exp_id",
    "study",
    "implementation",
    "n_learners",
    "codebook_size",
    "sve_bits",
    "gem5_timestamp",
    "stats_file",
    "output_file",
    "stats_blocks",
    "rows_written",
]


@dataclass(frozen=True)
class Experiment:
    exp_id: str
    study: str
    model: str
    d_q: int
    d_seq: int
    d_model: int
    num_head: int
    d_ff: int
    implementation: str
    n_learners: int
    codebook_size: str
    sve_bits: int
    executable: str
    gem5_timestamp: str
    stats_file: str
    input_path: Path
    output_name: str
    is_dense: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def study_for(exp_num: int) -> str:
    if 1 <= exp_num <= 6:
        return "Dense baseline"
    if 7 <= exp_num <= 24:
        return "Learner scaling"
    if 25 <= exp_num <= 36:
        return "Codebook-size scaling"
    raise ValueError(f"Unsupported experiment number E{exp_num:02d}")


def model_dims(model_token: str) -> tuple[str, int, int, int, int, int]:
    if model_token == "BERT_mini":
        return ("BERT-mini", 64, 512, 256, 4, 1024)
    if model_token == "BERT_base":
        return ("BERT-base", 64, 512, 768, 12, 3072)
    raise ValueError(f"Unsupported model token {model_token}")


def slugify_study(study: str) -> str:
    return study.lower().replace("-", "_").replace(" ", "_").replace("/", "_")


def experiment_from_path(path: Path) -> Experiment:
    match = STAT_FILE_RE.match(path.name)
    if not match:
        raise ValueError(f"Unexpected stats filename: {path}")

    exp_num = int(match.group("num"))
    exp_id = f"E{exp_num:02d}"
    model_token = match.group("model")
    model, d_q, d_seq, d_model, num_head, d_ff = model_dims(model_token)
    n_learners = int(match.group("learners"))
    sve_bits = int(match.group("sve"))
    timestamp = match.group("timestamp")
    study = study_for(exp_num)
    is_dense = bool(match.group("dense"))

    if is_dense:
        codebook_size = "NA"
        implementation = "Dense naive/default"
        executable_impl = "dense" if exp_num == 1 else "dense_baseline"
    else:
        codebook_size = match.group("cb")
        implementation = "Codebook SIMD int8"
        executable_impl = f"CB_{codebook_size}"

    executable = (
        f"transformer_{model_token}_int8_noTiling_{n_learners}D_"
        f"{executable_impl}_SVE_{sve_bits}.o"
    )
    gem5_timestamp = f"run_{timestamp}"
    stats_file = f"/home/thu/gem5/output/{gem5_timestamp}/stats_{timestamp}.txt"
    output_name = (
        f"e{exp_num:02d}_{slugify_study(study)}_n{n_learners}_"
        f"cb{codebook_size}_sve{sve_bits}_{gem5_timestamp}.tsv"
    )

    return Experiment(
        exp_id=exp_id,
        study=study,
        model=model,
        d_q=d_q,
        d_seq=d_seq,
        d_model=d_model,
        num_head=num_head,
        d_ff=d_ff,
        implementation=implementation,
        n_learners=n_learners,
        codebook_size=codebook_size,
        sve_bits=sve_bits,
        executable=executable,
        gem5_timestamp=gem5_timestamp,
        stats_file=stats_file,
        input_path=path,
        output_name=output_name,
        is_dense=is_dense,
    )


def parse_stats_blocks(path: Path) -> list[dict[str, Decimal]]:
    blocks: list[dict[str, Decimal]] = []
    current: dict[str, Decimal] | None = None

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "Begin Simulation Statistics" in line:
                current = {}
                continue
            if "End Simulation Statistics" in line:
                if current is None:
                    raise ValueError(f"End marker before begin marker in {path}")
                blocks.append(current)
                current = None
                continue
            if current is None:
                continue

            stat_text = line.split("#", 1)[0].strip()
            if not stat_text:
                continue
            parts = stat_text.split()
            if len(parts) < 2:
                continue
            try:
                current[parts[0]] = Decimal(parts[1])
            except Exception:
                continue

    if current is not None:
        raise ValueError(f"Unclosed stats block in {path}")
    return blocks


def value(block: dict[str, Decimal], stat_name: str) -> Decimal:
    try:
        return block[stat_name]
    except KeyError as exc:
        raise KeyError(f"Missing stat {stat_name}") from exc


def zero_block() -> dict[str, Decimal]:
    names = [source for _, source, _ in ADD_METRICS] + list(RATIO_SOURCES.values())
    return {name: Decimal(0) for name in names}


def delta_metrics(
    current: dict[str, Decimal], previous: dict[str, Decimal]
) -> dict[str, Decimal]:
    return {
        column: value(current, source) - value(previous, source)
        for column, source, _ in ADD_METRICS
    }


def add_metric_maps(
    left: dict[str, Decimal], right: dict[str, Decimal]
) -> dict[str, Decimal]:
    return {column: left.get(column, Decimal(0)) + right.get(column, Decimal(0)) for column, _, _ in ADD_METRICS}


def multiply_metric_map(metrics: dict[str, Decimal], factor: int) -> dict[str, Decimal]:
    return {column: metrics[column] * factor for column, _, _ in ADD_METRICS}


def aggregate_intervals(
    exp: Experiment, blocks: list[dict[str, Decimal]]
) -> tuple[list[dict[str, Decimal]], dict[str, Decimal], dict[str, Decimal]]:
    if len(blocks) < 6:
        raise ValueError(f"{exp.input_path} has only {len(blocks)} stats blocks")

    partial_scaled_dense = exp.exp_id in {"E05", "E06"}
    dense_multi_complete = exp.is_dense and exp.n_learners > 1 and not partial_scaled_dense

    if dense_multi_complete:
        expected = exp.n_learners * 6
        if len(blocks) < expected:
            raise ValueError(
                f"{exp.input_path} has {len(blocks)} blocks; expected {expected}"
            )
        intervals = [dict((column, Decimal(0)) for column, _, _ in ADD_METRICS) for _ in REGIONS]
        previous = zero_block()
        for block_index, current in enumerate(blocks[:expected]):
            region_index = block_index % len(REGIONS)
            intervals[region_index] = add_metric_maps(
                intervals[region_index], delta_metrics(current, previous)
            )
            previous = current
        final_metrics = dict(intervals[0])
        for interval_metrics in intervals[1:]:
            final_metrics = add_metric_maps(final_metrics, interval_metrics)
        final_ratio_source = blocks[expected - 1]
        return intervals, final_metrics, final_ratio_source

    intervals = []
    previous = zero_block()
    for current in blocks[:6]:
        intervals.append(delta_metrics(current, previous))
        previous = current

    if partial_scaled_dense:
        intervals = [multiply_metric_map(metrics, exp.n_learners) for metrics in intervals]
        final_metrics = dict(intervals[0])
        for interval_metrics in intervals[1:]:
            final_metrics = add_metric_maps(final_metrics, interval_metrics)
        return intervals, final_metrics, blocks[5]

    final_metrics = {column: value(blocks[5], source) for column, source, _ in ADD_METRICS}
    return intervals, final_metrics, blocks[5]


def fmt_metric(column: str, metric_type: str, metrics: dict[str, Decimal]) -> str:
    number = metrics[column]
    if metric_type == "seconds":
        return format(number.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), "f")
    return str(int(number))


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal(0)
    return numerator / denominator


def fmt_ratio(value_: Decimal, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    return format(value_.quantize(quantum, rounding=ROUND_HALF_UP), "f")


def base_row(exp: Experiment, row_index: int, row_kind: str, dump_index: int) -> dict[str, str]:
    checkpoint, interval = REGIONS[dump_index - 1]
    return {
        "exp_id": exp.exp_id,
        "study": exp.study,
        "model": exp.model,
        "d_q": str(exp.d_q),
        "d_seq": str(exp.d_seq),
        "d_model": str(exp.d_model),
        "num_head": str(exp.num_head),
        "d_ff": str(exp.d_ff),
        "implementation": exp.implementation,
        "n_learners": str(exp.n_learners),
        "codebook_size": exp.codebook_size,
        "sve_bits": str(exp.sve_bits),
        "executable": exp.executable,
        "gem5_timestamp": exp.gem5_timestamp,
        "stats_file": exp.stats_file,
        "row_index": str(row_index),
        "row_kind": row_kind,
        "dump_index": str(dump_index),
        "checkpoint": checkpoint,
        "interval": interval,
    }


def build_rows(exp: Experiment, blocks: list[dict[str, Decimal]]) -> list[dict[str, str]]:
    intervals, final_metrics, final_ratio_source = aggregate_intervals(exp, blocks)
    rows: list[dict[str, str]] = []

    for index, interval_metrics in enumerate(intervals, start=1):
        row = base_row(exp, index, "interval_delta", index)
        for column, _, metric_type in ADD_METRICS:
            row[column] = fmt_metric(column, metric_type, interval_metrics)
        for column in OUTPUT_COLUMNS:
            row.setdefault(column, "")
        rows.append(row)

    total_row = base_row(exp, len(REGIONS) + 1, "final_total", len(REGIONS))
    total_row["interval"] = "total_program"
    for column, _, metric_type in ADD_METRICS:
        total_row[column] = fmt_metric(column, metric_type, final_metrics)

    total_row["ipc"] = fmt_ratio(
        ratio(final_metrics["instructions"], final_metrics["cpu_cycles"]), 6
    )
    total_row["cpi"] = fmt_ratio(
        ratio(final_metrics["cpu_cycles"], final_metrics["instructions"]), 6
    )
    total_row["dcache_demand_miss_rate"] = fmt_ratio(
        ratio(final_metrics["dcache_demand_misses"], final_metrics["dcache_demand_accesses"]),
        12,
    )
    total_row["icache_demand_miss_rate"] = fmt_ratio(
        ratio(final_metrics["icache_demand_misses"], final_metrics["icache_demand_accesses"]),
        12,
    )
    total_row["l2_demand_miss_rate"] = fmt_ratio(
        ratio(final_metrics["l2_demand_misses"], final_metrics["l2_demand_accesses"]), 12
    )
    total_row["branch_misprediction_rate"] = fmt_ratio(
        ratio(final_metrics["branch_mispredictions"], final_metrics["committed_branches"]),
        12,
    )
    total_row["btb_hit_ratio"] = fmt_ratio(
        value(final_ratio_source, RATIO_SOURCES["btb_hit_ratio"]), 6
    )
    for column in OUTPUT_COLUMNS:
        total_row.setdefault(column, "")
    rows.append(total_row)

    return rows


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def discover_experiments(input_root: Path) -> list[Experiment]:
    paths = [
        *sorted((input_root / "BERT_mini").glob("e*_stats_*.txt")),
        *sorted((input_root / "BERT_base").glob("e*_stats_*.txt")),
    ]
    experiments = [experiment_from_path(path) for path in paths]
    return sorted(experiments, key=lambda exp: exp.exp_id)


def write_metric_sources(output_root: Path) -> None:
    rows = [
        {
            "column": column,
            "source": source,
            "handling": (
                "interval rows use current cumulative dump minus previous cumulative dump; "
                "dense multi-learner baselines sum matching stages across learner chunks; "
                "BERT-base E05/E06 use the first learner chunk multiplied by n_learners; "
                "final_total uses the aggregate cumulative/additive total"
            ),
        }
        for column, source, _ in ADD_METRICS
    ]
    rows.extend(
        [
            {
                "column": "ipc",
                "source": "instructions / cpu_cycles from final_total row",
                "handling": "final_total only; interval rows blank",
            },
            {
                "column": "cpi",
                "source": "cpu_cycles / instructions from final_total row",
                "handling": "final_total only; interval rows blank",
            },
            {
                "column": "dcache_demand_miss_rate",
                "source": "dcache_demand_misses / dcache_demand_accesses from final_total row",
                "handling": "final_total only; interval rows blank",
            },
            {
                "column": "icache_demand_miss_rate",
                "source": "icache_demand_misses / icache_demand_accesses from final_total row",
                "handling": "final_total only; interval rows blank",
            },
            {
                "column": "l2_demand_miss_rate",
                "source": "l2_demand_misses / l2_demand_accesses from final_total row",
                "handling": "final_total only; interval rows blank",
            },
            {
                "column": "branch_misprediction_rate",
                "source": "branch_mispredictions / committed_branches from final_total row",
                "handling": "final_total only; interval rows blank",
            },
            {
                "column": "btb_hit_ratio",
                "source": RATIO_SOURCES["btb_hit_ratio"],
                "handling": "final_total only; interval rows blank",
            },
        ]
    )
    write_tsv(output_root / "metric_sources.tsv", ["column", "source", "handling"], rows)


def write_readme(output_root: Path) -> None:
    readme = """# Final BERT profiling TSVs

This directory contains the E01-E36 profiling extraction for BERT-mini and BERT-base.

Each per-experiment TSV has seven rows: six `interval_delta` rows and one `final_total` row. The interval rows use the same stage separation as `base_mini`: `MHA`, `Projection`, `non_GEMM_after_projection`, `FF1`, `FF2`, and `non_GEMM_after_ff2`.

For normal six-dump files, each interval is the current cumulative gem5 dump minus the previous cumulative dump. Complete dense multi-learner baseline files are aggregated by summing the same stage across each six-dump learner chunk. BERT-base E05 and E06 had only ten dumps available, so their first completed learner chunk was multiplied by `n_learners` to estimate the whole dense baseline run.

The curated inputs were read from `/home/thu/gem5/transformer_profiling/BERT_mini` and `/home/thu/gem5/transformer_profiling/BERT_base`. The `stats_file` column keeps the prior `base_mini` convention of recording the corresponding `/home/thu/gem5/output/run_.../stats_...txt` path.

Use `final_all_experiments.tsv` for a combined table, or the `E*.tsv` files for per-experiment analysis. See `metric_sources.tsv` for source stat names.
"""
    (output_root / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    experiments = discover_experiments(args.input_root)
    if [exp.exp_id for exp in experiments] != [f"E{i:02d}" for i in range(1, 37)]:
        found = ", ".join(exp.exp_id for exp in experiments)
        raise ValueError(f"Expected E01-E36, found: {found}")

    all_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []

    for exp in experiments:
        blocks = parse_stats_blocks(exp.input_path)
        rows = build_rows(exp, blocks)
        output_path = output_root / exp.output_name
        write_tsv(output_path, OUTPUT_COLUMNS, rows)
        all_rows.extend(rows)
        manifest_rows.append(
            {
                "exp_id": exp.exp_id,
                "study": exp.study,
                "implementation": exp.implementation,
                "n_learners": str(exp.n_learners),
                "codebook_size": exp.codebook_size,
                "sve_bits": str(exp.sve_bits),
                "gem5_timestamp": exp.gem5_timestamp,
                "stats_file": exp.stats_file,
                "output_file": str(output_path),
                "stats_blocks": str(len(blocks)),
                "rows_written": str(len(rows)),
            }
        )

    write_tsv(output_root / "final_all_experiments.tsv", OUTPUT_COLUMNS, all_rows)
    write_tsv(output_root / "manifest.tsv", MANIFEST_COLUMNS, manifest_rows)
    write_metric_sources(output_root)
    write_readme(output_root)

    print(f"Wrote {len(experiments)} experiments and {len(all_rows)} rows to {output_root}")


if __name__ == "__main__":
    main()
