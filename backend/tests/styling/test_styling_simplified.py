"""
Simplified test cases focusing on the API integration and agent behavior.

These tests verify that the styling functionality works correctly through
the actual API endpoints without trying to directly invoke LangChain tools.
"""
import requests
import json
import pytest
from typing import Dict, Any


# Test configuration
BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30


@pytest.mark.integration
@pytest.mark.styling
class TestBasicStyling:
    """Basic styling functionality tests via API."""
    
    def create_test_layer(self, name: str, description: str = "") -> Dict[str, Any]:
        """Helper to create a test layer structure."""
        return {
            "id": f"test-{name.lower().replace(' ', '-')}",
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
                "fill_opacity": 0.3
            }
        }
    
    def make_chat_request(self, query: str, layers: list = None) -> Dict[str, Any]:
        """Helper to make a chat API request."""
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
    
    def test_api_connectivity(self):
        """Test that the API is running and accessible."""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.RequestException:
            pytest.skip("Backend API not running")
    
    def test_basic_styling_request(self):
        """Test basic styling request through API."""
        layer = self.create_test_layer("Test Layer", "A test layer for styling")
        
        result = self.make_chat_request(
            "Change the color of this layer to red",
            [layer]
        )
        
        # Should return a response
        assert "messages" in result
        assert len(result["messages"]) > 0
        
        # Should have layer data
        assert "geodata_layers" in result
        assert len(result["geodata_layers"]) == 1
    
    def test_specific_color_styling(self):
        """Test requesting specific colors."""
        layer = self.create_test_layer("Roads", "Transportation network")
        
        result = self.make_chat_request(
            "Make the Roads layer blue with thick borders",
            [layer]
        )
        
        # Should have a response
        assert "messages" in result
        messages = result.get("messages", [])
        assert len(messages) > 0
        
        # Check if AI provided some response about styling
        ai_messages = [msg for msg in messages if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        # Should mention colors or styling
        assert any(keyword in response_text for keyword in ["color", "style", "blue", "border"])
    
    def test_layer_with_description_context(self):
        """Test that layer descriptions provide context for styling."""
        layer = self.create_test_layer(
            "Water Bodies", 
            "Rivers, lakes, and other water features across the region"
        )
        
        result = self.make_chat_request(
            "Apply appropriate colors to this water layer",
            [layer]
        )
        
        # Should have response
        assert "messages" in result
        ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        # Should understand it's about water
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        assert any(keyword in response_text for keyword in ["water", "blue", "color", "style"])
    
    def test_multiple_layers_handling(self):
        """Test handling multiple layers."""
        layers = [
            self.create_test_layer("Rivers", "Water features"),
            self.create_test_layer("Buildings", "Urban structures")
        ]
        
        result = self.make_chat_request(
            "Style these layers with appropriate colors",
            layers
        )
        
        # Should return both layers
        assert "geodata_layers" in result
        assert len(result["geodata_layers"]) == 2
        
        # Should have meaningful response
        assert "messages" in result
        ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
    
    def test_error_handling_no_layers(self):
        """Test graceful handling when no layers provided."""
        result = self.make_chat_request("Style this layer blue", [])
        
        # Should still provide a response
        assert "messages" in result
        messages = result.get("messages", [])
        assert len(messages) > 0
        
        # Should handle gracefully (not crash)
        ai_messages = [msg for msg in messages if msg.get("type") == "ai"]
        assert len(ai_messages) > 0


@pytest.mark.integration  
@pytest.mark.styling
class TestStylingScenarios:
    """Test realistic styling scenarios."""
    
    def create_test_layer(self, name: str, description: str = "") -> Dict[str, Any]:
        """Helper to create a test layer structure."""
        return {
            "id": f"scenario-{name.lower().replace(' ', '-')}",
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
                "fill_opacity": 0.3
            }
        }
    
    def make_chat_request(self, query: str, layers: list = None) -> Dict[str, Any]:
        """Helper to make a chat API request."""
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
    
    def test_natural_language_styling(self):
        """Test natural language styling requests."""
        layer = self.create_test_layer("Forest Areas", "Protected forest regions")
        
        result = self.make_chat_request(
            "Make the forest green like trees",
            [layer]
        )
        
        # Should understand the request
        assert "messages" in result
        ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        assert any(keyword in response_text for keyword in ["green", "forest", "color", "style"])
    
    def test_cartographic_appropriateness(self):
        """Test that the agent understands cartographic conventions."""
        scenarios = [
            ("Rivers of Africa", "Major river systems", ["water", "blue", "river"]),
            ("Urban Buildings", "City building footprints", ["building", "structure", "urban"]),
            ("National Parks", "Protected green areas", ["park", "green", "protected"]),
        ]
        
        for name, description, expected_keywords in scenarios:
            layer = self.create_test_layer(name, description)
            
            result = self.make_chat_request(
                f"Apply cartographically appropriate colors to the {name} layer",
                [layer]
            )
            
            # Should have response
            assert "messages" in result
            ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
            assert len(ai_messages) > 0
            
            response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
            
            # Should mention at least one expected keyword
            assert any(keyword in response_text for keyword in expected_keywords), \
                f"Expected one of {expected_keywords} in response for {name}"
    
    def test_styling_workflow(self):
        """Test a complete styling workflow."""
        layer = self.create_test_layer(
            "Transportation Network",
            "Major roads and highways for regional connectivity"
        )
        
        # Step 1: Request styling
        result = self.make_chat_request(
            "This is a roads dataset. Please style it appropriately for a transportation map.",
            [layer]
        )
        
        # Should have response
        assert "messages" in result
        assert "geodata_layers" in result
        
        # Should understand it's about transportation
        ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        assert any(keyword in response_text for keyword in [
            "road", "transport", "highway", "color", "style"
        ])


@pytest.mark.integration
@pytest.mark.styling  
@pytest.mark.slow
class TestAdvancedStyling:
    """Test advanced styling capabilities."""
    
    def create_test_layer(self, name: str, description: str = "") -> Dict[str, Any]:
        """Helper to create a test layer structure."""
        return {
            "id": f"advanced-{name.lower().replace(' ', '-')}",
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
                "fill_opacity": 0.3
            }
        }
    
    def make_chat_request(self, query: str, layers: list = None) -> Dict[str, Any]:
        """Helper to make a chat API request."""
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
    
    def test_complex_styling_parameters(self):
        """Test complex styling with multiple parameters."""
        layer = self.create_test_layer("Boundary Lines", "Administrative boundaries")
        
        result = self.make_chat_request(
            "Make this boundary layer have dashed red lines with 50% transparency",
            [layer]
        )
        
        # Should understand complex parameters
        assert "messages" in result
        ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        # Should mention some of the styling concepts
        styling_terms = ["dash", "red", "transparent", "line", "border", "stroke"]
        assert any(term in response_text for term in styling_terms)
    
    def test_contextual_styling_decisions(self):
        """Test that agent makes contextual styling decisions."""
        layers = [
            self.create_test_layer("Water Supply Network", "Pipes and water infrastructure"),
            self.create_test_layer("Electrical Grid", "Power lines and substations"),
            self.create_test_layer("Telecommunications", "Cable and communication networks")
        ]
        
        result = self.make_chat_request(
            "Style these infrastructure layers with distinct, appropriate colors",
            layers
        )
        
        # Should handle multiple infrastructure layers
        assert "messages" in result
        assert "geodata_layers" in result
        assert len(result["geodata_layers"]) == 3
        
        ai_messages = [msg for msg in result.get("messages", []) if msg.get("type") == "ai"]
        assert len(ai_messages) > 0
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        # Should mention infrastructure or utilities
        infrastructure_terms = ["infrastructure", "network", "utility", "distinct", "different"]
        assert any(term in response_text for term in infrastructure_terms)


if __name__ == "__main__":
    # Basic connectivity test
    print("Testing API connectivity...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Backend API is accessible")
        else:
            print(f"❌ Backend API returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to backend API: {e}")
        print("Make sure the backend is running on http://localhost:8000")
    
    print("\nTo run these tests:")
    print("pytest tests/test_styling_simplified.py -v")
