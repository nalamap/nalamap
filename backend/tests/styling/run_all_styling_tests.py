"""
Complete styling test suite for NaLaMap agent.
Execute this file to run all styling tests.
"""
import requests
import json
import pytest
import time
from typing import Dict, Any, List


# Test configuration
BASE_URL = "http://localhost:8000"
API_TIMEOUT = 30


class StylingTestSuite:
    """Complete test suite for styling functionality."""
    
    def __init__(self):
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []
    
    def create_test_layer(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a test layer structure."""
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
    
    def make_chat_request(self, query: str, layers: List[Dict] = None) -> Dict[str, Any]:
        """Make a chat API request."""
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
            raise Exception(f"API request failed: {e}")
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and track results."""
        print(f"🧪 Running: {test_name}")
        try:
            test_func()
            print(f"✅ PASSED: {test_name}")
            self.passed_tests += 1
            self.test_results.append((test_name, "PASSED", None))
        except Exception as e:
            print(f"❌ FAILED: {test_name} - {str(e)}")
            self.failed_tests += 1
            self.test_results.append((test_name, "FAILED", str(e)))
    
    def test_api_connectivity(self):
        """Test API connectivity."""
        response = requests.get(f"{BASE_URL}/", timeout=5)
        assert response.status_code == 200, "API not responding"
    
    def test_basic_styling_request(self):
        """Test basic styling request."""
        layer = self.create_test_layer("Test Layer", "A test layer")
        result = self.make_chat_request("Change the color to red", [layer])
        
        assert "messages" in result, "No messages in response"
        assert "geodata_layers" in result, "No layers in response"
        assert len(result["geodata_layers"]) == 1, "Wrong number of layers"
    
    def test_water_layer_styling(self):
        """Test water layer gets appropriate response."""
        layer = self.create_test_layer("Rivers", "Major river systems")
        result = self.make_chat_request("Apply appropriate colors to this rivers layer", [layer])
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        water_terms = ["water", "blue", "river", "hydro", "aqua"]
        assert any(term in response_text for term in water_terms), "No water-related terms in response"
    
    def test_forest_layer_styling(self):
        """Test forest layer gets appropriate response."""
        layer = self.create_test_layer("Forests", "Protected forest areas")
        result = self.make_chat_request("Style this forest layer appropriately", [layer])
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        forest_terms = ["green", "forest", "vegetation", "natural", "tree"]
        assert any(term in response_text for term in forest_terms), "No forest-related terms in response"
    
    def test_urban_layer_styling(self):
        """Test urban layer gets appropriate response."""
        layer = self.create_test_layer("Buildings", "Urban building footprints")
        result = self.make_chat_request("Apply urban styling to this buildings layer", [layer])
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        urban_terms = ["urban", "building", "structure", "city", "development"]
        assert any(term in response_text for term in urban_terms), "No urban-related terms in response"
    
    def test_multiple_layers(self):
        """Test handling multiple layers."""
        layers = [
            self.create_test_layer("Rivers", "Water features"),
            self.create_test_layer("Roads", "Transportation network")
        ]
        result = self.make_chat_request("Style these layers appropriately", layers)
        
        assert "geodata_layers" in result, "No layers in response"
        assert len(result["geodata_layers"]) == 2, "Wrong number of layers returned"
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
    
    def test_specific_color_request(self):
        """Test specific color styling request."""
        layer = self.create_test_layer("Test Layer", "Test layer")
        result = self.make_chat_request("Make this layer blue with thick borders", [layer])
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        color_terms = ["blue", "color", "border", "thick", "style"]
        assert any(term in response_text for term in color_terms), "No color-related terms in response"
    
    def test_natural_language_styling(self):
        """Test natural language styling request."""
        layer = self.create_test_layer("Parks", "Urban parks and green spaces")
        result = self.make_chat_request("Make this look like nature", [layer])
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        nature_terms = ["nature", "natural", "green", "park", "vegetation"]
        assert any(term in response_text for term in nature_terms), "No nature-related terms in response"
    
    def test_complex_styling_parameters(self):
        """Test complex styling with multiple parameters."""
        layer = self.create_test_layer("Boundaries", "Administrative boundaries")
        result = self.make_chat_request("Make this have dashed red lines with transparency", [layer])
        
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response"
        
        response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
        styling_terms = ["dash", "red", "transparent", "line", "border"]
        assert any(term in response_text for term in styling_terms), "No styling parameter terms in response"
    
    def test_cartographic_knowledge(self):
        """Test cartographic knowledge across different feature types."""
        test_cases = [
            ("Water Bodies", "Lakes and reservoirs", ["water", "blue"]),
            ("Transportation", "Road network", ["road", "transport"]),
            ("Vegetation", "Forest cover", ["green", "forest"]),
        ]
        
        for name, description, expected_terms in test_cases:
            layer = self.create_test_layer(name, description)
            result = self.make_chat_request(f"Apply cartographic colors to {name}", [layer])
            
            ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
            assert len(ai_messages) > 0, f"No AI response for {name}"
            
            response_text = " ".join([msg.get("content", "") for msg in ai_messages]).lower()
            found_terms = [term for term in expected_terms if term in response_text]
            assert len(found_terms) >= 1, f"No expected terms found for {name}: {expected_terms}"
    
    def test_error_handling_no_layers(self):
        """Test error handling when no layers provided."""
        result = self.make_chat_request("Style this layer blue", [])
        
        assert "messages" in result, "No messages in response"
        ai_messages = [msg for msg in result["messages"] if msg.get("type") == "ai"]
        assert len(ai_messages) > 0, "No AI response for error case"
    
    def test_performance_multiple_layers(self):
        """Test performance with multiple layers."""
        layers = [
            self.create_test_layer("African Rivers", "Major river systems"),
            self.create_test_layer("Urban Areas", "City development"),
            self.create_test_layer("Protected Areas", "National parks"),
            self.create_test_layer("Transportation", "Road network")
        ]
        
        start_time = time.time()
        result = self.make_chat_request("Style all these layers appropriately", layers)
        end_time = time.time()
        
        execution_time = end_time - start_time
        assert execution_time < 45.0, f"Too slow: {execution_time} seconds"
        
        assert len(result["geodata_layers"]) == 4, "Wrong number of layers returned"
    
    def run_all_tests(self):
        """Run all styling tests."""
        print("🎨 NaLaMap Styling Test Suite")
        print("=" * 50)
        
        # Test methods to run
        tests = [
            ("API Connectivity", self.test_api_connectivity),
            ("Basic Styling Request", self.test_basic_styling_request),
            ("Water Layer Styling", self.test_water_layer_styling),
            ("Forest Layer Styling", self.test_forest_layer_styling),
            ("Urban Layer Styling", self.test_urban_layer_styling),
            ("Multiple Layers", self.test_multiple_layers),
            ("Specific Color Request", self.test_specific_color_request),
            ("Natural Language Styling", self.test_natural_language_styling),
            ("Complex Styling Parameters", self.test_complex_styling_parameters),
            ("Cartographic Knowledge", self.test_cartographic_knowledge),
            ("Error Handling No Layers", self.test_error_handling_no_layers),
            ("Performance Multiple Layers", self.test_performance_multiple_layers),
        ]
        
        # Run all tests
        for test_name, test_func in tests:
            self.run_test(test_name, test_func)
            print()
        
        # Print summary
        print("=" * 50)
        print("📊 TEST SUMMARY")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"📈 Success Rate: {(self.passed_tests / (self.passed_tests + self.failed_tests) * 100):.1f}%")
        
        if self.failed_tests > 0:
            print("\n💥 FAILED TESTS:")
            for test_name, status, error in self.test_results:
                if status == "FAILED":
                    print(f"  - {test_name}: {error}")
        
        return self.failed_tests == 0


def main():
    """Main execution function."""
    print("Starting NaLaMap Styling Tests...")
    print(f"Target API: {BASE_URL}")
    print()
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"❌ API not responding correctly (status: {response.status_code})")
            return 1
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Please start the backend server first:")
        print("  python main.py")
        return 1
    
    # Run the test suite
    suite = StylingTestSuite()
    success = suite.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)
