#!/bin/bash
cd ~/Documents/JrencProjects/geolore-tools
exec > /tmp/geolore_fanhua.log 2>&1
export PYTHONUNBUFFERED=1
python scripts/run_fanhua.py
echo "EXIT_CODE: $?"
