# telnet localhost 3456
# ./util/term/gem5term localhost 3456
# mount -t 9p -o trans=virtio,version=9p2000.L,aname=/home/jerry/gem5/shared_folder gem5 /mnt
# mount -t 9p -o trans=virtio,version=9p2000.L,aname=/home/thu/gem5/shared_folder gem5 /mnt
# mount -t 9p -o trans=virtio,version=9p2000.L,aname=/home/thu/TiC-SAT gem5 /mnt
# Gem5 should be re-complied after VirtIO90.py is modified

# export M5_PATH=/home/thu/gem5_resources

# Checkpoint
# /sbin/m5 checkpoint

# source launch_simulation.sh


# Run transformer.o in gem5
# mkdir -p /home/thu/gem5/shared_folder/lib
# cp /home/thu/miniforge3/envs/gem5_env/lib/gcc/aarch64-conda-linux-gnu/13.4.0/libgomp.so.1 /home/thu/gem5/shared_folder/lib/
# cp /home/thu/miniforge3/envs/gem5_env/lib/gcc/aarch64-conda-linux-gnu/13.4.0/libstdc++.so.6 /home/thu/gem5/shared_folder/lib/
# cp /home/thu/miniforge3/envs/gem5_env/lib/gcc/aarch64-conda-linux-gnu/13.4.0/libgcc_s.so.1 /home/thu/gem5/shared_folder/lib/

# mount -t 9p -o trans=virtio,version=9p2000.L,aname=/home/thu/gem5/shared_folder gem5 /mnt

# mkdir -p /home/thu/TiC-SAT
# ln -sfn /mnt/weights /home/thu/TiC-SAT/weights

# export LD_LIBRARY_PATH=/mnt/lib:$LD_LIBRARY_PATH
# cd /mnt
# ./transformer.o



# Timestamp
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


# New run
./build/ARM/gem5.fast \
    -d "${run_dir}" \
    --stats-file="${stats_filename}" \
    --dump-config="${config_filename}"\
    configs/example/arm/starter_fs.py \
    --kernel=../gem5_resources/vmlinux_wa \
    --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
    --interactive-terminal \
    --vio-9p=/home/thu/TiC-SAT
    --cpu=atomic

#     --vio-9p=/home/thu/gem5/shared_folder \
#     --vio-9p=/home/thu/TiC-SAT \


# Restore
# ./build/ARM/gem5.fast \
#     -d "${run_dir}" \
#     --stats-file="${stats_filename}" \
#     --dump-config="${config_filename}" \
#     configs/example/arm/starter_fs.py \
#     --kernel=../gem5_resources/vmlinux_wa \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --interactive-terminal \
#     --vio-9p=/home/thu/gem5/shared_folder \
#     --restore=/home/thu/gem5/output/run_20260404_154228/cpt.27256638941500 \
#     --cpu=atomic

