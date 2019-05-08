#!/bin/bash

THIS_DIR=$( (cd "$(dirname -- "$BASH_SOURCE")" && pwd -P) )

cd "$THIS_DIR"

docker build -t mqtt-json-to-influxdb-publisher  .
