#!/usr/bin/env bash
set -euo pipefail

cd /home/jerry/gem5

export M5_PATH=/home/jerry/gem5_resources
GEM5=./build/ARM/gem5.opt
CFG=configs/example/arm/starter_fs.py
KERNEL=/home/jerry/gem5_resources/arm64-vmlinux-5.4.49
DISK=/home/jerry/gem5_resources/arm64-ubuntu-20220727.img

RUN_ID=$(date +%Y%m%d_%H%M%S)
OUT=/home/jerry/gem5/runs/base_ckpt/${RUN_ID}
mkdir -p "$OUT"

"$GEM5" -d "$OUT" --stats-file="stats_atomic_ckpt_${RUN_ID}.txt" \
  "$CFG" \
  --cpu=atomic \
  --kernel="$KERNEL" \
  --disk-image="$DISK" \
  --script="configs/boot/hack_back_ckpt.rcS" \
  --checkpoint

echo "Done. Checkpoint(s):"
ls -d "$OUT"/cpt.*
echo "Base run dir: $OUT"
