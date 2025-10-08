"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp, RotateCcw, Info } from "lucide-react";
import { ColorScale, ColorSettings } from "../../stores/settingsStore";

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

const COLOR_SCALE_NAMES: Record<keyof ColorSettings, string> = {
  primary: "Primary",
  second_primary: "Second Primary",
  secondary: "Secondary",
  tertiary: "Tertiary",
};

// Color usage documentation
const COLOR_USAGE: Record<
  keyof ColorSettings,
  Record<keyof ColorScale, { used: boolean; locations: string[] }>
> = {
  primary: {
    shade_50: {
      used: true,
      locations: [
        "Settings page background",
        "Chat interface background",
        "Info panel backgrounds",
      ],
    },
    shade_100: {
      used: true,
      locations: ["Layer list background", "System message backgrounds"],
    },
    shade_200: {
      used: true,
      locations: [
        "Mobile menu buttons",
        "Progress bars",
        "Reset button",
        "Toggle buttons",
      ],
    },
    shade_300: {
      used: true,
      locations: [
        "Form input borders",
        "Component borders",
        "Chat interface borders",
      ],
    },
    shade_400: {
      used: true,
      locations: ["Resize handles", "Disabled text"],
    },
    shade_500: {
      used: true,
      locations: ["Secondary text", "Status messages", "Hex code display"],
    },
    shade_600: {
      used: true,
      locations: [
        "Interactive links and buttons",
        "Chevron icons",
        "Percentage displays",
      ],
    },
    shade_700: {
      used: true,
      locations: [
        "Icon colors",
        "Description text",
        "Hover states",
        "Shade labels",
      ],
    },
    shade_800: {
      used: true,
      locations: ["Sidebar background", "Section headings"],
    },
    shade_900: {
      used: true,
      locations: ["Main text", "Page headings", "Strong emphasis"],
    },
    shade_950: {
      used: false,
      locations: [],
    },
  },
  second_primary: {
    shade_50: { used: false, locations: [] },
    shade_100: { used: false, locations: [] },
    shade_200: {
      used: true,
      locations: ["User message backgrounds in chat"],
    },
    shade_300: { used: false, locations: [] },
    shade_400: { used: false, locations: [] },
    shade_500: {
      used: true,
      locations: ["Loading progress bar fill"],
    },
    shade_600: {
      used: true,
      locations: [
        "Action buttons (Import, Add)",
        "Active tool indicators",
        "Send button",
        "Loading spinner",
      ],
    },
    shade_700: {
      used: true,
      locations: ["Button hover states"],
    },
    shade_800: { used: false, locations: [] },
    shade_900: { used: false, locations: [] },
    shade_950: { used: false, locations: [] },
  },
  secondary: {
    shade_50: { used: false, locations: [] },
    shade_100: {
      used: true,
      locations: ["Badge backgrounds (e.g. Corporate Branding)"],
    },
    shade_200: {
      used: true,
      locations: ["Info box borders (Color tips section)"],
    },
    shade_300: {
      used: true,
      locations: ["Input focus rings (chat textarea)"],
    },
    shade_400: { used: false, locations: [] },
    shade_500: {
      used: true,
      locations: ["Waiting state progress bar"],
    },
    shade_600: {
      used: true,
      locations: ["Waiting status text", "Send button icon"],
    },
    shade_700: {
      used: true,
      locations: ["Send button hover state"],
    },
    shade_800: {
      used: true,
      locations: ["Sidebar menu item hover background"],
    },
    shade_900: { used: false, locations: [] },
    shade_950: { used: false, locations: [] },
  },
  tertiary: {
    shade_50: { used: false, locations: [] },
    shade_100: { used: false, locations: [] },
    shade_200: { used: false, locations: [] },
    shade_300: { used: false, locations: [] },
    shade_400: { used: false, locations: [] },
    shade_500: {
      used: true,
      locations: ["Completed embedding progress bars"],
    },
    shade_600: {
      used: true,
      locations: [
        "Success messages",
        "Form checkboxes",
        "Completed status indicators",
      ],
    },
    shade_700: {
      used: true,
      locations: ["Export button hover state"],
    },
    shade_800: { used: false, locations: [] },
    shade_900: { used: false, locations: [] },
    shade_950: { used: false, locations: [] },
  },
};

interface ColorScaleEditorProps {
  scaleName: keyof ColorSettings;
  scale: ColorScale;
  onUpdate: (shade: keyof ColorScale, color: string) => void;
}

function ColorScaleEditor({
  scaleName,
  scale,
  onUpdate,
}: ColorScaleEditorProps) {
  const [expanded, setExpanded] = useState(false);
  const [hoveredShade, setHoveredShade] = useState<keyof ColorScale | null>(
    null,
  );

  return (
    <div className="border border-primary-300 rounded p-3 bg-white">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center space-x-3">
          <div className="flex space-x-1">
            {Object.entries(scale).map(([shade, color]) => (
              <div
                key={shade}
                className="w-4 h-8 border border-gray-300 rounded-sm"
                style={{ backgroundColor: color }}
                title={`${shade}: ${color}`}
              />
            ))}
          </div>
          <span className="font-medium text-primary-900">
            {COLOR_SCALE_NAMES[scaleName]}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-primary-600" />
        ) : (
          <ChevronDown className="w-5 h-5 text-primary-600" />
        )}
      </button>

      {expanded && (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {Object.entries(scale).map(([shade, color]) => {
            const usage = COLOR_USAGE[scaleName][shade as keyof ColorScale];
            return (
              <div
                key={shade}
                className="flex items-center space-x-2 relative"
                onMouseEnter={() => setHoveredShade(shade as keyof ColorScale)}
                onMouseLeave={() => setHoveredShade(null)}
              >
                <input
                  type="color"
                  value={color}
                  onChange={(e) =>
                    onUpdate(shade as keyof ColorScale, e.target.value)
                  }
                  className="w-10 h-8 rounded border border-primary-300 cursor-pointer"
                />
                <div className="flex-1 text-xs">
                  <div className="text-primary-700 font-medium flex items-center space-x-1">
                    <span>{COLOR_SCALE_LABELS[shade as keyof ColorScale]}</span>
                    {usage.used ? (
                      <Info className="w-3 h-3 text-second-primary-600" />
                    ) : (
                      <span className="text-primary-400 text-[10px]">
                        (unused)
                      </span>
                    )}
                  </div>
                  <div className="text-primary-500 font-mono">{color}</div>
                </div>

                {/* Usage Tooltip */}
                {hoveredShade === shade && usage.used && (
                  <div className="absolute left-0 top-full mt-1 z-50 w-64 p-3 bg-primary-900 text-white text-xs rounded shadow-lg">
                    <div className="font-semibold mb-2">
                      Used in {usage.locations.length} location
                      {usage.locations.length !== 1 ? "s" : ""}:
                    </div>
                    <ul className="space-y-1">
                      {usage.locations.map((location, idx) => (
                        <li key={idx} className="flex items-start">
                          <span className="mr-1">•</span>
                          <span>{location}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ColorSettingsComponent() {
  const [collapsed, setCollapsed] = useState(true);

  const colorSettings = useInitializedSettingsStore((s) => s.color_settings);
  const updateColorScale = useInitializedSettingsStore(
    (s) => s.updateColorScale,
  );
  const resetColorSettings = useInitializedSettingsStore(
    (s) => s.resetColorSettings,
  );

  if (!colorSettings) {
    return (
      <div className="border border-primary-300 rounded p-4 bg-white">
        <p className="text-sm text-primary-600">
          Loading color settings...
        </p>
      </div>
    );
  }

  return (
    <div className="border border-primary-300 rounded bg-white overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between p-4 hover:bg-primary-50 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <h2 className="text-2xl font-semibold text-primary-800">
            Color Customization
          </h2>
          <span className="text-xs text-primary-600 bg-secondary-100 px-2 py-1 rounded">
            Corporate Branding
          </span>
        </div>
        {collapsed ? (
          <ChevronDown className="w-6 h-6 text-primary-600" />
        ) : (
          <ChevronUp className="w-6 h-6 text-primary-600" />
        )}
      </button>

      {!collapsed && (
        <div className="p-4 pt-0 space-y-4">
          <div className="flex items-start justify-between">
            <p className="text-sm text-primary-600">
              Customize the application's color scheme to match your corporate
              branding. Changes apply immediately and are saved with your
              settings.
            </p>
            <button
              onClick={() => {
                if (
                  confirm(
                    "Are you sure you want to reset all colors to defaults?",
                  )
                ) {
                  resetColorSettings();
                }
              }}
              className="flex items-center space-x-1 px-3 py-1 text-sm bg-primary-200 hover:bg-primary-300 text-primary-800 rounded transition-colors"
              title="Reset to default colors"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reset</span>
            </button>
          </div>

          <div className="space-y-3">
            {Object.entries(colorSettings).map(([scaleName, scale]) => (
              <ColorScaleEditor
                key={scaleName}
                scaleName={scaleName as keyof ColorSettings}
                scale={scale}
                onUpdate={(shade, color) =>
                  updateColorScale(
                    scaleName as keyof ColorSettings,
                    shade,
                    color,
                  )
                }
              />
            ))}
          </div>

          <div className="mt-4 p-3 bg-secondary-50 border border-secondary-200 rounded">
            <h4 className="text-sm font-semibold text-primary-800 mb-2">
              💡 Tips for Color Selection
            </h4>
            <ul className="text-xs text-primary-700 space-y-1">
              <li>• Use lighter shades (50-300) for backgrounds</li>
              <li>• Use middle shades (400-600) for borders and accents</li>
              <li>• Use darker shades (700-950) for text and emphasis</li>
              <li>
                • Maintain sufficient contrast for accessibility (WCAG AA)
              </li>
              <li>
                • Test your colors with the UI before finalizing changes
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
