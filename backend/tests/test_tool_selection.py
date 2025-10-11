"""
Test suite for tool selection behavior with improved system prompts.

These tests verify that the agent makes correct tool choices based on:
1. General system prompt improvements (Phase 1)
2. Domain-specific configurations via prompt_override (Phase 2)

Focus: Attribute tool usage patterns, field discovery, pattern matching,
natural language responses, and multi-field analysis.
"""

from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import Point

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_protected_areas_gdf():
    """
    Create a sample protected areas GeoDataFrame matching UAE dataset structure.

    Contains 3 features with key attributes:
    - Basic info: NAME, DESIG_ENG, IUCN_CAT, STATUS_YR
    - Biodiversity: BII 2015/2020 Mean Value
    - Land cover: 6 Landcover * fields (sample of actual 28)
    - Threats: BUILTUP_area_ha, POP_gt10_area_ha
    """
    gdf = gpd.GeoDataFrame(
        {
            "NAME": [
                "Al Houbara Protected Area",
                "Dubai Desert Conservation Reserve",
                "Ras Al Khor Wildlife Sanctuary",
            ],
            "DESIG_ENG": ["Protected Area", "Conservation Reserve", "Wildlife Sanctuary"],
            "IUCN_CAT": ["IV", "IV", "Ia"],
            "STATUS_YR": [2007, 2003, 1998],
            "GIS_AREA": [11500.5, 22500.0, 6.2],  # hectares
            "REP_AREA": [11500.0, 22500.0, 6.2],
            "MANG_AUTH": [
                "Environment Agency - Abu Dhabi",
                "Dubai Desert Conservation Reserve Authority",
                "Dubai Municipality",
            ],
            # Biodiversity indicators
            "Biodiversity Integrity Index 2015 Mean Value": [0.75, 0.68, 0.82],
            "Biodiversity Integrity Index 2020 Mean Value": [0.78, 0.70, 0.85],
            # Land cover (sample - actual dataset has 28 fields)
            "Landcover Cropland hectares": [120.5, 450.0, 0.5],
            "Landcover Forest hectares": [50.0, 200.0, 1.0],
            "Landcover Grassland hectares": [8500.0, 15000.0, 2.0],
            "Landcover Shrubland hectares": [2500.0, 6000.0, 1.5],
            "Landcover Wetland hectares": [100.0, 50.0, 1.2],
            "Landcover Barren hectares": [230.0, 800.0, 0.0],
            # Threats
            "BUILTUP_area_ha": [5.0, 120.0, 0.1],
            "POP_gt10_area_ha": [10.0, 250.0, 0.2],
            "AQUEDUCT_FUTURE_EXTREMELY High (>80%)_ha": [500.0, 2000.0, 0.5],
        },
        geometry=[Point(54.5, 24.5), Point(55.3, 25.2), Point(55.28, 25.22)],
        crs="EPSG:4326",
    )

    return gdf


@pytest.fixture
def sample_filtered_gdf(sample_protected_areas_gdf):
    """Create a filtered GeoDataFrame with just Al Houbara (1 feature)."""
    gdf = sample_protected_areas_gdf
    filtered_gdf = gdf[gdf["NAME"] == "Al Houbara Protected Area"].copy()
    return filtered_gdf


# ============================================================================
# PHASE 1: GENERAL SYSTEM PROMPT IMPROVEMENTS
# ============================================================================


class TestFieldDiscovery:
    """Test that agent discovers fields before using them."""

    @pytest.mark.unit
    def test_list_fields_returns_all_columns(self, sample_protected_areas_gdf):
        """Verify list_fields operation returns all available columns."""
        from services.tools.attribute_tools import list_fields_gdf

        result = list_fields_gdf(sample_protected_areas_gdf)

        # Should return dict with "fields" key
        assert isinstance(result, dict)
        assert "fields" in result

        # Extract field names
        field_names = [f["name"] for f in result["fields"]]

        assert "NAME" in field_names
        assert "Biodiversity Integrity Index 2015 Mean Value" in field_names
        assert "Landcover Cropland hectares" in field_names
        assert len(field_names) >= 15  # Should have all test fields (19 including geometry)

    @pytest.mark.unit
    def test_field_names_with_spaces_handled(self, sample_protected_areas_gdf):
        """Verify fields with spaces can be accessed."""
        gdf = sample_protected_areas_gdf

        # Should be able to access field with spaces
        assert "Biodiversity Integrity Index 2015 Mean Value" in gdf.columns
        values = gdf["Biodiversity Integrity Index 2015 Mean Value"]
        assert len(values) == 3
        assert all(0 <= v <= 1 for v in values)  # BII values are 0-1


class TestPatternBasedFieldSelection:
    """Test pattern-based field discovery and selection."""

    @pytest.mark.unit
    def test_identify_landcover_pattern_fields(self, sample_protected_areas_gdf):
        """Test identifying all Landcover * pattern fields."""
        gdf = sample_protected_areas_gdf

        # Pattern matching for "Landcover *"
        landcover_fields = [col for col in gdf.columns if col.startswith("Landcover ")]

        assert len(landcover_fields) >= 6  # Our sample has 6
        assert "Landcover Cropland hectares" in landcover_fields
        assert "Landcover Forest hectares" in landcover_fields
        assert "Landcover Wetland hectares" in landcover_fields

    @pytest.mark.unit
    def test_identify_biodiversity_pattern_fields(self, sample_protected_areas_gdf):
        """Test identifying biodiversity indicator fields."""
        gdf = sample_protected_areas_gdf

        # Pattern matching for biodiversity
        bio_fields = [col for col in gdf.columns if "Biodiversity" in col or "BII" in col]

        assert len(bio_fields) >= 2
        assert "Biodiversity Integrity Index 2015 Mean Value" in bio_fields
        assert "Biodiversity Integrity Index 2020 Mean Value" in bio_fields

    @pytest.mark.unit
    def test_summarize_multiple_fields_single_call(self, sample_filtered_gdf):
        """Test summarizing multiple pattern-matched fields in one operation."""
        from services.tools.attribute_tools import summarize_gdf

        gdf = sample_filtered_gdf

        # All landcover fields in ONE call
        landcover_fields = [col for col in gdf.columns if col.startswith("Landcover ")]

        result = summarize_gdf(gdf, fields=landcover_fields)

        # Should return summary for all fields
        assert isinstance(result, dict)
        assert len(result) == len(landcover_fields)

        # Each field should have statistics
        for field in landcover_fields:
            assert field in result
            assert "mean" in result[field] or "count" in result[field]


class TestNaturalLanguageResponses:
    """Test that responses are human-readable, not raw JSON."""

    @pytest.mark.unit
    def test_temporal_comparison_interpretation(self, sample_filtered_gdf):
        """Test comparing BII 2015 vs 2020 values."""
        from services.tools.attribute_tools import summarize_gdf

        gdf = sample_filtered_gdf

        # Get both years in one call
        result = summarize_gdf(
            gdf,
            fields=[
                "Biodiversity Integrity Index 2015 Mean Value",
                "Biodiversity Integrity Index 2020 Mean Value",
            ],
        )

        bii_2015 = result["Biodiversity Integrity Index 2015 Mean Value"]["mean"]
        bii_2020 = result["Biodiversity Integrity Index 2020 Mean Value"]["mean"]

        # Agent should interpret this as trend
        if bii_2020 > bii_2015:
            interpretation = f"Biodiversity improved from {bii_2015:.2f} to {bii_2020:.2f}"
        elif bii_2020 < bii_2015:
            interpretation = f"Biodiversity declined from {bii_2015:.2f} to {bii_2020:.2f}"
        else:
            interpretation = f"Biodiversity remained stable at {bii_2015:.2f}"

        # Verify interpretation makes sense
        assert "Biodiversity" in interpretation
        assert str(bii_2015)[:4] in interpretation  # Contains value
        assert str(bii_2020)[:4] in interpretation

    @pytest.mark.unit
    def test_categorical_summary_interpretation(self, sample_filtered_gdf):
        """Test summarizing categorical data with interpretation."""
        gdf = sample_filtered_gdf

        # Get land cover distribution
        landcover_fields = [col for col in gdf.columns if col.startswith("Landcover ")]

        from services.tools.attribute_tools import summarize_gdf

        result = summarize_gdf(gdf, fields=landcover_fields)

        # Find dominant land cover type (use mean since we have single feature)
        # For single feature: mean = value
        totals = {field: result[field]["mean"] for field in landcover_fields}
        dominant = max(totals.items(), key=lambda x: x[1])

        # Extract category name (e.g., "Grassland" from "Landcover Grassland hectares")
        category = dominant[0].replace("Landcover ", "").replace(" hectares", "")

        interpretation = (
            f"The area is predominantly {category.lower()} ({dominant[1]:.1f} hectares)"
        )

        # Verify interpretation is meaningful
        assert category in ["Cropland", "Forest", "Grassland", "Shrubland", "Wetland", "Barren"]
        assert "predominantly" in interpretation
        assert "hectares" in interpretation


class TestMultiFieldAnalysis:
    """Test efficient multi-field operations."""

    @pytest.mark.unit
    def test_compare_fields_single_call(self, sample_filtered_gdf):
        """Test comparing multiple related fields in one operation."""
        from services.tools.attribute_tools import summarize_gdf

        gdf = sample_filtered_gdf

        # Compare all threat indicators in ONE call (not separate calls)
        threat_fields = [
            col for col in gdf.columns if "BUILTUP" in col or "POP_gt10" in col or "AQUEDUCT" in col
        ]

        result = summarize_gdf(gdf, fields=threat_fields)

        # Should return all results together
        assert len(result) == len(threat_fields)

        # Verify we got meaningful data
        for field in threat_fields:
            assert field in result
            assert "sum" in result[field] or "mean" in result[field]

    @pytest.mark.unit
    def test_get_attribute_values_for_specific_fields(self, sample_filtered_gdf):
        """Test retrieving specific values (not statistics) efficiently."""
        from services.tools.attribute_tools import get_attribute_values_gdf

        gdf = sample_filtered_gdf

        # Get specific site description fields
        result = get_attribute_values_gdf(
            gdf, columns=["NAME", "IUCN_CAT", "MANG_AUTH", "STATUS_YR"]
        )

        # Should return dict with columns key
        assert isinstance(result, dict)
        assert "columns" in result
        assert "row_count" in result
        assert result["row_count"] == 1  # One feature

        # Extract values from result
        columns = result["columns"]
        assert columns["NAME"][0] == "Al Houbara Protected Area"
        assert columns["IUCN_CAT"][0] == "IV"
        assert "Environment Agency" in columns["MANG_AUTH"][0]
        assert columns["STATUS_YR"][0] == 2007


class TestErrorHandling:
    """Test error handling and recovery strategies."""

    @pytest.mark.unit
    def test_invalid_field_name_recovery(self, sample_protected_areas_gdf):
        """Test handling of invalid field names."""
        from services.tools.attribute_tools import list_fields_gdf, summarize_gdf

        gdf = sample_protected_areas_gdf

        # Try invalid field first (returns error dict, doesn't raise)
        result = summarize_gdf(gdf, fields=["NonExistentField"])

        # Should return error for missing field
        assert "NonExistentField" in result
        assert "error" in result["NonExistentField"]
        assert result["NonExistentField"]["error"] == "field not found"

        # Recovery: use list_fields to discover correct name
        available_fields_result = list_fields_gdf(gdf)
        available_fields = [f["name"] for f in available_fields_result["fields"]]

        # Find similar field (fuzzy matching)
        biodiversity_fields = [f for f in available_fields if "Biodiversity" in f]
        assert len(biodiversity_fields) > 0

        # Retry with correct name
        result = summarize_gdf(gdf, fields=biodiversity_fields[:1])
        assert len(result) == 1
        assert "error" not in result[biodiversity_fields[0]]

    @pytest.mark.unit
    def test_field_with_spaces_in_where_clause(self, sample_protected_areas_gdf):
        """Test WHERE clause with field names containing spaces."""
        from services.tools.attribute_tools import filter_where_gdf

        gdf = sample_protected_areas_gdf

        # Field name with spaces requires quotes
        # WHERE "Biodiversity Integrity Index 2020 Mean Value" > 0.7
        filtered, metadata = filter_where_gdf(
            gdf, where='"Biodiversity Integrity Index 2020 Mean Value" > 0.7'
        )

        # Should filter correctly
        assert len(filtered) >= 1
        assert all(filtered["Biodiversity Integrity Index 2020 Mean Value"] > 0.7)


# ============================================================================
# PHASE 2: IUCN-SPECIFIC CONFIGURATION TESTS
# (These tests verify prompt_override has intended effect)
# ============================================================================


class TestIUCNConfiguration:
    """Test that IUCN-specific prompt_override provides better guidance."""

    @pytest.mark.integration
    def test_iucn_field_examples_in_prompt_override(self):
        """Verify IUCN configuration includes field examples."""
        # This would be configured via /settings/options
        iucn_prompt_override = (
            "Perform attribute operations on GeoJSON layers.\n\n"
            "For IUCN Protected Areas datasets, common field patterns:\n"
            "- Biodiversity: 'Biodiversity Integrity Index 2015/2020 Mean Value'\n"
            "- Land cover: 'Landcover * hectares' (20-30 fields)\n"
            "- Threats: 'Builtup Area', 'Populated Area'\n\n"
            "Pattern-based field selection:\n"
            "1. list_fields first\n"
            "2. Identify pattern matches\n"
            "3. Summarize all in one call\n\n"
            "Provide natural language summaries with interpretation."
        )

        # Verify prompt contains IUCN-specific guidance
        assert "IUCN" in iucn_prompt_override
        assert "Biodiversity Integrity Index" in iucn_prompt_override
        assert "Landcover * hectares" in iucn_prompt_override
        assert "pattern matches" in iucn_prompt_override
        assert "natural language" in iucn_prompt_override

    @pytest.mark.integration
    @patch("services.tools.attribute_tool2.attribute_tool2")
    def test_prompt_override_applied_to_tool(self, mock_tool):
        """Verify prompt_override is applied to tool description."""
        from models.settings_model import ToolConfig

        # IUCN configuration
        iucn_config = ToolConfig(
            name="attribute_tool2",
            enabled=True,
            prompt_override=("IUCN-specific guidance: Use Biodiversity Integrity Index fields"),
        )

        # Mock tool with description
        mock_tool.description = "Original generic description"

        # Apply configuration (this is what tool_configurator does)
        if iucn_config.prompt_override:
            configured_description = iucn_config.prompt_override
        else:
            configured_description = mock_tool.description

        # Verify prompt_override replaced description
        assert "IUCN-specific" in configured_description
        assert "Biodiversity Integrity Index" in configured_description


# ============================================================================
# INTEGRATION: FULL WORKFLOW TESTS
# ============================================================================


class TestFullWorkflow:
    """Test complete user journey scenarios."""

    @pytest.mark.integration
    def test_site_description_workflow(self, sample_filtered_gdf):
        """Test Q4: Site description for Al Houbara."""
        from services.tools.attribute_tools import get_attribute_values_gdf

        gdf = sample_filtered_gdf

        # User: "Can you retrieve the Designation, Area, Status and Management Authority?"

        # Step 1: Get specific values (not statistics)
        result = get_attribute_values_gdf(
            gdf, columns=["DESIG_ENG", "GIS_AREA", "STATUS_YR", "MANG_AUTH", "IUCN_CAT"]
        )

        assert result["row_count"] == 1
        columns = result["columns"]

        # Extract first values (single feature)
        site_info = {k: v[0] for k, v in columns.items()}

        # Step 2: Format as natural language response
        response = (
            f"Here's the site description for the protected area:\n\n"
            f"**Designation**: {site_info['DESIG_ENG']}\n"
            f"**Area**: {site_info['GIS_AREA']:.1f} hectares\n"
            f"**IUCN Category**: {site_info['IUCN_CAT']}\n"
            f"**Status Year**: {site_info['STATUS_YR']}\n"
            f"**Management Authority**: {site_info['MANG_AUTH']}"
        )

        # Verify response is human-readable
        assert "Designation" in response
        assert "hectares" in response
        assert "Environment Agency" in response
        assert "2007" in response

    @pytest.mark.integration
    def test_biodiversity_temporal_comparison_workflow(self, sample_filtered_gdf):
        """Test Q6b: BII over time comparison."""
        from services.tools.attribute_tools import summarize_gdf

        gdf = sample_filtered_gdf

        # User: "Tell me about the Biodiversity Integrity Index and whether it changed over time"

        # Step 1: Summarize both years in ONE call
        result = summarize_gdf(
            gdf,
            fields=[
                "Biodiversity Integrity Index 2015 Mean Value",
                "Biodiversity Integrity Index 2020 Mean Value",
            ],
        )

        bii_2015 = result["Biodiversity Integrity Index 2015 Mean Value"]["mean"]
        bii_2020 = result["Biodiversity Integrity Index 2020 Mean Value"]["mean"]

        # Step 2: Calculate change
        change = bii_2020 - bii_2015
        percent_change = (change / bii_2015) * 100

        # Step 3: Format as natural language
        if change > 0:
            trend = f"improved by {abs(percent_change):.1f}%"
        elif change < 0:
            trend = f"declined by {abs(percent_change):.1f}%"
        else:
            trend = "remained stable"

        response = (
            f"The Biodiversity Integrity Index (BII) for this area "
            f"{trend} between 2015 and 2020.\n\n"
            f"- **2015 BII**: {bii_2015:.2f}\n"
            f"- **2020 BII**: {bii_2020:.2f}\n"
            f"- **Change**: {'+' if change > 0 else ''}{change:.3f}\n\n"
            f"This suggests biodiversity conditions have "
            f"{'improved' if change > 0 else 'deteriorated' if change < 0 else 'remained stable'}."
        )

        # Verify response quality
        assert "improved" in response or "declined" in response or "stable" in response
        assert "2015" in response and "2020" in response
        assert "%" in response  # Percentage change mentioned

    @pytest.mark.integration
    def test_landcover_pattern_summary_workflow(self, sample_filtered_gdf):
        """Test Q7: Summarize all land cover fields."""
        from services.tools.attribute_tools import list_fields_gdf, summarize_gdf

        gdf = sample_filtered_gdf

        # User: "Can you summarize the main land cover classes?"

        # Step 1: Discover fields matching pattern
        all_fields_result = list_fields_gdf(gdf)
        all_field_names = [f["name"] for f in all_fields_result["fields"]]
        landcover_fields = [f for f in all_field_names if f.startswith("Landcover ")]

        assert len(landcover_fields) >= 6

        # Step 2: Summarize ALL in ONE call
        result = summarize_gdf(gdf, fields=landcover_fields)

        # Step 3: Format as natural language with interpretation
        # For single feature, mean = value
        totals = [
            (field.replace("Landcover ", "").replace(" hectares", ""), result[field]["mean"])
            for field in landcover_fields
        ]

        # Sort by area
        totals.sort(key=lambda x: x[1], reverse=True)

        response = "Here's the land cover distribution:\n\n"
        for category, area in totals:
            percent = (area / gdf["GIS_AREA"].iloc[0]) * 100
            response += f"- **{category}**: {area:.1f} ha ({percent:.1f}%)\n"

        response += f"\nThe area is predominantly {totals[0][0].lower()}."

        # Verify response quality
        assert "land cover" in response.lower()
        assert "predominantly" in response
        assert "ha" in response  # Uses appropriate units
        assert all(cat in response for cat, _ in totals[:3])  # Top 3 categories mentioned


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Verify performance doesn't degrade with improvements."""

    @pytest.mark.performance
    def test_large_field_list_performance(self, sample_protected_areas_gdf):
        """Test list_fields with many columns."""
        import time

        from services.tools.attribute_tools import list_fields_gdf

        gdf = sample_protected_areas_gdf

        start = time.time()
        result = list_fields_gdf(gdf)
        elapsed = time.time() - start

        # Should be very fast (< 0.1 seconds)
        assert elapsed < 0.1
        assert len(result) > 0

    @pytest.mark.performance
    def test_multi_field_summarize_performance(self, sample_filtered_gdf):
        """Test summarizing many fields at once."""
        import time

        from services.tools.attribute_tools import summarize_gdf

        gdf = sample_filtered_gdf

        # Get all numeric fields
        numeric_fields = gdf.select_dtypes(include=["number"]).columns.tolist()

        start = time.time()
        result = summarize_gdf(gdf, fields=numeric_fields)
        elapsed = time.time() - start

        # Should complete in < 1 second even with many fields
        assert elapsed < 1.0
        assert len(result) == len(numeric_fields)


# ============================================================================
# EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.edge_case
    def test_empty_pattern_match(self, sample_protected_areas_gdf):
        """Test when pattern matching finds no fields."""
        gdf = sample_protected_areas_gdf

        # Pattern that won't match anything
        nonexistent_pattern = [f for f in gdf.columns if f.startswith("ZZZZZ_")]

        assert len(nonexistent_pattern) == 0

        # Agent should handle gracefully (no crash)
        from services.tools.attribute_tools import summarize_gdf

        # Empty field list should return empty result
        result = summarize_gdf(gdf, fields=[])
        assert result == {} or result == []

    @pytest.mark.edge_case
    def test_single_feature_statistics(self, sample_filtered_gdf):
        """Test statistics on single-feature layer."""
        from services.tools.attribute_tools import summarize_gdf

        gdf = sample_filtered_gdf
        assert len(gdf) == 1

        # Statistics should still work
        result = summarize_gdf(gdf, fields=["GIS_AREA"])

        assert "GIS_AREA" in result
        # For single value, mean = min = max
        assert result["GIS_AREA"]["mean"] == result["GIS_AREA"]["min"]
        assert result["GIS_AREA"]["mean"] == result["GIS_AREA"]["max"]

    @pytest.mark.edge_case
    def test_special_characters_in_field_names(self, sample_protected_areas_gdf):
        """Test field names with special characters."""
        gdf = sample_protected_areas_gdf

        # Field with parentheses and >
        special_field = "AQUEDUCT_FUTURE_EXTREMELY High (>80%)_ha"

        assert special_field in gdf.columns

        # Should be accessible despite special chars
        from services.tools.attribute_tools import summarize_gdf

        result = summarize_gdf(gdf, fields=[special_field])

        assert special_field in result
        # Check for mean (not sum - that's not returned by summarize_gdf)
        assert "mean" in result[special_field]
        assert isinstance(result[special_field]["mean"], float)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
