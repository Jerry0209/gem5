# telnet localhost 3456
# ./util/term/gem5term localhost 3456
# mount -t 9p -o trans=virtio,version=9p2000.L,aname=/home/jerry/gem5/shared_folder gem5 /mnt
# mount -t 9p -o trans=virtio,version=9p2000.L,aname=/home/thu/gem5/shared_folder gem5 /mnt
# Gem5 should be re-complied after VirtIO90.py is modified

# export M5_PATH=/home/thu/gem5_resources

# 自动生成类似 20260226_173006 的时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
run_dir="output/run_${TIMESTAMP}"
stats_filename="stats_${TIMESTAMP}.txt"
config_filename="config_${TIMESTAMP}.json"

# ./build/ARM/gem5.fast -d output/run_${TIMESTAMP} configs/example/arm/starter_fs.py \
#     --kernel=../gem5_resources/vmlinux_wa \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --script=/scripts/keep_alive.sh \
#     --vio-9p=/home/jerry/gem5/shared_folder \
#     --restore=m5out/cpt.258013579250 \
#     --cpu=atomic


# ./build/ARM/gem5.fast \
#     -d "${run_dir}" \
#     --stats-file="${stats_filename}" \
#     --dump-config="${config_filename}"\
#     configs/example/arm/starter_fs.py \
#     --kernel=../gem5_resources/vmlinux_wa \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --interactive-terminal \
#     --vio-9p=/home/jerry/gem5/shared_folder \
#     --cpu=atomic

./build/ARM/gem5.fast \
    -d "${run_dir}" \
    --stats-file="${stats_filename}" \
    --dump-config="${config_filename}"\
    configs/example/arm/starter_fs.py \
    --kernel=../gem5_resources/vmlinux_wa \
    --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
    --interactive-terminal \
    --vio-9p=/home/thu/gem5/shared_folder \
    --cpu=atomic