#!/bin/bash

set -euxo pipefail

cwd="$(pwd)"

cd src
zip -r9 ../chrome_extension.zip .
