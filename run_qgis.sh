#!/bin/bash
docker rm -f qgis-server

docker run -d \
  --name qgis-server \
  --platform linux/amd64 \
  -p 8080:80 \
  -v /Users/noellelaw/Desktop/2026-SUMMER/rewild/data/20260609:/io/data \
  -e QGIS_PROJECT_FILE=/io/data/projects.qgz \
  camptocamp/qgis-server:latest