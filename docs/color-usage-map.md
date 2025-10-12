# Color Usage Documentation

This document provides a comprehensive overview of all color classes used in the NalaMap frontend application.

## Color Palette Overview

The application uses four main color scales:
- **Primary**: Main brand color (dark blue/gray)
- **Second Primary**: Accent color
- **Secondary**: Supporting color
- **Tertiary**: Highlight/success color

Each scale has 11 shades from 50 (lightest) to 950 (darkest).

## Color Usage by Shade

### Primary Colors

#### primary-50
- **Used in:** Background for main content areas, chat interface
- **Locations:**
  - `app/settings/page.tsx`: Main content background
  - `app/page.tsx`: Info panel backgrounds
  - `app/components/chat/AgentInterface.tsx`: Chat interface background
  - `app/components/settings/ColorSettingsComponent.tsx`: Hover states

#### primary-100
- **Used in:** Light backgrounds, chat messages
- **Locations:**
  - `app/page.tsx`: Layer list background
  - `app/components/chat/AgentInterface.tsx`: System message backgrounds

#### primary-200
- **Used in:** Buttons, loading indicators, borders
- **Locations:**
  - `app/settings/page.tsx`: Mobile menu buttons, hover states, progress bars, buttons
  - `app/page.tsx`: Toggle buttons
  - `app/components/chat/AgentInterface.tsx`: Message borders
  - `app/components/settings/ColorSettingsComponent.tsx`: Reset button backgrounds

#### primary-300
- **Used in:** Borders, input fields
- **Locations:**
  - `app/settings/page.tsx`: All form input borders
  - `app/page.tsx`: Button borders
  - `app/components/chat/AgentInterface.tsx`: Chat interface border, input borders, overlay borders
  - `app/components/settings/*`: All component borders

#### primary-400
- **Used in:** Hover states, resize handles, disabled text
- **Locations:**
  - `app/settings/page.tsx`: Sidebar resize handle, disabled tool/backend text
  - `app/page.tsx`: Resize handles

#### primary-500
- **Used in:** Secondary text, status messages
- **Locations:**
  - `app/settings/page.tsx`: Unknown status text
  - `app/components/chat/AgentInterface.tsx`: Small text, metadata
  - `app/components/settings/ColorSettingsComponent.tsx`: Hex code display

#### primary-600
- **Used in:** Interactive elements, icons, links
- **Locations:**
  - `app/settings/page.tsx`: Links, buttons, percentage displays
  - `app/components/chat/AgentInterface.tsx`: Active tool buttons, close buttons
  - `app/components/settings/ColorSettingsComponent.tsx`: Chevron icons, description text

#### primary-700
- **Used in:** Hover states, descriptive text
- **Locations:**
  - `app/settings/page.tsx`: Icon colors, description text, hover states
  - `app/page.tsx`: Icon colors, hover states
  - `app/components/chat/AgentInterface.tsx`: Message text, hover states
  - `app/components/settings/ColorSettingsComponent.tsx`: Shade labels

#### primary-800
- **Used in:** Sidebar background, headings
- **Locations:**
  - `app/settings/page.tsx`: Sidebar background, section headings
  - `app/page.tsx`: Sidebar background
  - `app/components/chat/AgentInterface.tsx`: Tool text
  - `app/components/settings/*`: All section headings
  - `app/components/sidebar/Sidebar.tsx`: Main sidebar background

#### primary-900
- **Used in:** Main text, strong emphasis
- **Locations:**
  - `app/settings/page.tsx`: Main heading, enabled text
  - `app/components/chat/AgentInterface.tsx`: Message text, headings
  - `app/components/settings/ColorSettingsComponent.tsx`: Scale names, main text

#### primary-950
- **Used in:** Not currently used in the application
- **Status:** ❌ Unused

### Second Primary Colors

#### second-primary-200
- **Used in:** User message backgrounds
- **Locations:**
  - `app/components/chat/AgentInterface.tsx`: User message background

#### second-primary-500
- **Used in:** Progress bars
- **Locations:**
  - `app/settings/page.tsx`: Loading progress bar fill

#### second-primary-600
- **Used in:** Action buttons, active states
- **Locations:**
  - `app/settings/page.tsx`: Import/add buttons, active tool indicators
  - `app/components/chat/AgentInterface.tsx`: Send button, active chat tool button, loading spinner
  - `app/components/settings/ToolSettingsComponent.tsx`: Add tool button

#### second-primary-700
- **Used in:** Button hover states
- **Locations:**
  - `app/settings/page.tsx`: Button hover states
  - `app/components/chat/AgentInterface.tsx`: Button hover states
  - `app/components/settings/ToolSettingsComponent.tsx`: Button hover state

#### second-primary-50, 100, 300, 400, 800, 900, 950
- **Status:** ❌ Unused

### Secondary Colors

#### secondary-100
- **Used in:** Badge backgrounds
- **Locations:**
  - `app/components/settings/ColorSettingsComponent.tsx`: "Corporate Branding" badge

#### secondary-200
- **Used in:** Info box borders
- **Locations:**
  - `app/components/settings/ColorSettingsComponent.tsx`: Tips section border

#### secondary-300
- **Used in:** Input focus rings
- **Locations:**
  - `app/components/chat/AgentInterface.tsx`: Textarea focus ring

#### secondary-500
- **Used in:** Progress bar (waiting state)
- **Locations:**
  - `app/settings/page.tsx`: Waiting state progress bar

#### secondary-600
- **Used in:** Status text (waiting)
- **Locations:**
  - `app/settings/page.tsx`: Waiting status message
  - `app/components/chat/AgentInterface.tsx`: Send button

#### secondary-700
- **Used in:** Hover states
- **Locations:**
  - `app/components/chat/AgentInterface.tsx`: Send button hover

#### secondary-800
- **Used in:** Sidebar hover states
- **Locations:**
  - `app/components/sidebar/Sidebar.tsx`: Menu item hover background

#### secondary-50, 400, 900, 950
- **Status:** ❌ Unused

### Tertiary Colors

#### tertiary-500
- **Used in:** Success progress bars
- **Locations:**
  - `app/settings/page.tsx`: Completed embedding progress bar

#### tertiary-600
- **Used in:** Success messages, checkboxes, completed states
- **Locations:**
  - `app/settings/page.tsx`: Success text, form checkboxes, completed status
  - `app/components/settings/ToolSettingsComponent.tsx`: Checkbox color
  - `app/components/settings/GeoServerSettingsComponent.tsx`: Checkbox color

#### tertiary-700
- **Used in:** Export button hover state
- **Locations:**
  - `app/settings/page.tsx`: Export button hover

#### tertiary-50, 100, 200, 300, 400, 800, 900, 950
- **Status:** ❌ Unused

## Summary Statistics

### Primary Colors
- **In Use:** 50, 100, 200, 300, 400, 500, 600, 700, 800, 900 (10/11 shades)
- **Unused:** 950

### Second Primary Colors  
- **In Use:** 200, 500, 600, 700 (4/11 shades)
- **Unused:** 50, 100, 300, 400, 800, 900, 950

### Secondary Colors
- **In Use:** 100, 200, 300, 500, 600, 700, 800 (7/11 shades)
- **Unused:** 50, 400, 900, 950

### Tertiary Colors
- **In Use:** 500, 600, 700 (3/11 shades)
- **Unused:** 50, 100, 200, 300, 400, 800, 900, 950

## Overall Statistics
- **Total Shades Defined:** 44 (4 scales × 11 shades)
- **Shades In Use:** 24 (54.5%)
- **Unused Shades:** 20 (45.5%)

## Recommendations

1. **Consider consolidating:** Many lighter and darker shades are unused. Consider reducing the palette to only the shades actually needed.

2. **Most used patterns:**
   - Primary-300 for borders
   - Primary-600/700 for interactive elements
   - Primary-800 for dark backgrounds
   - Primary-900 for text
   - Second-primary-600/700 for action buttons
   - Tertiary-600 for success states

3. **Potential additions:**
   - Error/danger color scale (currently using red-600 directly)
   - Warning color scale for alerts

## Non-standard Colors

The application also uses some non-palette colors directly:
- `red-600`: Error messages and remove buttons
- `white`: Various backgrounds
- `black`: Some text (rare)
- `gray-300`: Some borders (ColorSettingsComponent preview)
