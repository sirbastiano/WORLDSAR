#!/bin/bash

source /Data_large/SARGFM/srp/.venv/bin/activate
phidown --name $1 -o /Data_large/SARGFM/1_data -c /Data_large/SARGFM/.s5cfg
