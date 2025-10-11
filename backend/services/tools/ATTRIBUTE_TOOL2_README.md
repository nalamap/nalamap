# Attribute Tool 2 - Simplified Attribute Operations

## Overview

`attribute_tool2` is a simplified version of the original `attribute_tool` designed specifically for better usability by AI agents. It provides direct, explicit operation calls without requiring natural language interpretation.

## Key Differences from Original `attribute_tool`

### Original Tool (`attribute_tool`)
- Uses natural language query interpretation via LLM planner
- Agent provides a query like "show me countries with GDP over 100"
- Tool uses LLM to parse and plan the operation
- More complex but more flexible for unstructured queries

### New Tool (`attribute_tool2`)
- Direct, explicit operation calls
- Agent specifies exactly what operation to perform
- No LLM interpretation needed
- Faster, more predictable, easier to debug

## Supported Operations

All operations from the original tool are supported:

### 1. `list_fields`
List all fields/columns with types, null counts, and examples.

```python
attribute_tool2(
    operation="list_fields",
    target_layer_name="cities"
)
```

### 2. `summarize`
Get statistical summaries (count, mean, min, max, quartiles) for numeric fields.

```python
attribute_tool2(
    operation="summarize",
    target_layer_name="countries",
    fields=["population", "gdp"]
)
```

### 3. `unique_values`
Get unique values and their counts for a field.

```python
attribute_tool2(
    operation="unique_values",
    target_layer_name="roads",
    field="road_type",
    top_k=10  # Optional: limit to top K values
)
```

### 4. `filter_where`
Filter features using CQL-lite WHERE clause (creates new layer).

```python
attribute_tool2(
    operation="filter_where",
    target_layer_name="countries",
    where="gdp_per_capita > 50000"
)
```

Supported WHERE syntax:
- Comparisons: `=`, `!=`, `>`, `<`, `>=`, `<=`
- Logical: `AND`, `OR`, `NOT`
- Special: `IN (...)`, `IS NULL`, `IS NOT NULL`
- Parentheses for grouping

### 5. `select_fields`
Select or exclude specific columns (creates new layer).

```python
# Include specific fields
attribute_tool2(
    operation="select_fields",
    target_layer_name="places",
    include_fields=["name", "type", "population"],
    keep_geometry=True
)

# Or exclude fields
attribute_tool2(
    operation="select_fields",
    target_layer_name="data",
    exclude_fields=["internal_id", "temp_field"],
    keep_geometry=True
)
```

### 6. `sort_by`
Sort features by one or more fields (creates new layer).

```python
attribute_tool2(
    operation="sort_by",
    target_layer_name="countries",
    sort_fields=[("population", "desc"), ("name", "asc")]
)
```

### 7. `describe_dataset`
Get comprehensive dataset overview with geometry types, statistics, and suggested next steps.

```python
attribute_tool2(
    operation="describe_dataset",
    target_layer_name="biodiversity_sites"
)
```

### 8. `get_attribute_values`
Extract specific attribute values from features.

```python
attribute_tool2(
    operation="get_attribute_values",
    target_layer_name="protected_areas",
    columns=["NAME", "DESIG_ENG", "REP_AREA"],
    row_filter="WDPA_PID = '555555'"  # Optional WHERE clause
)
```

## Integration

The tool is integrated into both:
- `services/single_agent.py` - For single agent mode
- `services/default_agent_settings.py` - For default agent configuration

Both tools (`attribute_tool` and `attribute_tool2`) are available simultaneously, allowing agents to choose based on their needs.

## When to Use Which Tool

### Use `attribute_tool` (original) when:
- Agent needs to interpret user's natural language query
- Flexibility in query interpretation is desired
- User provides unstructured requests

### Use `attribute_tool2` (new) when:
- Agent knows exactly which operation to perform
- Speed and predictability are important
- Debugging and testing are priorities
- Multiple operations need to be chained programmatically

## Testing

Comprehensive test suite with 14 tests covering:
- All 8 operations
- Error handling (missing parameters, invalid fields, etc.)
- Integration workflows
- Edge cases

Run tests:
```bash
cd backend
poetry run pytest tests/test_attribute_tool2.py -v
```

## Examples

### Example 1: Explore then Filter
```python
# Step 1: List fields to understand data
result1 = attribute_tool2(
    operation="list_fields",
    target_layer_name="biodiversity_data"
)

# Step 2: Get unique categories
result2 = attribute_tool2(
    operation="unique_values",
    target_layer_name="biodiversity_data",
    field="threat_level"
)

# Step 3: Filter high-threat areas
result3 = attribute_tool2(
    operation="filter_where",
    target_layer_name="biodiversity_data",
    where="threat_level = 'Critical'"
)
```

### Example 2: Extract and Analyze
```python
# Get specific values for analysis
result = attribute_tool2(
    operation="get_attribute_values",
    target_layer_name="protected_areas",
    columns=["NAME", "AREA_KM2", "IUCN_CAT"],
    row_filter="COUNTRY = 'Tanzania'"
)
```

## Benefits

1. **Predictability**: No LLM interpretation variability
2. **Speed**: No extra LLM calls for planning
3. **Debugging**: Easier to trace and debug issues
4. **Testing**: Simpler to write and maintain tests
5. **Cost**: Fewer LLM API calls
6. **Transparency**: Clear what operation will be performed

## File Structure

```
backend/
├── services/
│   ├── tools/
│   │   ├── attribute_tools.py      # Original tool
│   │   └── attribute_tool2.py      # New simplified tool
│   ├── single_agent.py              # Single agent integration
│   └── default_agent_settings.py   # Default agent config
└── tests/
    ├── test_attribute_tools.py      # Original tool tests (46 tests)
    └── test_attribute_tool2.py      # New tool tests (14 tests)
```

## Implementation Notes

- Reuses all underlying operation functions from `attribute_tools.py`
- No code duplication for core logic
- Only implements the simplified interface layer
- Fully compatible with existing agent state management
- Supports same fuzzy field matching as original tool
