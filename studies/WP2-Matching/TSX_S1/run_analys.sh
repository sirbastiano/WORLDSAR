#bin/bash
PY="/Users/roberto.delprete/Library/CloudStorage/OneDrive-ESA/Desktop/Repos/WORLDSAR/srp/.venv/bin/python"

nohup $PY 0_search_matches.py && $PY 1_build_stacks.py && $PY 2_visualize.py