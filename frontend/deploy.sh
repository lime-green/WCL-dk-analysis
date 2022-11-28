#!/bin/bash

set -euxo pipefail

cwd="$(pwd)"

yarn build
cd dist

aws s3 cp . s3://dk-analyze-frontend/ --recursive
aws cloudfront create-invalidation --distribution-id E1PIFMLD39KZYU --paths '/*'

cd -
rm -rf dist
