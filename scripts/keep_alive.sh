#!/bin/bash

echo "========================================"
echo "Boot complete. Creating Checkpoint..."
echo "========================================"

# 1. 这里是关键：告诉 gem5 存盘
/sbin/m5 checkpoint

echo "========================================"
echo "Checkpoint done! Entering Interactive Shell..."
echo "========================================"

# 2. 存盘后继续进入 Shell，方便你操作
while true; do
    echo -n "gem5-user# "
    read line
    eval "$line"
done
