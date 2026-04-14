"use client";

import { memo, useState } from "react";
import { ChevronDown, ChevronUp, Info, RotateCcw, Wand2 } from "lucide-react";
import {
  ColorScale,
  ColorSettings,
  useSettingsStore,
} from "../../stores/settingsStore";
import { generateColorScale } from "../../utils/colorGenerator";

const COLOR_SCALE_LABELS: Record<keyof ColorScale, string> = {
  shade_50: "50",
  shade_100: "100",
  shade_200: "200",
  shade_300: "300",
  shade_400: "400",
  shade_500: "500",
  shade_600: "600",
  shade_700: "700",
  shade_800: "800",
  shade_900: "900",
  shade_950: "950",
};

const COLOR_GROUPS = {
  core: {
    title: "Core System",
    description:
      "Primary interaction, surface contrast, and key UI accents.",
    scales: ["primary", "second_primary", "secondary", "tertiary"] as (
      | keyof ColorSettings
    )[],
  },
  semantic: {
    title: "Semantic Feedback",
    description: "Status colors used for warnings, errors, and guidance.",
    scales: ["danger", "warning", "info", "neutral"] as (
      | keyof ColorSettings
    )[],
  },
  corporate: {
    title: "Brand Extensions",
    description:
      "Supporting palettes for layers, highlights, and project-specific branding.",
    scales: ["corporate_1", "corporate_2", "corporate_3"] as (
      | keyof ColorSettings
    )[],
  },
} as const;

const COLOR_GROUP_ORDER = ["core", "semantic", "corporate"] as const;

const COLOR_SCALE_NAMES: Record<keyof ColorSettings, string> = {
  primary: "Primary",
  second_primary: "Action",
  secondary: "Accent",
  tertiary: "Success",
  danger: "Danger",
  warning: "Warning",
  info: "Info",
  neutral: "Neutral",
  corporate_1: "Corporate 01",
  corporate_2: "Corporate 02",
  corporate_3: "Corporate 03",
};

const COLOR_USAGE_HINTS: Record<keyof ColorSettings, string> = {
  primary:
    "Drives text hierarchy, layered surfaces, and resting states across the interface.",
  second_primary:
    "Powers primary actions, progress states, and high-attention controls.",
  secondary:
    "Used for focus, supporting accents, and subtle directional cues.",
  tertiary:
    "Reserved for completion states, success feedback, and positive actions.",
  danger:
    "Used for destructive actions, validation failures, and critical system states.",
  warning:
    "Highlights caution, recoverable issues, and operations that need review.",
  info: "Supports helper content, guidance, and informational callouts.",
  neutral:
    "Anchors white, black, overlays, and grayscale utility values for contrast.",
  corporate_1:
    "Brand accent for thematic map layers and rose-leaning category highlights.",
  corporate_2:
    "Brand accent for thematic map layers and sky-leaning category highlights.",
  corporate_3:
    "Brand accent for thematic map layers and violet-leaning category highlights.",
};

function getShadeEntries(scale: ColorScale) {
  return Object.entries(scale) as [keyof ColorScale, string][];
}

interface ShadeTokenProps {
  shade: keyof ColorScale;
  color: string;
  onUpdate: (shade: keyof ColorScale, color: string) => void;
}

function ShadeToken({ shade, color, onUpdate }: ShadeTokenProps) {
  return (
    <label className="obsidian-color-token">
      <input
        type="color"
        value={color}
        onChange={(event) => onUpdate(shade, event.target.value)}
        className="sr-only"
        aria-label={`Set shade ${COLOR_SCALE_LABELS[shade]} color`}
      />
      <span
        className="obsidian-color-token-preview"
        style={{ backgroundColor: color }}
      />
      <span className="obsidian-overline mt-3 block">
        {COLOR_SCALE_LABELS[shade]}
      </span>
      <span className="obsidian-strong mt-1 block font-mono text-xs">
        {color.toUpperCase()}
      </span>
    </label>
  );
}

interface ColorScaleEditorProps {
  scaleName: keyof ColorSettings;
  scale: ColorScale;
  onUpdate: (shade: keyof ColorScale, color: string) => void;
  onAutoGenerate: (baseColor: string) => void;
}

const ColorScaleEditor = memo(function ColorScaleEditor({
  scaleName,
  scale,
  onUpdate,
  onAutoGenerate,
}: ColorScaleEditorProps) {
  const [expanded, setExpanded] = useState(false);
  const [showQuickPicker, setShowQuickPicker] = useState(false);
  const shadeEntries = getShadeEntries(scale);

  return (
    <article className="obsidian-card space-y-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1 space-y-3">
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="w-full text-left"
            aria-expanded={expanded}
          >
            <div className="flex flex-wrap items-center gap-3">
              <h4 className="obsidian-heading text-base">
                {COLOR_SCALE_NAMES[scaleName]}
              </h4>
              <span className="obsidian-chip">{scale.shade_500.toUpperCase()}</span>
            </div>
            <p className="obsidian-muted mt-2 text-sm leading-6">
              {COLOR_USAGE_HINTS[scaleName]}
            </p>
          </button>

          <div className="obsidian-preview-strip">
            {shadeEntries.map(([shade, color]) => (
              <label key={shade} className="block">
                <input
                  type="color"
                  value={color}
                  onChange={(event) => onUpdate(shade, event.target.value)}
                  className="sr-only"
                  aria-label={`Edit ${COLOR_SCALE_NAMES[scaleName]} shade ${COLOR_SCALE_LABELS[shade]}`}
                />
                <span
                  className="obsidian-preview-swatch"
                  style={{ backgroundColor: color }}
                  title={`${COLOR_SCALE_LABELS[shade]}: ${color.toUpperCase()}`}
                />
              </label>
            ))}
          </div>
        </div>

        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => setShowQuickPicker((current) => !current)}
            className="obsidian-icon-button"
            aria-pressed={showQuickPicker}
            aria-label={`Toggle quick generator for ${COLOR_SCALE_NAMES[scaleName]}`}
            title="Generate a full tonal scale from one base color"
          >
            <Wand2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="obsidian-icon-button"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${COLOR_SCALE_NAMES[scaleName]} editor`}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {showQuickPicker && (
        <div className="obsidian-note obsidian-note-info flex flex-col gap-4 sm:flex-row sm:items-center">
          <label className="obsidian-color-well">
            <input
              type="color"
              value={scale.shade_500}
              onChange={(event) => onAutoGenerate(event.target.value)}
              className="absolute inset-0 cursor-pointer opacity-0"
              aria-label={`Pick a base color for ${COLOR_SCALE_NAMES[scaleName]}`}
            />
            <span
              className="absolute inset-3 rounded-[0.8rem]"
              style={{ backgroundColor: scale.shade_500 }}
            />
          </label>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="obsidian-overline">Quick Generate</span>
              <span className="obsidian-chip">
                Base {scale.shade_500.toUpperCase()}
              </span>
            </div>
            <p className="obsidian-strong text-sm">
              Pick one anchor tone and regenerate the full 11-step scale.
            </p>
            <p className="obsidian-muted text-sm leading-6">
              This keeps the palette coherent and is a better starting point
              than hand-editing every shade in isolation.
            </p>
          </div>
        </div>
      )}

      {expanded && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {shadeEntries.map(([shade, color]) => (
            <ShadeToken
              key={shade}
              shade={shade}
              color={color}
              onUpdate={onUpdate}
            />
          ))}
        </div>
      )}
    </article>
  );
});

export default function ColorSettingsComponent() {
  const [isOpen, setIsOpen] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const colorSettings = useSettingsStore((state) => state.color_settings);
  const updateColorScale = useSettingsStore((state) => state.updateColorScale);
  const resetColorSettings = useSettingsStore((state) => state.resetColorSettings);

  const handleAutoGenerate = (
    scaleName: keyof ColorSettings,
    baseColor: string,
  ) => {
    const generatedScale = generateColorScale(baseColor);

    for (const [shade, color] of getShadeEntries(generatedScale)) {
      updateColorScale(scaleName, shade, color);
    }
  };

  if (!colorSettings) {
    return (
      <section className="obsidian-panel">
        <div className="obsidian-panel-body pt-5">
          <div className="obsidian-note">
            <p className="obsidian-overline mb-2">Color System</p>
            <p className="obsidian-strong text-sm">
              Loading palette configuration.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="obsidian-panel">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="obsidian-panel-header bg-transparent"
        aria-expanded={isOpen}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="obsidian-heading text-xl">Color System</h2>
            <span className="obsidian-chip">Brand and Theme</span>
          </div>
          <p className="obsidian-muted mt-3 max-w-3xl text-sm leading-6">
            Tune the tonal hierarchy that drives surfaces, text contrast,
            interaction states, and branded map accents.
          </p>
        </div>
        <span className="obsidian-chip h-10 w-10 shrink-0 p-0">
          {isOpen ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
      </button>

      {isOpen && (
        <div className="obsidian-panel-body space-y-6">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(17rem,0.75fr)]">
            <div className="obsidian-note obsidian-note-info">
              <div className="flex items-start gap-3">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <div className="space-y-3">
                  <div>
                    <p className="obsidian-overline mb-2">
                      Design Direction
                    </p>
                    <p className="obsidian-strong text-sm">
                      Keep the system tonal, layered, and restrained.
                    </p>
                  </div>
                  <ul className="obsidian-muted list-disc space-y-2 pl-4 text-sm leading-6">
                    <li>Use shade 50-300 for surfaces and shade 700-950 for text.</li>
                    <li>Keep semantic colors recognizable instead of pushing them toward brand hues.</li>
                    <li>Use corporate scales for map storytelling and branded accents, not core readability.</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="obsidian-note obsidian-note-warning">
              <p className="obsidian-overline mb-2">Operational Notes</p>
              <ul className="obsidian-muted list-disc space-y-2 pl-4 text-sm leading-6">
                <li>Changes apply immediately across the application.</li>
                <li>Quick Generate is the fastest way to keep a scale internally consistent.</li>
                <li>Test high-contrast areas after changing primary or neutral values.</li>
              </ul>
            </div>
          </div>

          {COLOR_GROUP_ORDER.map((groupKey) => {
            const group = COLOR_GROUPS[groupKey];

            return (
              <section key={groupKey} className="space-y-4">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="obsidian-overline mb-2">{group.title}</p>
                    <p className="obsidian-muted max-w-3xl text-sm leading-6">
                      {group.description}
                    </p>
                  </div>
                  <span className="obsidian-chip">
                    {group.scales.length} scales
                  </span>
                </div>

                <div className="space-y-4">
                  {group.scales.map((scaleName) => (
                    <ColorScaleEditor
                      key={scaleName}
                      scaleName={scaleName}
                      scale={colorSettings[scaleName]}
                      onUpdate={(shade, color) =>
                        updateColorScale(scaleName, shade, color)
                      }
                      onAutoGenerate={(baseColor) =>
                        handleAutoGenerate(scaleName, baseColor)
                      }
                    />
                  ))}
                </div>
              </section>
            );
          })}

          {!showResetConfirm ? (
            <button
              type="button"
              onClick={() => setShowResetConfirm(true)}
              className="obsidian-button-ghost"
            >
              <RotateCcw className="h-4 w-4" />
              Restore default palette
            </button>
          ) : (
            <div className="obsidian-note obsidian-note-danger flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="obsidian-overline mb-2">Reset Palette</p>
                <p className="obsidian-strong text-sm">
                  Restore the original application colors.
                </p>
                <p className="obsidian-muted mt-2 text-sm leading-6">
                  This replaces all current edits with the default tonal system.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => {
                    resetColorSettings();
                    setShowResetConfirm(false);
                  }}
                  className="obsidian-button-danger"
                >
                  Confirm reset
                </button>
                <button
                  type="button"
                  onClick={() => setShowResetConfirm(false)}
                  className="obsidian-button-ghost"
                >
                  Keep current palette
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
