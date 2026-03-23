# OpenSearch Dashboards Setup Guide

## Overview

Token usage data is automatically written to the `llm-audits` OpenSearch index during every LLM call (generation and extraction pipelines). This guide explains how to set up dashboards and visualizations to inspect this data.

## Index Mapping (Already Optimized)

The `llm-audits` index mapping is defined in [backend/app/core/opensearch.py](../backend/app/core/opensearch.py#L20-L33) and is created automatically on app startup. The mapping is production-ready for aggregations:

| Field               | Type    | Purpose                                             |
| ------------------- | ------- | --------------------------------------------------- |
| `timestamp`         | date    | Time-series aggregations, filtering by date range   |
| `pipeline`          | keyword | Dimension: segment by extraction vs. generation     |
| `client_id`         | keyword | Dimension: segment by client                        |
| `model`             | keyword | Dimension: segment by model name (e.g., `llama3.2`) |
| `status`            | keyword | Dimension: segment by success/error                 |
| `latency_ms`        | float   | Metric: compute avg, max, percentiles               |
| `prompt_tokens`     | integer | Metric: sum, avg, max, percentiles                  |
| `completion_tokens` | integer | Metric: sum, avg, max, percentiles                  |
| `prompt`            | text    | Search/debug: full-text search over prompt text     |
| `response`          | text    | Search/debug: full-text search over response text   |
| `error`             | text    | Search/debug: error message details                 |

**No additional mapping changes needed.** All fields are properly typed for dashboard aggregations.

### Optional Future Enhancements

If needed in the future, consider adding:

- `prompt_char_count` (integer) — prompt size optimization analysis without storing full text
- `total_tokens` (integer) — computed field for total token consumption
- `cost_usd` (scaled_float, disabled by default) — cost estimation when cloud providers are added

---

## Dashboard Panels

Below are the recommended panels to create in OpenSearch Dashboards. Each panel uses the `llm-audits` index and performs specific aggregations.

### **Panel 1: Total Tokens Over Time (Time Series)**

**Purpose**: Track cumulative token consumption over time for capacity planning and trend analysis.

**Visualization Type**: `Time Series` (or `Line Chart`)

**Data Source**: `llm-audits`

**Metrics**:

- X-axis: `timestamp` (Date Histogram, auto interval)
- Y-axis (left): `Sum` of `prompt_tokens`
- Y-axis (left): `Sum` of `completion_tokens`
- Optional Y-axis (right): `Sum` of `prompt_tokens + completion_tokens` as total

**Filter**: `status: "success"` (excludes errors)

**Display**: Dual-line or area chart showing prompt vs. completion token burn.

---

### **Panel 2: Token Usage by Pipeline**

**Purpose**: Isolate token consumption patterns between extraction and generation workflows.

**Visualization Type**: `Pie Chart` or `Bar Chart`

**Data Source**: `llm-audits`

**Aggregations**:

- Split by: `pipeline` (Terms, order by count)
- Metric: `Sum` of `(prompt_tokens + completion_tokens)`

**Filter**: `status: "success"`

**Display**: Pie chart showing generation vs. extraction proportion, or bar chart with absolute values.

---

### **Panel 3: Token Usage by Model**

**Purpose**: Identify which models consume the most tokens (useful when testing different Ollama models or preparing for cloud provider swap).

**Visualization Type**: `Bar Chart`

**Data Source**: `llm-audits`

**Aggregations**:

- X-axis: `model` (Terms, order by `Sum of total_tokens` descending)
- Y-axis: `Sum` of `prompt_tokens`
- Y-axis: `Sum` of `completion_tokens`

**Filter**: `status: "success"`

**Display**: Horizontal or vertical bar chart showing token volume per model.

---

### **Panel 4: Average Latency by Pipeline**

**Purpose**: Track LLM response time and identify performance bottlenecks.

**Visualization Type**: `Line Chart` or `Gauge`

**Data Source**: `llm-audits`

**Aggregations**:

- X-axis: `timestamp` (Date Histogram) OR `pipeline` (Terms)
- Y-axis: `Average` of `latency_ms`

**Filter**: `status: "success"`

**Display**: Time-series showing latency trend, or static gauge for current pipeline average.

---

### **Panel 5: Token Efficiency (Tokens per Millisecond)**

**Purpose**: Measure model throughput — completion tokens generated per unit time.

**Visualization Type**: `Metric` (single value) or `Time Series`

**Data Source**: `llm-audits`

**Aggregations**:

- Metric: Custom `Metric` using `Sum of completion_tokens / Sum of latency_ms`
  - In Kibana/OpenSearch syntax: `(params.completion_gen || 0) / (params.latency_total || 1) * 1000`
- Optional Split by: `pipeline` or `model`

**Filter**: `status: "success"`

**Display**: Single metric card showing tokens/sec, or small multiples by dimension.

---

### **Panel 6: Error Rate by Pipeline**

**Purpose**: Monitor extraction/generation pipeline reliability.

**Visualization Type**: `Gauge` or `Stat`

**Data Source**: `llm-audits`

**Aggregations**:

- Numerator: `Count` where `status: "error"`
- Denominator: `Count` of all records
- Calculate: `(errors / total) * 100`

**Optional Split by**: `pipeline`, then repeat gauge for each.

**Display**: Single gauge showing error % or stacked bar showing success vs. error counts.

---

### **Panel 7: Distribution of Prompt Token Counts**

**Purpose**: Identify outliers and optimize prompt engineering.

**Visualization Type**: `Histogram` or `Box Plot`

**Data Source**: `llm-audits`

**Aggregations**:

- Histogram: `prompt_tokens` (auto bucket size or manual, e.g., 50-token buckets)
- Count: frequency per bucket

**Filter**: `status: "success"`

**Display**: Histogram showing the distribution of prompt sizes, identifying whether most prompts are small (good for context window) or if there are outliers.

---

### **Panel 8: Client Activity Overview**

**Purpose**: Identify high-volume clients and usage patterns.

**Visualization Type**: `Data Table` or `Bar Chart`

**Data Source**: `llm-audits`

**Aggregations**:

- Rows: Top 20 by `client_id` (Terms)
- Columns:
  - Unique `client_id`
  - `Count` (number of LLM calls)
  - `Sum` of `prompt_tokens`
  - `Sum` of `completion_tokens`
  - `Average` of `latency_ms`

**Filter**: `status: "success"`

**Sort**: By total tokens descending.

**Display**: Data table or horizontal bar chart, sortable.

---

## Dashboard Assembly Steps

### Step 1: Access OpenSearch Dashboards

1. Navigate to `http://localhost:5601` (or your OpenSearch Dashboards URL)
2. Log in (if authentication is enabled; otherwise, proceed directly)

### Step 2: Create a New Dashboard

1. Click **Dashboards** (left sidebar)
2. Click **Create Dashboard**
3. Name: `LLM Token Usage & Performance`
4. Click **Create**

### Step 3: Add Visualizations

For each panel above:

1. Click **Edit**
2. Click **Add panel** → **Create new** (or select existing if already created)
3. Choose visualization type (e.g., `Time Series`, `Pie Chart`)
4. Configure data source as `llm-audits` index pattern
5. Set up aggregations as specified for each panel
6. Click **Save**
7. Drag and arrange on the dashboard grid

### Step 4: Configure Time Range

1. Dashboard top-right: click the time range picker
2. Set default range (e.g., `Last 7 days`, `Last 24 hours`)
3. Enable auto-refresh if desired (e.g., every 1 minute)

### Step 5: Save and Share

1. Click **Save** (top-right)
2. Provide a description
3. Dashboard URL can be shared with team members

---

## Useful OpenSearch Queries (for debugging)

If you want to inspect the raw data or create custom panels, use the **Dev Tools** > **Console** in OpenSearch Dashboards.

### Query: Last 100 LLM calls

```json
GET llm-audits/_search
{
  "size": 100,
  "sort": [
    { "timestamp": { "order": "desc" } }
  ]
}
```

### Query: Aggregate token consumption by client (last 24h)

```json
GET llm-audits/_search
{
  "query": {
    "range": {
      "timestamp": {
        "gte": "now-24h"
      }
    }
  },
  "size": 0,
  "aggs": {
    "by_client": {
      "terms": {
        "field": "client_id",
        "size": 50
      },
      "aggs": {
        "total_prompt_tokens": { "sum": { "field": "prompt_tokens" } },
        "total_completion_tokens": { "sum": { "field": "completion_tokens" } }
      }
    }
  }
}
```

### Query: Error logs from last 6h

```json
GET llm-audits/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "status": "error" } },
        { "range": { "timestamp": { "gte": "now-6h" } } }
      ]
    }
  },
  "size": 50,
  "sort": [
    { "timestamp": { "order": "desc" } }
  ]
}
```

---

## Monitoring Recommendations

Once dashboards are live, check them regularly for:

1. **Token Spike**: Sudden increase in total tokens may indicate a prompt engineering issue or change in usage pattern
2. **High Error Rate**: Watch extraction/generation error rates; errors cost tokens without producing output
3. **Latency Degradation**: If average latency climbs, may indicate Ollama instance overload or model swap
4. **Client Outliers**: Identify clients driving the most token consumption; useful for eventual cost tracking
5. **Distribution Shifts**: If prompt tokens shift dramatically, model context window utilization may have changed

---

## Next Steps

1. **Create dashboards** using the panels defined above
2. **Set alerts** (optional) if error rate exceeds threshold (e.g., >5%)
3. **Investigate** token outliers and unusual patterns in the data table view
4. **Revisit** when token usage reporting becomes a product requirement (see issue #82)
   - At that point, decide whether to add Postgres persistence for durable analytics
   - Or continue using OpenSearch Dashboards as the primary visibility tool

---

## Related Files

- [backend/app/core/opensearch.py](../backend/app/core/opensearch.py) — Index mapping and client initialization
- [backend/app/services/llm_audit.py](../backend/app/services/llm_audit.py) — Audit event logging
- [backend/app/services/generation_service.py](../backend/app/services/generation_service.py#L146) — Generation pipeline audit calls
- [backend/app/services/extraction.py](../backend/app/services/extraction.py#L106) — Extraction pipeline audit calls
- [Issue #82](https://github.com/vikraman2212/sentiment-analyst/issues/82) — Future token usage tracking feature request
