#!/usr/bin/env bash
# Flatten the POS image to a single layer.
#
# patch-restaurant.dockerfile does `FROM custom-erpnext:<tag>` onto its own
# output, so every bake adds ~50 layers. Past roughly 480 the overlayfs mount
# option string exceeds the kernel's limit and EVERY build dies with
#   mount source: "overlay" ... err: no such file or directory
# on an arbitrary early step. Running containers keep working, which makes it
# look like a build-cache problem; pruning the cache does not help.
#
#   ./restaurant/flatten-image.sh [custom-erpnext:v16.6.0]

set -euo pipefail
IMAGE="${1:-custom-erpnext:v16.6.0}"
TMP="${IMAGE%%:*}:flatten-tmp"

before=$(docker inspect "$IMAGE" --format '{{len .RootFS.Layers}}')
echo "==> $IMAGE has $before layer(s)"
if [ "$before" -le 2 ]; then echo "already flat, nothing to do"; exit 0; fi

cid=$(docker create "$IMAGE")
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT

# Carry the config across — export/import keeps only the filesystem.
mapfile -t OPTS < <(docker inspect "$IMAGE" --format '{{json .Config}}' | python3 -c '
import json, sys
c = json.load(sys.stdin)
for e in c.get("Env") or []:
    print("ENV " + e)
if c.get("User"):
    print("USER " + c["User"])
if c.get("WorkingDir"):
    print("WORKDIR " + c["WorkingDir"])
if c.get("Entrypoint"):
    print("ENTRYPOINT " + json.dumps(c["Entrypoint"]))
if c.get("Cmd"):
    print("CMD " + json.dumps(c["Cmd"]))
for v in (c.get("Volumes") or {}):
    print("VOLUME " + json.dumps([v]))
')
args=()
for o in "${OPTS[@]}"; do args+=(-c "$o"); done

echo "==> exporting and re-importing as one layer (a few minutes)"
docker export "$cid" | docker import "${args[@]}" - "$TMP" >/dev/null

docker tag "$TMP" "$IMAGE"
docker rmi "$TMP" >/dev/null
echo "==> $IMAGE now has $(docker inspect "$IMAGE" --format '{{len .RootFS.Layers}}') layer(s)"
