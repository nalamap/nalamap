# Color Customization Feature

## Overview

The color customization feature allows users to customize the application's color scheme to match their corporate branding or personal preferences. This is particularly useful for organizations that want to maintain consistent branding across all their tools.

## Architecture

### Backend (Python/FastAPI)

**File:** `backend/api/settings.py`

The backend provides default color settings through the `/settings/options` endpoint. These defaults match the colors defined in `globals.css`.

**Models:**
- `ColorScale`: Represents a complete color scale with 11 shades (50-950)
- `ColorSettings`: Contains all four color scales (primary, second_primary, secondary, tertiary)
- `SettingsOptions`: Extended to include `color_settings` field

**Default Colors:**
- **Primary**: Gray-blue tones for main UI elements (#505160 at 700)
- **Second Primary**: Lighter blue-gray for secondary elements (#68829e at 600)
- **Secondary**: Yellow-green accent color (#aebd38 at 500)
- **Tertiary**: Deep green for success states (#598234 at 600)

### Frontend (Next.js/React)

#### Color Injection (`app/components/ColorInjector.tsx`)

A client-side component that:
1. Subscribes to color settings from the settings store
2. Dynamically applies CSS custom properties when colors change
3. Falls back to defaults from `globals.css` when no custom colors are set
4. Provides zero-latency color updates without page reload

**Usage:** Added to `app/layout.tsx` to ensure colors are applied globally.

#### Color Settings Component (`app/components/settings/ColorSettingsComponent.tsx`)

A collapsible UI component that:
- Displays all four color scales with visual previews
- Allows editing individual shades using native color pickers
- Shows hex color codes for each shade
- Provides reset functionality to restore defaults
- Includes helpful tips for color selection
- Is fully integrated with the settings store

**Features:**
- Collapsible interface to save screen space
- Visual color gradient preview for each scale
- Expandable scales to edit individual shades
- Real-time updates reflected across the entire UI
- Reset button with confirmation dialog

#### Settings Store (`app/stores/settingsStore.ts`)

Extended with color-related state and actions:

**State:**
```typescript
color_settings?: ColorSettings;
```

**Actions:**
- `setColorSettings(colors)`: Replace entire color settings
- `updateColorScale(scaleName, shade, color)`: Update a single shade
- `resetColorSettings()`: Clear custom colors (fall back to defaults)

## Color Scale Structure

Each color scale has 11 shades following Tailwind CSS conventions:

| Shade | Usage |
|-------|-------|
| 50    | Lightest - backgrounds, subtle highlights |
| 100   | Very light backgrounds |
| 200   | Light borders, subtle separators |
| 300   | Borders, disabled states |
| 400   | Secondary text, icons |
| 500   | **Base color** - primary use case |
| 600   | Hover states, emphasis |
| 700   | Active states, important text |
| 800   | High contrast text |
| 900   | Very dark text, emphasis |
| 950   | Darkest - maximum contrast |

## Usage Examples

### Applying Colors in Components

Colors are used via CSS custom properties and Tailwind utility classes:

```tsx
// Background colors
<div className="bg-primary-50">Lightest background</div>
<div className="bg-primary-800">Dark background</div>

// Text colors
<span className="text-primary-900">Dark text</span>
<span className="text-secondary-600">Accent text</span>

// Borders
<div className="border border-primary-300">With border</div>

// Hover states
<button className="hover:bg-primary-700">Hover me</button>

// Inline styles (when dynamic)
<div style={{ backgroundColor: 'var(--tertiary-600)' }}>
  Custom element
</div>
```

### Programmatic Color Updates

```typescript
import { useSettingsStore } from '@/app/stores/settingsStore';

// Update a single shade
useSettingsStore.getState().updateColorScale('primary', 'shade_500', '#ff0000');

// Replace entire color scale
useSettingsStore.getState().setColorSettings({
  primary: { /* ... all shades ... */ },
  second_primary: { /* ... */ },
  secondary: { /* ... */ },
  tertiary: { /* ... */ }
});

// Reset to defaults
useSettingsStore.getState().resetColorSettings();
```

## Import/Export

Color settings are automatically included when exporting/importing settings:

**Export:**
```json
{
  "geoserver_backends": [...],
  "model_settings": {...},
  "tools": [...],
  "color_settings": {
    "primary": {
      "shade_50": "#f7f7f8",
      "shade_100": "#eeeef0",
      ...
    },
    ...
  }
}
```

## Testing

### Backend Tests (`backend/tests/test_color_settings.py`)

Tests cover:
- Color settings are returned from `/settings/options`
- Default colors match `globals.css`
- Model validation for color scales
- Session ID is set alongside color settings

Run with:
```bash
pytest backend/tests/test_color_settings.py
```

### Frontend Tests (`frontend/tests/color-settings.spec.ts`)

E2E tests cover:
- Color customization section visibility
- Expand/collapse functionality
- Individual color editing
- Real-time UI updates
- Reset functionality
- Export/import with colors
- Graceful handling of missing data

Run with:
```bash
npm run test:e2e -- color-settings.spec.ts
```

## Accessibility Considerations

When customizing colors:

1. **Contrast Ratio:** Maintain WCAG AA compliance (4.5:1 for normal text, 3:1 for large text)
2. **Color Blindness:** Don't rely solely on color to convey information
3. **Testing:** Test your color scheme with various color blindness simulators
4. **Documentation:** Document the intended use of each color scale

**Recommended Tools:**
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [Color Oracle](https://colororacle.org/) - Color blindness simulator
- Chrome DevTools - Has built-in contrast checker

## Best Practices

### For Organizations

1. **Create a Style Guide:** Document your color choices and usage rules
2. **Test Thoroughly:** Verify colors work across all pages and components
3. **Export Settings:** Save and distribute your color configuration
4. **Train Users:** Provide guidance on maintaining brand consistency

### For Developers

1. **Use Semantic Classes:** Prefer `bg-primary-50` over hardcoded colors
2. **Respect the Scale:** Use appropriate shades for different contexts
3. **Test Dark Mode:** Ensure colors work well in different environments
4. **Provide Fallbacks:** Always assume colors might be customized

## Limitations

1. **No Dark Mode:** Current implementation doesn't include separate dark mode colors
2. **No Color Validation:** The UI accepts any hex color without validation
3. **No Named Palettes:** Users can't save and switch between multiple color schemes
4. **No Color Generation:** Users must manually define all 11 shades per scale

## Future Enhancements

Potential improvements:

1. **Automatic Scale Generation:** Generate full scale from a single base color
2. **Color Palette Presets:** Provide common corporate color schemes
3. **Dark Mode Support:** Separate color definitions for dark mode
4. **Accessibility Checker:** Built-in contrast ratio validation
5. **Color Naming:** Allow users to name custom color schemes
6. **Import from Brand Guidelines:** Parse colors from CSS/design files

## Troubleshooting

### Colors Not Applying

**Problem:** Changed colors don't appear in the UI

**Solutions:**
1. Check browser console for errors
2. Verify `ColorInjector` is mounted in layout
3. Clear browser cache and hard reload
4. Check that color_settings exists in store:
   ```javascript
   console.log(window.useSettingsStore.getState().color_settings);
   ```

### Colors Reset After Reload

**Problem:** Custom colors don't persist between sessions

**Solutions:**
1. Ensure settings are exported before closing
2. Check localStorage for settings persistence
3. Verify settings import functionality works
4. Review backend session handling

### Color Picker Not Working

**Problem:** Native color picker doesn't open

**Solutions:**
1. Try a different browser (Safari, Chrome, Firefox have different implementations)
2. Check that input type="color" is supported
3. Use browser DevTools to inspect the element

## Related Files

- Backend: `backend/api/settings.py`
- Frontend Store: `frontend/app/stores/settingsStore.ts`
- Color Injector: `frontend/app/components/ColorInjector.tsx`
- Settings UI: `frontend/app/components/settings/ColorSettingsComponent.tsx`
- CSS Defaults: `frontend/app/globals.css`
- Backend Tests: `backend/tests/test_color_settings.py`
- Frontend Tests: `frontend/tests/color-settings.spec.ts`
