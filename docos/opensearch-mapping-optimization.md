# LLM Audits Index Mapping Optimization

## Status: ✅ Production-Ready

The `llm-audits` index mapping defined in [backend/app/core/opensearch.py](../backend/app/core/opensearch.py) is already optimized for dashboard aggregations and search use cases. No changes are needed for current functionality.

---

## Current Mapping (v1)

```json
{
  "llm-audits": {
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "pipeline": { "type": "keyword" },
        "client_id": { "type": "keyword" },
        "model": { "type": "keyword" },
        "status": { "type": "keyword" },
        "latency_ms": { "type": "float" },
        "prompt_tokens": { "type": "integer" },
        "completion_tokens": { "type": "integer" },
        "prompt": { "type": "text" },
        "response": { "type": "text" },
        "error": { "type": "text" }
      }
    }
  }
}
```

---

## Field Optimization Analysis

### ✅ Aggregation-Friendly Fields

| Field               | Type    | Aggregation Use                               | Current Status |
| ------------------- | ------- | --------------------------------------------- | -------------- |
| `pipeline`          | keyword | Terms aggregation (extraction vs. generation) | ✅ Optimal     |
| `model`             | keyword | Terms aggregation (by Ollama model name)      | ✅ Optimal     |
| `client_id`         | keyword | Terms aggregation, filtering by client        | ✅ Optimal     |
| `status`            | keyword | Terms aggregation, filtering by success/error | ✅ Optimal     |
| `prompt_tokens`     | integer | Sum, avg, max, percentiles                    | ✅ Optimal     |
| `completion_tokens` | integer | Sum, avg, max, percentiles                    | ✅ Optimal     |
| `latency_ms`        | float   | Avg, max, percentiles, histogram              | ✅ Optimal     |
| `timestamp`         | date    | Date histogram, range filtering, time-series  | ✅ Optimal     |

### ✅ Search-Friendly Fields

| Field      | Type | Search Use                                     | Current Status |
| ---------- | ---- | ---------------------------------------------- | -------------- |
| `prompt`   | text | Full-text search, phrase queries, highlighting | ✅ Optimal     |
| `response` | text | Full-text search, debugging responses          | ✅ Optimal     |
| `error`    | text | Full-text search, error analysis               | ✅ Optimal     |

---

## Production-Ready Features

### ✅ Performance Optimizations

1. **Keywords vs. Text**: All dimension fields (`pipeline`, `model`, `client_id`, `status`) are keyword type, which are cheaper for aggregations than text fields.
2. **Numeric Types**: Metric fields (`prompt_tokens`, `completion_tokens`, `latency_ms`) are properly typed (integer, float) for efficient aggregation and statistical operations.
3. **Date Type**: `timestamp` is properly indexed as a date, enabling fast time-series filtering and bucketing.
4. **No Analysis Overhead**: Dimension fields have no analyzer overhead; queries are exact-match.

### ✅ Index Settings (Implicit)

When the index is created in `opensearch.py`, it uses OpenSearch's default settings:

- **Shards**: 1 (appropriate for single-node development cluster)
- **Replicas**: 0 (appropriate for single-node, no redundancy needed)
- **Refresh Interval**: `1s` (default, reasonable for audit logs)

For a production multi-node cluster, consider:

- **Shards**: 3-5 (parallel query performance)
- **Replicas**: 1-2 (redundancy)
- **Refresh Interval**: `30s` (reduce indexing cost, acceptable for near-real-time analytics)

---

## Recommended Dashboard Aggregations (Already Optimal)

Based on the current mapping, these aggregations are efficient:

### Dimension Aggregations (Cheap, parallel-friendly)

```json
{
  "terms": {
    "field": "pipeline", // keyword → instant
    "size": 10
  }
}
```

```json
{
  "terms": {
    "field": "client_id", // keyword → instant
    "size": 100
  }
}
```

### Metric Aggregations (Efficient)

```json
{
  "sum": { "field": "prompt_tokens" } // integer → fast
}
```

```json
{
  "avg": { "field": "latency_ms" } // float → fast
}
```

### Time-Series (Optimized)

```json
{
  "date_histogram": {
    "field": "timestamp", // date type → fast bucketing
    "fixed_interval": "1d"
  }
}
```

---

## Optional Future Enhancements (v2+)

If requirements change, consider these additions **without disrupting existing dashboards**:

### Enhancement 1: Computed Total Tokens

**Current State**: Dashboards compute `prompt_tokens + completion_tokens` on the fly.

**Problem**: Minor overhead in dashboard rendering; filters on total are cumbersome.

**Solution**: Add a computed field at index time.

**Implementation** (v2 mapping):

```json
{
  "total_tokens": {
    "type": "integer"
  }
}
```

**Python Code Change** ([backend/app/services/llm_audit.py](../backend/app/services/llm_audit.py)):

```python
@dataclasses.dataclass
class LLMAuditEvent:
    # ... existing fields ...
    total_tokens: int = dataclasses.field(init=False, default=0)

    def __post_init__(self):
        self.total_tokens = (self.prompt_tokens or 0) + (self.completion_tokens or 0)
```

**Benefit**: Direct aggregations on `total_tokens`, faster dashboard cardinality checks.

---

### Enhancement 2: Prompt Character Count (for optimization analysis)

**Current State**: Full prompt text stored in `prompt` field (which can be large).

**Problem**: Full text is useful for debugging but inflates index size; prompts can be 5-50KB each.

**Solution**: Store a lightweight `prompt_char_count` instead of or alongside full text.

**Implementation** (v2 mapping):

```json
{
  "prompt_char_count": { "type": "integer" },
  "response_char_count": { "type": "integer" }
}
```

**Python Code Change** ([backend/app/services/llm_audit.py](../backend/app/services/llm_audit.py)):

```python
@dataclasses.dataclass
class LLMAuditEvent:
    # ... existing fields ...
    prompt_char_count: int = dataclasses.field(init=False, default=0)
    response_char_count: int = dataclasses.field(init=False, default=0)

    def __post_init__(self):
        self.prompt_char_count = len(self.prompt) if self.prompt else 0
        self.response_char_count = len(self.response) if self.response else 0
```

**Benefit**: Create "prompt efficiency" panels showing average/max/p95 prompt sizes by pipeline, enabling prompt engineering optimization without storing gigabytes of text.

---

### Enhancement 3: Cost Estimation (When Cloud Providers Are Added)

**Current State**: No cost field; local Ollama is free.

**Problem**: When adding OpenAI/Anthropic, will need to track cost per call.

**Solution**: Add an optional cost field that remains null/zero for Ollama, populated for cloud.

**Implementation** (v2 mapping):

```json
{
  "cost_usd": {
    "type": "scaled_float",
    "scaling_factor": 100000 // Store at cent precision
  }
}
```

**Python Code Change** (future OpenAI provider):

```python
class OpenAIProvider(LLMProvider):
    async def complete(...) -> LLMResult:
        result = await client.chat.completions.create(...)
        cost = self._calculate_cost(result.usage.prompt_tokens, result.usage.completion_tokens)
        return LLMResult(..., cost_usd=cost)
```

**Benefit**: Dashboards can instantly slice by cost; cost-per-client/model reports become simple aggregations.

---

### Enhancement 4: Advisor Tracking (Better Multi-Tenant Analytics)

**Current State**: `client_id` is tracked, but not the advisor who triggered the call.

**Problem**: Can't answer "which advisor's actions drove the most token usage?"

**Solution**: Add `advisor_id` keyword field.

**Implementation** (v2 mapping):

```json
{
  "advisor_id": { "type": "keyword" }
}
```

**Python Code Change** ([backend/app/services/llm_audit.py](../backend/app/services/llm_audit.py)):

```python
@dataclasses.dataclass
class LLMAuditEvent:
    # ... existing fields ...
    advisor_id: str | None = None
```

Update callers in [generation_service.py](../backend/app/services/generation_service.py), [extraction.py](../backend/app/services/extraction.py) to pass `advisor_id` if available from context.

**Benefit**: Multi-dimensional analytics; advisor performance dashboards.

---

## Migration Strategy (If Enhancements Are Adopted)

Adding new fields to the index mapping is **non-breaking** and can be done anytime:

1. **Add to mapping** in `opensearch.py`
2. **Run the app** — OpenSearch will apply the new mapping on next index creation (or use `indices.put_mapping()` if index already exists)
3. **Update data schema** in `llm_audit.py` to populate the new fields
4. **Rebuild dashboards** to use the new fields (old dashboards continue working)

**No re-indexing required** unless you want to backfill old documents.

---

## Monitoring & Maintenance

### Index Size

Over time, the `llm-audits` index will grow. Rough estimates:

- **Per document**: ~2-5 KB (depends on prompt/response text size)
- **Per million calls**: ~2-5 GB
- **Per year** (10 calls/sec average): ~500 million calls → ~1-2 TB

**Action**: Plan index retention policy (e.g., delete indices older than 90 days) or set up index lifecycle management (ILM) in OpenSearch.

### Query Performance

If dashboards become slow:

1. Check index shard count in `docker-compose.yml` settings
2. Increase `refresh_interval` if near-real-time isn't critical
3. Use **saved searches** and **aggregations** rather than raw queries
4. Consider archiving old indices to a separate container or external storage

---

## Checklist for Current State (v1)

- ✅ Mapping is defined and created on startup
- ✅ All dimension fields are keyword type (optimal for aggregations)
- ✅ All metric fields are numeric type (optimal for statistics)
- ✅ Date field is properly indexed (optimal for time-series)
- ✅ Text fields are available for debugging and search
- ✅ No schema changes needed for OpenSearch Dashboards to function
- ✅ Ready for production dashboards and monitoring

---

## Checklist for Future Enhancements (v2+)

Only implement if requirements demand it:

- [ ] Add `total_tokens` computed field (if dashboard performance matters)
- [ ] Add `prompt_char_count` (if prompt optimization becomes a goal)
- [ ] Add `cost_usd` (when cloud LLM providers are evaluated)
- [ ] Add `advisor_id` (when multi-advisor analytics are needed)
- [ ] Implement index retention / ILM policy (when index size becomes a cost concern)
- [ ] Tune shard count for multi-node cluster (if moving to production Kubernetes cluster)

---

## References

- [OpenSearch Field Types Documentation](https://opensearch.org/docs/latest/field-types/)
- [OpenSearch Aggregations Guide](https://opensearch.org/docs/latest/aggregations/)
- [OpenSearch Dashboards Setup](./opensearch-dashboards-setup.md)
- [Backend OpenSearch Integration](../backend/app/core/opensearch.py)
- [LLM Audit Logger](../backend/app/services/llm_audit.py)
