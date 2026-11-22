"""Generate monitoring/kibana/dashboards.ndjson: the RegulationDiff Kibana dashboard.

    python monitoring/kibana/build_dashboards.py

The panels are defined below as data so the dashboard is reviewable and versioned;
setup.sh imports the generated file. Data view id: "regulationdiff" (regulationdiff-*).
"""

import json
from pathlib import Path

DATA_VIEW = "regulationdiff"
OUT = Path(__file__).with_name("dashboards.ndjson")
INDEX_REF = "kibanaSavedObjectMeta.searchSourceJSON.index"


def count(agg_id="1"):
    return {"id": agg_id, "enabled": True, "type": "count", "schema": "metric", "params": {}}


def metric(agg_id, agg_type, field, label, **params):
    return {
        "id": agg_id,
        "enabled": True,
        "type": agg_type,
        "schema": "metric",
        "params": {"field": field, "customLabel": label, **params},
    }


def over_time(agg_id="2"):
    return {
        "id": agg_id,
        "enabled": True,
        "type": "date_histogram",
        "schema": "segment",
        "params": {"field": "@timestamp", "interval": "auto", "min_doc_count": 1, "extended_bounds": {}},
    }


def terms(agg_id, field, schema, size=10, order_by="1"):
    return {
        "id": agg_id,
        "enabled": True,
        "type": "terms",
        "schema": schema,
        "params": {"field": field, "size": size, "order": "desc", "orderBy": order_by, "otherBucket": False},
    }


def line_params(metrics: list[tuple[str, str]], axis_title: str) -> dict:
    return {
        "type": "line",
        "grid": {"categoryLines": False},
        "categoryAxes": [
            {
                "id": "CategoryAxis-1",
                "type": "category",
                "position": "bottom",
                "show": True,
                "style": {},
                "scale": {"type": "linear"},
                "labels": {"show": True, "filter": True, "truncate": 100},
                "title": {},
            }
        ],
        "valueAxes": [
            {
                "id": "ValueAxis-1",
                "name": "LeftAxis-1",
                "type": "value",
                "position": "left",
                "show": True,
                "style": {},
                "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": axis_title},
            }
        ],
        "seriesParams": [
            {
                "show": True,
                "type": "line",
                "mode": "normal",
                "data": {"label": label, "id": agg_id},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True,
                "lineWidth": 2,
                "interpolate": "linear",
                "showCircles": True,
            }
            for agg_id, label in metrics
        ],
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False,
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
        "labels": {},
    }


PIE = {
    "type": "pie",
    "addTooltip": True,
    "addLegend": True,
    "legendDisplay": "show",
    "legendPosition": "right",
    "isDonut": True,
    "labels": {"show": True, "values": True, "last_level": True, "truncate": 100},
}
TABLE = {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False, "showTotal": False}
METRIC = {
    "addTooltip": True,
    "addLegend": False,
    "type": "metric",
    "metric": {
        "percentageMode": False,
        "useRanges": False,
        "colorSchema": "Green to Red",
        "metricColorMode": "None",
        "colorsRange": [{"from": 0, "to": 100000}],
        "labels": {"show": True},
        "invertColors": False,
        "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 32},
    },
}

# (id, title, vis type, params, aggs, KQL query, grid width, grid height)
PANELS = [
    (
        "rd-requests",
        "API requests over time, by service",
        "line",
        line_params([("1", "Requests")], "Requests"),
        [count(), over_time(), terms("3", "service.keyword", "group", 5)],
        "event:http_request",
        24,
        12,
    ),
    (
        "rd-latency",
        "API latency (ms)",
        "line",
        line_params([("1", "Average"), ("3", "95th percentile")], "Milliseconds"),
        [
            metric("1", "avg", "duration_ms", "Average"),
            over_time(),
            metric("3", "percentiles", "duration_ms", "95th percentile", percents=[95]),
        ],
        "event:http_request",
        24,
        12,
    ),
    (
        "rd-errors",
        "Errors over time (5xx, failed jobs, LLM failures)",
        "line",
        line_params([("1", "Errors")], "Errors"),
        [count(), over_time(), terms("3", "event.keyword", "group", 6)],
        "outcome:error",
        24,
        12,
    ),
    (
        "rd-builds",
        "Requests served per build (deployments)",
        "table",
        TABLE,
        [count(), terms("2", "build_number.keyword", "bucket", 20)],
        "event:http_request",
        12,
        12,
    ),
    (
        "rd-jobs",
        "Worker jobs by outcome",
        "pie",
        PIE,
        [count(), terms("2", "event.keyword", "segment", 5)],
        "event:(job_done or job_failed or job_retry or job_deferred)",
        12,
        12,
    ),
    (
        "rd-changes",
        "Clause changes detected",
        "metric",
        METRIC,
        [
            metric("1", "sum", "substantially_changed", "Substantially changed"),
            metric("2", "sum", "added", "Added"),
            metric("3", "sum", "deleted", "Deleted"),
            metric("4", "sum", "modified", "Modified"),
            metric("5", "sum", "renumbered", "Renumbered"),
        ],
        "event:comparison_done",
        24,
        8,
    ),
    (
        "rd-llm",
        "LLM calls by HTTP status",
        "pie",
        PIE,
        [count(), terms("2", "status.keyword", "segment", 6)],
        "event:llm_call",
        12,
        12,
    ),
    (
        "rd-reports",
        "Impact reports: verified vs unverified",
        "pie",
        PIE,
        [count(), terms("2", "verified", "segment", 2)],
        "event:impact_report_created",
        12,
        12,
    ),
]


def visualization(vis_id, title, vis_type, params, aggs, query):
    search = {"query": {"query": query, "language": "kuery"}, "filter": [], "indexRefName": INDEX_REF}
    return {
        "type": "visualization",
        "id": vis_id,
        "attributes": {
            "title": title,
            "description": "",
            "uiStateJSON": "{}",
            "version": 1,
            "visState": json.dumps({"title": title, "type": vis_type, "params": params, "aggs": aggs}),
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(search)},
        },
        "references": [{"name": INDEX_REF, "type": "index-pattern", "id": DATA_VIEW}],
    }


def dashboard():
    panels, references, x, y, row_height = [], [], 0, 0, 0
    for index, (vis_id, *_, width, height) in enumerate(PANELS):
        if x + width > 48:
            x, y, row_height = 0, y + row_height, 0
        ref = f"panel_{index}"
        panels.append(
            {
                "panelIndex": str(index),
                "gridData": {"x": x, "y": y, "w": width, "h": height, "i": str(index)},
                "embeddableConfig": {},
                "panelRefName": ref,
                "version": "8.15.3",
            }
        )
        references.append({"name": ref, "type": "visualization", "id": vis_id})
        x, row_height = x + width, max(row_height, height)
    return {
        "type": "dashboard",
        "id": "regulationdiff-overview",
        "attributes": {
            "title": "RegulationDiff overview",
            "description": "API traffic, latency, errors, deployments, worker jobs, detected changes and LLM health.",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": True,
            "timeFrom": "now-24h",
            "timeTo": "now",
            "refreshInterval": {"pause": False, "value": 30000},
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}})},
        },
        "references": references,
    }


def main() -> None:
    objects = [visualization(*panel[:6]) for panel in PANELS] + [dashboard()]
    OUT.write_text("".join(json.dumps(obj) + "\n" for obj in objects), encoding="utf-8")
    print(f"wrote {OUT} ({len(objects)} objects)")


if __name__ == "__main__":
    main()
