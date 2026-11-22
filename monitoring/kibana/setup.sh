#!/usr/bin/env sh
# Create the Kibana data view for RegulationDiff logs and import saved dashboards.
#   KIBANA_URL=http://localhost:5601 monitoring/kibana/setup.sh
set -eu

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Waiting for Kibana at $KIBANA_URL ..."
until curl -fs "$KIBANA_URL/api/status" >/dev/null; do sleep 5; done

echo "Creating data view regulationdiff-*"
curl -fs -X POST "$KIBANA_URL/api/data_views/data_view" \
  -H "kbn-xsrf: true" -H "Content-Type: application/json" \
  -d '{"data_view":{"id":"regulationdiff","title":"regulationdiff-*","name":"RegulationDiff logs","timeFieldName":"@timestamp"},"override":true}' \
  >/dev/null

if [ -f "$DIR/dashboards.ndjson" ]; then
  echo "Importing saved dashboards"
  curl -fs -X POST "$KIBANA_URL/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" --form file=@"$DIR/dashboards.ndjson" >/dev/null
fi
echo "Kibana is ready: $KIBANA_URL/app/discover"
