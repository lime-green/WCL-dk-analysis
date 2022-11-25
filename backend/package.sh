#!/bin/bash

set -euxo pipefail

cd venv/lib/python3.9/site-packages/
zip -r9 ~/code/dk-analyze/backend/function.zip *

cd -
cd src
zip -g ../function.zip -r . -x '__pycache__/*'
