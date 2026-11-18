#!/bin/bash
cd /root/work/windtunnel/openfoam/airframe-sweep
export GEOM_DIR=$PWD/cad/v1/cfd_geom_multi_parallel
export SURF_LEVEL=6 FIN_LEVEL=7 BOX_LEVEL=3
echo "GEOM_DIR=$GEOM_DIR"
ls "$GEOM_DIR"/*.stl 2>/dev/null | wc -l
echo "=== make_case 手动 ==="
rm -rf /tmp/test_case
bash make_case.sh 10 -15 0 /tmp/test_case 2>&1 | tail -5
echo "rc=$?"
