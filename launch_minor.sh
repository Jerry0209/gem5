#!/bin/bash
# From Stefano

./../build/ARM/gem5.fast \
-d /home/albini/Documents/ESL/gem5/launch_scripts/test/   \
--stats-file=$stats_filename \
--dump-config=$config_filename \
/home/albini/Documents/ESL/gem5/configs/example/arm/starter_fs.py \
--cpu="minor" \
--num-cores=1 \
--l1d_size="32kB" \
--l2_size="1MB" 
