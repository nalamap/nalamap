"""
Comprehensive styling validation tests.

These tests validate that the NaLaMap agent correctly applies styling
to layers based on AI-driven color selection and industry standards.
"""
import requests
import json
import pytest
from typing import Dict, Any, List


# Test configuration
BASE_URL = "http://localhost:8000"
API_TIMEOUT = 45


@pytest.mark.integration
@pytest.mark.styling
class TestStylingValidation:
    """Validate styling behavior and AI decision-making."""
    
    def create_test_layer(self, name: str, description: str = "", 
                         layer_type: str = "polygon") -> Dict[str, Any]:
        """Create a test layer with default styling."""
        return {
            "id": f"validation-{name.lower().replace(' ', '-')}",
            "data_source_id": "test_db",
            "data_type": "GeoJson",
            "data_origin": "uploaded",
            "data_source": "Test Source",
            "data_link": "http://test.com",
            "name": name,
            "title": f"{name} Dataset",
            "description": description,
            "visible": True,
            "style": {
                "stroke_color": "#3388ff",
                "stroke_weight": 2,
                "fill_color": "#3388ff",
                "fill_opacity": 0.3,
                "stroke_opacity": 1.0,
                "radius": 8,
                "line_cap": "round",
                "line_join": "round"
            }
        }
    
    def make_chat_request(self, query: str, layers: List[Dict] = None) -> Dict[str, Any]:
        """Make a chat API request and return the response."""
        if layers is None:
            layers = []
            
        request_data = {
            "query": query,
            "messages": [],
            "geodata_layers": layers,
            "options": {}
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/chat",
                json=request_data,
                timeout=API_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            pytest.skip(f"API not available: {e}")
    
    def get_layer_style_changes(self, original_layer: Dict, updated_layer: Dict) -> Dict[str, tuple]:
        """Compare layer styles and return changes."""
        original_style = original_layer.get("style", {})
        updated_style = updated_layer.get("style", {})
        
        changes = {}
        for key in ["stroke_color", "fill_color", "stroke_weight", "fill_opacity"]:
            original_value = original_style.get(key)
            updated_value = updated_style.get(key)
            if original_value != updated_value:
                changes[key] = (original_value, updated_value)
        
        return changes
    
    def test_agent_understands_direct_styling_requests(self):
        """Test that the agent understands and acts on direct styling requests."""
        layer = self.create_test_layer("Test Roads", "Highway network for testing")
        
        # Make a direct styling request
        result = self.make_chat_request(
            "Make the Test Roads layer red with thick borders",
            [layer]
        )
        
        # Validate response structure
        assert "messages" in result
        assert "geodata_layers" in result
        assert len(result["geodata_layers"]) == 1
        
        # Check if the agent provided a styling response
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        
        # Should mention styling concepts
        styling_keywords = ["color", "style", "red", "border", "thick", "applied", "changed"]
        mentioned_keywords = [kw for kw in styling_keywords if kw in response_text]
        
        assert len(mentioned_keywords) >= 2, f"Expected styling keywords, got: {mentioned_keywords}"
    
    def test_agent_applies_cartographic_knowledge(self):
        """Test that the agent applies cartographic best practices."""
        test_cases = [
            {
                "layer": self.create_test_layer("Rivers", "Major river systems and waterways"),
                "query": "Apply appropriate cartographic colors to this rivers layer",
                "expected_concepts": ["water", "blue", "hydro", "river", "aqua"]
            },
            {
                "layer": self.create_test_layer("Forests", "Protected forest areas and woodlands"),
                "query": "Style this forest layer with standard cartographic colors",
                "expected_concepts": ["green", "forest", "vegetation", "natural", "tree"]
            },
            {
                "layer": self.create_test_layer("Urban Areas", "Built-up urban and suburban areas"), 
                "query": "Apply urban area styling following cartographic conventions",
                "expected_concepts": ["urban", "built", "gray", "city", "development"]
            }
        ]
        
        for test_case in test_cases:
            result = self.make_chat_request(test_case["query"], [test_case["layer"]])
            
            # Should have meaningful response
            assert "messages" in result
            ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
            assert len(ai_messages) > 0
            
            response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
            
            # Should mention relevant cartographic concepts
            mentioned_concepts = [concept for concept in test_case["expected_concepts"] 
                                if concept in response_text]
            
            assert len(mentioned_concepts) >= 1, \
                f"Expected cartographic concepts {test_case['expected_concepts']}, " \
                f"found {mentioned_concepts} in: {response_text[:200]}..."
    
    def test_agent_handles_multiple_layer_scenarios(self):
        """Test agent behavior with multiple layers."""
        layers = [
            self.create_test_layer("Water Bodies", "Lakes, rivers, and reservoirs"),
            self.create_test_layer("Road Network", "Major highways and local roads"),
            self.create_test_layer("Green Spaces", "Parks and natural areas")
        ]
        
        result = self.make_chat_request(
            "Apply appropriate colors to all these layers based on their purpose",
            layers
        )
        
        # Should handle all layers
        assert "geodata_layers" in result
        assert len(result["geodata_layers"]) == 3
        
        # Should provide comprehensive response
        assert "messages" in result
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        
        # Should mention multiple layer types
        layer_types = ["water", "road", "green", "park", "natural"]
        mentioned_types = [ltype for ltype in layer_types if ltype in response_text]
        
        assert len(mentioned_types) >= 2, \
            f"Expected multiple layer type mentions, got: {mentioned_types}"
    
    def test_agent_styling_workflow_completeness(self):
        """Test that the complete styling workflow executes."""
        layer = self.create_test_layer(
            "Agricultural Areas", 
            "Farming and agricultural land use zones"
        )
        
        result = self.make_chat_request(
            "This layer shows agricultural areas. Please style it with colors that represent farmland and agriculture.",
            [layer]
        )
        
        # Should complete the workflow
        assert "messages" in result
        assert "geodata_layers" in result
        
        # Should have substantive AI response
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        # Response should be substantive (not just asking for clarification)
        response_text = " ".join([msg.get("content", "") for msg in ai_messages])
        assert len(response_text) > 50, "Response should be substantive"
        
        # Should mention agriculture or farming concepts
        response_lower = response_text.lower()
        agriculture_terms = ["agriculture", "farm", "crop", "land", "rural", "agricultural"]
        mentioned_terms = [term for term in agriculture_terms if term in response_lower]
        
        assert len(mentioned_terms) >= 1, \
            f"Expected agricultural terms, got: {mentioned_terms}"
    
    def test_agent_handles_styling_parameters(self):
        """Test that the agent understands various styling parameters."""
        layer = self.create_test_layer("Boundary Lines", "Administrative boundaries")
        
        result = self.make_chat_request(
            "Make this boundary layer have dashed lines with 50% transparency and red color",
            [layer]
        )
        
        # Should understand complex styling request
        assert "messages" in result
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        
        # Should mention styling parameters
        styling_params = ["dash", "transparent", "red", "line", "boundary", "opacity"]
        mentioned_params = [param for param in styling_params if param in response_text]
        
        assert len(mentioned_params) >= 2, \
            f"Expected styling parameters, got: {mentioned_params}"
    
    def test_agent_provides_helpful_responses(self):
        """Test that the agent provides helpful, informative responses."""
        layer = self.create_test_layer("Elevation Data", "Digital elevation model showing terrain")
        
        result = self.make_chat_request(
            "What would be good colors for this elevation layer?",
            [layer]
        )
        
        # Should provide helpful guidance
        assert "messages" in result
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages])
        
        # Response should be helpful and informative
        assert len(response_text) > 100, "Response should be detailed"
        
        response_lower = response_text.lower()
        elevation_terms = ["elevation", "terrain", "height", "topographic", "gradient", "relief"]
        color_terms = ["color", "brown", "green", "white", "gradient", "scale"]
        
        elevation_mentioned = [term for term in elevation_terms if term in response_lower]
        color_mentioned = [term for term in color_terms if term in response_lower]
        
        assert len(elevation_mentioned) >= 1, "Should mention elevation concepts"
        assert len(color_mentioned) >= 1, "Should mention color concepts"
    
    def test_performance_with_realistic_scenarios(self):
        """Test performance with realistic layer scenarios."""
        realistic_layers = [
            self.create_test_layer(
                "African Rivers Network",
                "Comprehensive dataset of major rivers across Africa including seasonal flow patterns"
            ),
            self.create_test_layer(
                "Urban Development Lagos",
                "Building footprints and urban infrastructure for Lagos metropolitan area"
            ),
            self.create_test_layer(
                "Protected Wildlife Areas",
                "National parks, game reserves, and conservation areas with biodiversity data"
            ),
            self.create_test_layer(
                "Transportation Infrastructure",
                "Roads, railways, and airports forming the regional transportation network"
            )
        ]
        
        import time
        start_time = time.time()
        
        result = self.make_chat_request(
            "These are important layers for regional planning. Please apply appropriate styling to each layer based on cartographic best practices.",
            realistic_layers
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time
        assert execution_time < 60.0, f"Took too long: {execution_time} seconds"
        
        # Should handle all layers
        assert "geodata_layers" in result
        assert len(result["geodata_layers"]) == 4
        
        # Should provide comprehensive response
        assert "messages" in result
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages])
        assert len(response_text) > 200, "Should provide detailed response for multiple layers"


@pytest.mark.integration
@pytest.mark.styling
@pytest.mark.color_theory
class TestColorTheoryValidation:
    """Validate color theory and cartographic principles."""
    
    def create_test_layer(self, name: str, description: str) -> Dict[str, Any]:
        """Create a test layer for color theory testing."""
        return {
            "id": f"color-theory-{name.lower().replace(' ', '-')}",
            "data_source_id": "test_db",
            "data_type": "GeoJson",
            "data_origin": "uploaded",
            "data_source": "Color Theory Test",
            "data_link": "http://test.com",
            "name": name,
            "title": f"{name} Dataset",
            "description": description,
            "visible": True,
            "style": {
                "stroke_color": "#3388ff",
                "stroke_weight": 2,
                "fill_color": "#3388ff",
                "fill_opacity": 0.3
            }
        }
    
    def make_chat_request(self, query: str, layers: List[Dict]) -> Dict[str, Any]:
        """Make a chat API request."""
        request_data = {
            "query": query,
            "messages": [],
            "geodata_layers": layers,
            "options": {}
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/chat",
                json=request_data,
                timeout=API_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            pytest.skip(f"API not available: {e}")
    
    def test_water_features_get_blue_associations(self):
        """Test that water features are associated with blue colors."""
        water_features = [
            ("Rivers", "Major river systems"),
            ("Lakes", "Natural and artificial lakes"),
            ("Coastal Areas", "Shorelines and coastal zones"),
            ("Watersheds", "Drainage basins and catchment areas")
        ]
        
        for name, description in water_features:
            layer = self.create_test_layer(name, description)
            
            result = self.make_chat_request(
                f"Apply standard cartographic colors to this {name.lower()} layer",
                [layer]
            )
            
            ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
            response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
            
            # Should associate with blue/water colors
            water_color_terms = ["blue", "aqua", "cyan", "water", "marine", "naval"]
            mentioned_water_terms = [term for term in water_color_terms if term in response_text]
            
            assert len(mentioned_water_terms) >= 1, \
                f"Expected water color terms for {name}, got: {mentioned_water_terms}"
    
    def test_vegetation_gets_green_associations(self):
        """Test that vegetation features are associated with green colors."""
        vegetation_features = [
            ("Forests", "Forested areas and woodlands"),
            ("Parks", "Urban parks and recreational areas"),
            ("Agricultural Land", "Farming and crop areas"),
            ("Natural Reserves", "Protected natural habitats")
        ]
        
        for name, description in vegetation_features:
            layer = self.create_test_layer(name, description)
            
            result = self.make_chat_request(
                f"Style this {name.lower()} layer with appropriate colors",
                [layer]
            )
            
            ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
            response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
            
            # Should associate with green/natural colors
            vegetation_terms = ["green", "forest", "natural", "vegetation", "plant", "leaf"]
            mentioned_vegetation_terms = [term for term in vegetation_terms if term in response_text]
            
            assert len(mentioned_vegetation_terms) >= 1, \
                f"Expected vegetation terms for {name}, got: {mentioned_vegetation_terms}"
    
    def test_infrastructure_gets_appropriate_associations(self):
        """Test that infrastructure features get appropriate color associations."""
        infrastructure_features = [
            ("Roads", "Highway and street network"),
            ("Buildings", "Residential and commercial structures"),
            ("Railways", "Rail transportation network"),
            ("Utilities", "Power lines and infrastructure")
        ]
        
        for name, description in infrastructure_features:
            layer = self.create_test_layer(name, description)
            
            result = self.make_chat_request(
                f"Apply infrastructure-appropriate colors to this {name.lower()} layer",
                [layer]
            )
            
            ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
            response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
            
            # Should mention infrastructure concepts
            infrastructure_terms = ["infrastructure", "built", "urban", "transport", "development"]
            color_terms = ["gray", "brown", "black", "yellow", "orange", "red"]
            
            mentioned_infra_terms = [term for term in infrastructure_terms if term in response_text]
            mentioned_color_terms = [term for term in color_terms if term in response_text]
            
            assert len(mentioned_infra_terms) >= 1 or len(mentioned_color_terms) >= 1, \
                f"Expected infrastructure or color terms for {name}"


if __name__ == "__main__":
    print("Running styling validation tests...")
    print("These tests validate that the NaLaMap agent correctly applies")
    print("AI-driven styling based on layer context and cartographic principles.")
    print()
    print("To run these tests:")
    print("pytest tests/test_styling_validation.py -v")
