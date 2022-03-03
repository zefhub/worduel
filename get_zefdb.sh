#!/bin/bash

# Black magic to extract access token and then get asset id from github
# Steps:
# 1. Get GH_ACCESS_TOKEN from the secret passed in as the gitcredentials (this is not stored past this RUN command)
# 2. Scrap the github release to find the asset with "zefdb-" and "cp38" in its name (i.e. with julia and python 3.8).
# 3. Grab the file itself

if [ "$#" -ne 3 ] ; then
    echo "Need three arguments, the repo, the tag and the asset filter, zefDB v0.12.26 e.g. zefdb-.*cp38"
    exit 1
fi

REPO="$1"
ZEFDB_TAG="$2"
ASSET_FILTER="$3"

set -o pipefail
GH_ACCESS_TOKEN=$(cat /run/secrets/gitcredentials | sed -e 's_^https://.*:\(.*\)@.*$_\1_') || exit 1

DETAILS="$(curl "https://${GH_ACCESS_TOKEN}:@api.github.com/repos/synchronoustechnologies/$REPO/releases/tags/$ZEFDB_TAG" | jq ".assets | map(select(.name | test(\"$ASSET_FILTER\")))[0]")" || exit 1
ASSET_ID=$(echo $DETAILS | jq ".id") || exit 1
FILENAME=$(echo $DETAILS | jq ".name" | tr -d \") || exit 1

curl -L -o $FILENAME -H 'Accept: application/octet-stream' "https://${GH_ACCESS_TOKEN}:@api.github.com/repos/synchronoustechnologies/$REPO/releases/assets/${ASSET_ID}" || exit 1

if [[ "$FILENAME" == "null" ]] ; then
    exit 1
fi
pip3 install --no-cache-dir $FILENAME
