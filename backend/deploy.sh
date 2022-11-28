#!/bin/bash

set -euxo pipefail

cwd="$(pwd)"

cd venv/lib/python*/site-packages/
zip -u -r9 "${cwd}/function.zip" * -x '__pycache__/*' || true

cd "${cwd}/src"
zip -u "${cwd}/function.zip" -r . -x '__pycache__/*' || true

cd "${cwd}"
aws s3 cp function.zip s3://dk-analyze-lambda-code/function.zip
aws lambda update-function-code --function-name dk-analyze-lambda --s3-bucket dk-analyze-lambda-code --s3-key function.zip --publish
