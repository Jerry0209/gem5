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
# bash launch_simulation_session.sh # use screen to run the tasks in the background

# m5 exit
# /sbin/m5 exit

# ps -ef | grep gem5
# kill -9 PID
# ss -ltnp | grep 3456
# ps -ef | grep gem5.fast | grep -v grep
# grep "Listening for connections" logs/gem5_20260418_000728.log

# tail -f logs/gem5_20260412_210000.log
# screen -ls
# ~. # Disconnect from terminal but not kill it
# screen -r gem5_run_20260412_210000
# Ctrl+a -> d
# screen -S gem5_run_20260412_210000 -X quit



# Without using 9p device
# mkdir -p $HOME/gem5_disk
# fdisk -l $HOME/gem5_resources/arm64-ubuntu-20220727.img

# sudo mount -o loop,offset=105906176 \
#   $HOME/gem5_resources/arm64-ubuntu-20220727.img \
#   $HOME/gem5_disk

# sudo mkdir -p $HOME/gem5_disk/root/sve_bin
# sudo cp $HOME/TiC-SAT/test_prctl_sve $HOME/gem5_disk/root/sve_bin/
# sudo cp $HOME/TiC-SAT/transformer_boss_menu_int_noTiling_CB_8_SVE_4.o $HOME/gem5_disk/root/sve_bin/
# sudo chmod +x $HOME/gem5_disk/root/sve_bin/test_prctl_sve
# sudo chmod +x $HOME/gem5_disk/root/sve_bin/transformer_boss_menu_int_noTiling_CB_8_SVE_4.o
# sync
# sudo umount $HOME/gem5_disk




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

set -euo pipefail

# Timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
run_dir="output/run_${TIMESTAMP}"
stats_filename="stats_${TIMESTAMP}.txt"
config_filename="config_${TIMESTAMP}.json"
log_dir="logs"
session_name="gem5_run_${TIMESTAMP}"

mkdir -p "${run_dir}" "${log_dir}"

echo "Starting gem5 in screen session: ${session_name}"
echo "Run dir: ${run_dir}"

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
# ./build/ARM/gem5.fast \
#     -d "${run_dir}" \
#     --stats-file="${stats_filename}" \
#     --dump-config="${config_filename}"\
#     configs/example/arm/starter_fs.py \
#     --kernel=../gem5_resources/vmlinux_wa \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --interactive-terminal \
#     --vio-9p=/home/thu/TiC-SAT \
#     --cpu=atomic

#     --vio-9p=/home/thu/gem5/shared_folder \
#     --vio-9p=/home/thu/TiC-SAT \



# New run with new kernel
# ./build/ARM/gem5.fast \
#     -d "${run_dir}" \
#     --stats-file="${stats_filename}" \
#     --dump-config="${config_filename}"\
#     configs/example/arm/starter_fs.py \
#     --kernel=$HOME/kernel-build/linux/vmlinux \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --script=$(pwd)/scripts/drop_to_shell.rcS \
#     --vio-9p=/home/thu/TiC-SAT \
#     --cpu=atomic


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




# ./build/ARM/gem5.fast \
#     -d "${run_dir}" \
#     --stats-file="${stats_filename}" \
#     --dump-config="${config_filename}" \
#     configs/example/arm/starter_fs.py \
#     --kernel=../gem5_resources/vmlinux_wa \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --interactive-terminal \
#     --vio-9p=/home/thu/TiC-SAT \
#     --restore=/home/thu/gem5/output/run_20260404_162103/cpt.42797895763750 \
#     --cpu=atomic


# Screen
# screen -dmS "${session_name}" bash -lc "
# nice -n 0 ./build/ARM/gem5.fast \
#     -d '${run_dir}' \
#     --stats-file='${stats_filename}' \
#     --dump-config='${config_filename}' \
#     configs/example/arm/starter_fs.py \
#     --kernel=../gem5_resources/vmlinux_wa \
#     --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
#     --interactive-terminal \
#     --vio-9p=/home/thu/TiC-SAT \
#     --restore=/home/thu/gem5/output/run_20260412_195216/cpt.130181423886750 \
#     --cpu=minor \
#     > '${log_dir}/gem5_${TIMESTAMP}.log' 2>&1
# "

# echo "Started."
# echo "Screen session: ${session_name}"
# echo "Log file: ${log_dir}/gem5_${TIMESTAMP}.log"
# echo "To inspect log: tail -f ${log_dir}/gem5_${TIMESTAMP}.log"

# Screen new kernel
screen -dmS "${session_name}" bash -lc "
nice -n 0 ./build/ARM/gem5.fast \
    -d '${run_dir}' \
    --stats-file='${stats_filename}' \
    --dump-config='${config_filename}' \
    configs/example/arm/starter_fs.py \
    --kernel=$HOME/kernel-build/linux/vmlinux \
    --disk-image=../gem5_resources/arm64-ubuntu-20220727.img \
    --interactive-terminal \
    --vio-9p=/home/thu/TiC-SAT \
    --restore=/home/thu/gem5/output/run_20260423_115522/cpt.4042546229250 \
    --cpu=minor \
    > '${log_dir}/gem5_${TIMESTAMP}.log' 2>&1
"

echo "Started."
echo "Screen session: ${session_name}"
echo "Log file: ${log_dir}/gem5_${TIMESTAMP}.log"
echo "To inspect log: tail -f ${log_dir}/gem5_${TIMESTAMP}.log"

