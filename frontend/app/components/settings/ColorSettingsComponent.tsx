"use client";

import { useState, memo } from "react";
import { useSettingsStore } from "../../stores/settingsStore";
import { ChevronDown, ChevronUp, RotateCcw, Info, Wand2 } from "lucide-react";
import { ColorScale, ColorSettings } from "../../stores/settingsStore";
import { generateColorScale } from "../../utils/colorGenerator";

const COLOR_SCALE_LABELS: Record<keyof ColorScale, string> = {
  shade_50: "50 - Lightest",
  shade_100: "100",
  shade_200: "200",
  shade_300: "300",
  shade_400: "400",
  shade_500: "500 - Base",
  shade_600: "600",
  shade_700: "700",
  shade_800: "800",
  shade_900: "900",
  shade_950: "950 - Darkest",
};

// Organized color groups
const COLOR_GROUPS = {
  core: {
    title: "Core Colors",
    description: "Primary UI colors for text, backgrounds, and main actions",
    scales: ["primary", "second_primary", "secondary", "tertiary"] as (keyof ColorSettings)[],
  },
  semantic: {
    title: "Semantic Colors",
    description: "Status and feedback colors",
    scales: ["danger", "warning", "info", "neutral"] as (keyof ColorSettings)[],
  },
  corporate: {
    title: "Corporate/Brand Colors",
    description: "Your brand colors for layer styling and custom elements",
    scales: ["corporate_1", "corporate_2", "corporate_3"] as (keyof ColorSettings)[],
  },
};

const COLOR_SCALE_NAMES: Record<keyof ColorSettings, string> = {
  primary: "Primary (Text & Borders)",
  second_primary: "Second Primary (Actions)",
  secondary: "Secondary (Accents)",
  tertiary: "Tertiary (Success)",
  danger: "Danger (Errors)",
  warning: "Warning",
  info: "Info",
  neutral: "Neutral (White/Black)",
  corporate_1: "Corporate 1 (Rose)",
  corporate_2: "Corporate 2 (Sky)",
  corporate_3: "Corporate 3 (Purple)",
};

const COLOR_USAGE_HINTS: Record<keyof ColorSettings, string> = {
  primary: "Used for main text (900), backgrounds (50-100), borders (300), icons (600-700), and sidebar (800)",
  second_primary: "Action buttons (600), hover states (700), user messages (200), progress bars (500)",
  secondary: "Focus rings (300), waiting states (500-600), sidebar hover (800), badges (100)",
  tertiary: "Success messages (600), completed states, checkboxes, export button (700)",
  danger: "Error messages, delete/remove buttons (600), error backgrounds (100), hover (700)",
  warning: "Warning messages and alerts (600), warning backgrounds (100-200)",
  info: "Informational messages and hints (600), info backgrounds (100-200)",
  neutral: "Pure white (50), pure black (950), overlay backgrounds, neutral grays",
  corporate_1: "Your first brand color - used for layer type styling (rose/pink tones)",
  corporate_2: "Your second brand color - used for layer type styling (sky/blue tones)",
  corporate_3: "Your third brand color - used for layer type styling (purple tones)",
};

interface ColorScaleEditorProps {
  scaleName: keyof ColorSettings;
  scale: ColorScale;
  onUpdate: (shade: keyof ColorScale, color: string) => void;
  onAutoGenerate: (baseColor: string) => void;
}

// Memoize the ColorScaleEditor to prevent re-renders when parent state changes
// This ensures the expanded/collapsed state persists when colors are updated
const ColorScaleEditor = memo(function ColorScaleEditor({
  scaleName,
  scale,
  onUpdate,
  onAutoGenerate,
}: ColorScaleEditorProps) {
  const [expanded, setExpanded] = useState(false);
  const [showQuickPicker, setShowQuickPicker] = useState(false);

  const handleQuickColorChange = (color: string) => {
    onAutoGenerate(color);
    setShowQuickPicker(false);
  };

  return (
    <div className="border border-primary-300 rounded p-3 bg-neutral-50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center space-x-3 flex-1">
          {/* Gradient preview - clickable to select colors */}
          <div className="flex space-x-0.5">
            {Object.entries(scale).map(([shade, color]) => (
              <div
                key={shade}
                onClick={(e) => {
                  e.stopPropagation();
                  if (!expanded) {
                    setExpanded(true);
                  }
                  // Create a temporary color input to trigger color picker
                  const input = document.createElement('input');
                  input.type = 'color';
                  input.value = color;
                  input.style.position = 'absolute';
                  input.style.opacity = '0';
                  input.style.pointerEvents = 'none';
                  document.body.appendChild(input);
                  
                  input.addEventListener('change', (event) => {
                    const newColor = (event.target as HTMLInputElement).value;
                    onUpdate(shade as keyof ColorScale, newColor);
                    document.body.removeChild(input);
                  });
                  
                  input.addEventListener('blur', () => {
                    setTimeout(() => {
                      if (document.body.contains(input)) {
                        document.body.removeChild(input);
                      }
                    }, 100);
                  });
                  
                  input.click();
                }}
                className="w-3 h-8 first:rounded-l last:rounded-r cursor-pointer hover:ring-2 hover:ring-secondary-500 hover:z-10 transition-all"
                style={{ backgroundColor: color }}
                title={`${shade}: ${color} - Click to change`}
              />
            ))}
          </div>
          <div className="flex-1">
            <div className="font-medium text-primary-900 text-sm">
              {COLOR_SCALE_NAMES[scaleName]}
            </div>
            <div className="text-xs text-primary-600 mt-0.5">
              {COLOR_USAGE_HINTS[scaleName]}
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2 flex-shrink-0">
          {/* Quick Color Picker Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowQuickPicker(!showQuickPicker);
            }}
            className="p-1.5 bg-secondary-100 hover:bg-secondary-200 rounded transition-colors"
            title="Quick set color (auto-generates all shades)"
          >
            <Wand2 className="w-4 h-4 text-secondary-700" />
          </button>
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-primary-600" />
          ) : (
            <ChevronDown className="w-4 h-4 text-primary-600" />
          )}
        </div>
      </button>

      {/* Quick Color Picker */}
      {showQuickPicker && (
        <div className="mt-3 p-3 bg-secondary-50 border border-secondary-200 rounded">
          <div className="flex items-center space-x-3">
            <input
              type="color"
              value={scale.shade_500}
              onChange={(e) => handleQuickColorChange(e.target.value)}
              className="w-16 h-16 rounded cursor-pointer border-2 border-secondary-300"
              title="Pick main color - all shades will be generated automatically"
            />
            <div className="flex-1">
              <p className="text-sm font-medium text-secondary-900 mb-1">
                🪄 Quick Color Set
              </p>
              <p className="text-xs text-secondary-800">
                Pick your main color and we'll automatically generate all 11 shades (lighter to darker).
              </p>
            </div>
          </div>
        </div>
      )}

      {expanded && (
        <div className="mt-3 grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
          {Object.entries(scale).map(([shade, color]) => (
            <div key={shade} className="flex flex-col items-center space-y-1">
              <input
                type="color"
                value={color}
                onChange={(e) =>
                  onUpdate(shade as keyof ColorScale, e.target.value)
                }
                className="w-12 h-12 rounded cursor-pointer border border-primary-300"
                title={`Edit ${shade}`}
              />
              <span className="text-xs text-primary-700 font-mono">
                {COLOR_SCALE_LABELS[shade as keyof ColorScale]}
              </span>
              <span className="text-[10px] text-primary-500 font-mono">
                {color}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

export default function ColorSettingsComponent() {
  const [isOpen, setIsOpen] = useState(false); // Start collapsed by default
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const color_settings = useSettingsStore((state) => state.color_settings);
  const updateColorScale = useSettingsStore((state) => state.updateColorScale);
  const resetColorSettings = useSettingsStore((state) => state.resetColorSettings);

  if (!color_settings) {
    return (
      <div className="border border-primary-300 rounded p-4 bg-neutral-50">
        <p className="text-primary-600">Loading color settings...</p>
      </div>
    );
  }

  const handleReset = () => {
    resetColorSettings();
    setShowResetConfirm(false);
  };

  const handleAutoGenerate = (scaleName: keyof ColorSettings, baseColor: string) => {
    const generatedScale = generateColorScale(baseColor);
    // Update all shades at once
    Object.entries(generatedScale).forEach(([shade, color]) => {
      updateColorScale(scaleName, shade as keyof ColorScale, color);
    });
  };

  return (
    <div className="border border-primary-300 rounded bg-neutral-50 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 bg-primary-100 hover:bg-primary-200 transition-colors flex items-center justify-between"
      >
        <div className="flex items-center space-x-2">
          <h2 className="text-lg font-semibold text-primary-900">
            Color Customization
          </h2>
          <span className="text-xs bg-secondary-100 text-secondary-800 px-2 py-0.5 rounded-full font-medium">
            Corporate Branding
          </span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-primary-700" />
        ) : (
          <ChevronDown className="w-5 h-5 text-primary-700" />
        )}
      </button>

      {isOpen && (
        <div className="p-4 space-y-4">
          {/* Info Box */}
          <div className="bg-info-50 border border-info-200 rounded p-3 text-sm">
            <div className="flex items-start space-x-2">
              <Info className="w-4 h-4 text-info-600 mt-0.5 flex-shrink-0" />
              <div className="text-info-900">
                <p className="font-medium mb-1">
                  Customize your app's color scheme
                </p>
                <ul className="text-xs space-y-1 text-info-800">
                  <li>
                    • Click the <strong>🪄 magic wand</strong> icon for quick color generation
                  </li>
                  <li>
                    • Changes apply instantly across the entire application
                  </li>
                  <li>
                    • Use <strong>Core Colors</strong> for main UI elements
                  </li>
                  <li>
                    • <strong>Semantic Colors</strong> provide status feedback
                  </li>
                  <li>
                    • <strong>Corporate Colors</strong> for layer styling and
                    branding
                  </li>
                  <li>
                    • Each color has 11 shades (50=lightest, 950=darkest)
                  </li>
                  <li>
                    • Export your settings to save your custom color scheme
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Color Groups */}
          {Object.entries(COLOR_GROUPS).map(([groupKey, group]) => (
            <div key={groupKey} className="space-y-2">
              <div className="border-b border-primary-200 pb-1">
                <h3 className="text-sm font-semibold text-primary-800">
                  {group.title}
                </h3>
                <p className="text-xs text-primary-600">{group.description}</p>
              </div>
              <div className="space-y-2">
                {group.scales.map((scaleName) => (
                  <ColorScaleEditor
                    key={scaleName}
                    scaleName={scaleName}
                    scale={color_settings[scaleName]}
                    onUpdate={(shade, color) =>
                      updateColorScale(scaleName, shade, color)
                    }
                    onAutoGenerate={(baseColor) =>
                      handleAutoGenerate(scaleName, baseColor)
                    }
                  />
                ))}
              </div>
            </div>
          ))}

          {/* Reset Button */}
          <div className="pt-4 border-t border-primary-200">
            {!showResetConfirm ? (
              <button
                onClick={() => setShowResetConfirm(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-primary-200 text-primary-700 rounded hover:bg-primary-300 transition-colors font-medium"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Reset</span>
              </button>
            ) : (
              <div className="flex items-center space-x-2">
                <p className="text-sm text-primary-700">
                  Reset all colors to defaults?
                </p>
                <button
                  onClick={handleReset}
                  className="px-3 py-1 bg-danger-600 text-neutral-50 rounded hover:bg-danger-700 transition-colors font-medium text-sm"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="px-3 py-1 bg-primary-300 text-primary-900 rounded hover:bg-primary-400 transition-colors font-medium text-sm"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {/* Usage Tips */}
          <div className="bg-warning-50 border border-warning-200 rounded p-3 text-xs text-warning-900">
            <p className="font-medium mb-1">Tips for Color Selection:</p>
            <ul className="space-y-1">
              <li>
                • Use lighter shades (50-300) for backgrounds, darker (700-950)
                for text
              </li>
              <li>
                • Maintain sufficient contrast for accessibility between text and background
                colors
              </li>
              <li>
                • Keep your brand colors consistent with corporate guidelines
              </li>
              <li>
                • Test colors with color blindness simulators for accessibility
              </li>
              <li>
                • Danger (red) should remain red-ish for universal recognition
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
