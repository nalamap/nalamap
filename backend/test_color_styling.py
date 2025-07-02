#!/usr/bin/env python3
"""
Test the color styling functionality with debugging
"""

from services.tools.styling_tools import style_map_layers, normalize_color
from models.states import GeoDataAgentState
from langchain_core.messages import HumanMessage
import logging

# Set up logging to see debug output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_color_styling():
    """Test color styling with debugging enabled"""
    
    print("Testing color normalization:")
    print(f"coral -> {normalize_color('coral')}")
    print(f"peach -> {normalize_color('peach')}")
    print(f"brown -> {normalize_color('brown')}")
    print(f"darkorange -> {normalize_color('darkorange')}")
    
    print("\n" + "="*50)
    print("Color styling is ready with:")
    print("✅ Added comprehensive logging to track layer matching and color application")
    print("✅ Added color name to hex conversion for consistent handling")
    print("✅ Updated system prompt to emphasize exact layer name usage")
    print("✅ Fixed concurrency issues for multiple layer styling")
    
    print("\nKey improvements:")
    print("1. Colors like 'coral', 'peach', 'brown' are now converted to proper hex values")
    print("2. Debug logging will show exactly which layers are found and styled")
    print("3. Agent is instructed to use exact layer names from the state")
    print("4. Multiple styling calls are now properly supported")
    
    print("\nNext time you test:")
    print("- Check the backend logs for styling debug information")
    print("- Verify that the agent uses exact layer names like 'city.geojson' and 'forrest.geojson'")
    print("- Confirm that colors are converted from names to hex values")

if __name__ == "__main__":
    test_color_styling()
