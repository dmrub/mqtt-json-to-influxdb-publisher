#!/bin/bash

THIS_DIR=$( (cd "$(dirname -- "$BASH_SOURCE")" && pwd -P) )

cd "$THIS_DIR"

IMAGE=mqtt-json-to-influxdb-publisher

docker run -ti --rm --name="$IMAGE" --net=host "$IMAGE" \
       --debug --log-to-console "$@"
