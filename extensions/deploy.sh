#!/bin/bash

set -euxo pipefail

cwd="$(pwd)"

cd src
zip -r9 ../chrome_extension.zip content.js icon_48.png icon_128.png manifest.json

cd ..
cp chrome_extension.zip firefox_extension.zip
sed 's/"manifest_version": 3/"manifest_version": 2/' src/manifest.json > /tmp/manifest.json
sed -i '' 's/"action"/"browser_action"/' /tmp/manifest.json

cd /tmp
zip "${cwd}/firefox_extension.zip" -u manifest.json
