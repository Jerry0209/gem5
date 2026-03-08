#!/usr/bin/env bash
set -euo pipefail

cd /home/jerry/gem5

# Usage:
#   ./scripts/run_from_ckpt_transformer.sh [checkpoint_dir] [cpu]
# Example:
#   ./scripts/run_from_ckpt_transformer.sh /home/jerry/gem5/runs/base_ckpt/20260226_120000/cpt.123456789 minor

# Default checkpoint: latest one under runs/base_ckpt
if [[ $# -ge 1 ]]; then
  CPT_DIR="$1"
else
  CPT_DIR=$(find /home/jerry/gem5/runs/base_ckpt -type d -name 'cpt.*' | sort -V | tail -n1 || true)
fi

if [[ -z "${CPT_DIR:-}" || ! -d "${CPT_DIR:-}" ]]; then
  echo "Error: checkpoint directory not found."
  echo "Pass one explicitly, e.g."
  echo "  ./scripts/run_from_ckpt_transformer.sh /home/jerry/gem5/runs/base_ckpt/<run_id>/cpt.<tick>"
  exit 1
fi

CPU="${2:-minor}"

export M5_PATH=/home/jerry/gem5_resources
GEM5=./build/ARM/gem5.opt
CFG=configs/example/arm/starter_fs.py
KERNEL=/home/jerry/gem5_resources/arm64-vmlinux-5.4.49
DISK=/home/jerry/gem5_resources/arm64-ubuntu-20220727.img

# Default app path inside guest image. Override with env vars if needed.
# Example:
#   APP_DIR=/home/gem5/apps/tic-sat \
#   APP_BIN=./test_model_4_act_fp32_w_int8.exe \
#   APP_ARGS="0 0 0" \
#   ./scripts/run_from_ckpt_transformer.sh
APP_DIR="${APP_DIR:-/home/gem5/apps/transformer}"
APP_BIN="${APP_BIN:-./transformer_sw.aarch64}"
APP_ARGS="${APP_ARGS-}"
APP_NAME="${APP_NAME:-transformer}"

RUN_ID=$(date +%Y%m%d_%H%M%S)
OUT=/home/jerry/gem5/runs/${APP_NAME}/${RUN_ID}
mkdir -p "$OUT"

cat > "$OUT/boot_run.rcS" <<EOF
#!/bin/sh
echo "[guest] running ${APP_NAME} from checkpoint"
cd "${APP_DIR}" || { echo "missing dir: ${APP_DIR}"; /sbin/m5 exit; }
export LD_LIBRARY_PATH="\$LD_LIBRARY_PATH:/home/gem5/apps/transformer/lib:/home/gem5/apps/tic-sat/lib:/usr/lib/aarch64-linux-gnu:/lib/aarch64-linux-gnu"
if [ ! -x "${APP_BIN}" ]; then
  echo "missing executable: ${APP_DIR}/${APP_BIN}"
  /sbin/m5 fail 2
fi
"${APP_BIN}" ${APP_ARGS}
RC=\$?
echo "[guest] app exit code: \$RC"
if [ "\$RC" -ne 0 ]; then
  /sbin/m5 fail "\$RC"
fi
echo "[guest] app done"
/sbin/m5 exit
EOF
chmod +x "$OUT/boot_run.rcS"

"$GEM5" -d "$OUT" --stats-file="stats_${APP_NAME}_${CPU}_${RUN_ID}.txt" \
  "$CFG" \
  --cpu="$CPU" \
  --kernel="$KERNEL" \
  --disk-image="$DISK" \
  --restore="$CPT_DIR" \
  --script="$OUT/boot_run.rcS"

echo "Done."
echo "Checkpoint used: $CPT_DIR"
echo "Run dir: $OUT"
