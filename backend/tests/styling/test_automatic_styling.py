"""
Test automatic styling functionality with AI-powered styling.
"""
import pytest
from unittest.mock import Mock
from services.tools.styling_tools import auto_style_new_layers, check_and_auto_style_layers
from models.geodata import GeoDataObject, LayerStyle


class TestAutomaticStyling:
    """Test AI-powered automatic styling functionality."""
    
    def create_test_layer(self, name: str, has_default_style: bool = True) -> GeoDataObject:
        """Create a test layer for styling tests."""
        layer = Mock(spec=GeoDataObject)
        layer.name = name
        layer.description = f"Test layer: {name}"
        layer.title = name
        
        if has_default_style:
            # Default blue styling that indicates need for auto-styling
            layer.style = Mock(spec=LayerStyle)
            layer.style.stroke_color = "#3388ff"
            layer.style.fill_color = "#3388ff"
        else:
            # Custom styling already applied
            layer.style = Mock(spec=LayerStyle)
            layer.style.stroke_color = "#ff0000"
            layer.style.fill_color = "#00ff00"
            
        return layer
    
    def test_check_and_auto_style_layers_detects_new_layers(self):
        """Test that check_and_auto_style_layers detects layers needing styling."""
        # Create test layers
        layer1 = self.create_test_layer("Rivers_of_Europe", has_default_style=True)
        layer2 = self.create_test_layer("Urban_Buildings", has_default_style=True) 
        layer3 = self.create_test_layer("Already_Styled", has_default_style=False)
        
        # Create mock state
        state = {
            "geodata_layers": [layer1, layer2, layer3],
            "messages": []
        }
        
        # Call the tool
        result = check_and_auto_style_layers(state, "test_call_id")
        
        # Check that it detected the layers needing styling
        assert result.update is not None
        messages = result.update["messages"]
        assert len(messages) == 1
        
        message_content = messages[0].content
        assert "2 newly uploaded layer(s)" in message_content
        assert "Rivers_of_Europe" in message_content
        assert "Urban_Buildings" in message_content
        assert "Already_Styled" not in message_content
    
    def test_auto_style_new_layers_identifies_layers_for_ai_styling(self):
        """Test that auto_style_new_layers correctly identifies layers for AI styling."""
        # Create test layers with different styling needs
        rivers_layer = self.create_test_layer("Rivers_of_Africa", has_default_style=True)
        parks_layer = self.create_test_layer("National_Parks_Canada", has_default_style=True)
        styled_layer = self.create_test_layer("Custom_Styled_Layer", has_default_style=False)
        
        # Create mock state
        state = {
            "geodata_layers": [rivers_layer, parks_layer, styled_layer],
            "messages": []
        }
        
        # Call the tool
        result = auto_style_new_layers(state, "test_call_id")
        
        # Check the response
        assert result.update is not None
        messages = result.update["messages"]
        assert len(messages) == 1
        
        message_content = messages[0].content
        assert "2 layer(s) that need intelligent styling" in message_content
        assert "Rivers_of_Africa" in message_content
        assert "National_Parks_Canada" in message_content
        assert "Custom_Styled_Layer" not in message_content
        assert "AI to determine the most appropriate cartographic styling" in message_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
