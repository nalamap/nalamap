"use client";

import { useState } from "react";
import { useInitializedSettingsStore } from "../../hooks/useInitializedSettingsStore";
import { ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
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
          {Object.entries(scale).map(([shade, color]) => (
            <div key={shade} className="flex items-center space-x-2">
              <input
                type="color"
                value={color}
                onChange={(e) =>
                  onUpdate(shade as keyof ColorScale, e.target.value)
                }
                className="w-10 h-8 rounded border border-primary-300 cursor-pointer"
              />
              <div className="flex-1 text-xs">
                <div className="text-primary-700 font-medium">
                  {COLOR_SCALE_LABELS[shade as keyof ColorScale]}
                </div>
                <div className="text-primary-500 font-mono">{color}</div>
              </div>
            </div>
          ))}
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
