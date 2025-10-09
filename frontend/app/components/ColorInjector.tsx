"use client";

import { useEffect } from "react";
import { useSettingsStore } from "../stores/settingsStore";
import { ColorSettings } from "../stores/settingsStore";

/**
 * Component that dynamically injects CSS variables from color settings.
 * This allows user-customizable colors without reloading the page.
 */
export default function ColorInjector() {
  const colorSettings = useSettingsStore((s) => s.color_settings);

  useEffect(() => {
    if (!colorSettings) {
      // No custom colors set, use defaults from globals.css
      return;
    }

    // Apply color settings to CSS variables
    applyCSSVariables(colorSettings);
  }, [colorSettings]);

  return null; // This component doesn't render anything
}

/**
 * Apply color settings to CSS custom properties
 */
function applyCSSVariables(colors: ColorSettings) {
  const root = document.documentElement;

  // Helper function to apply a color scale
  const applyScale = (scale: any, prefix: string) => {
    Object.entries(scale).forEach(([key, value]) => {
      const cssVarName = `--${prefix}-${key.replace("shade_", "")}`;
      root.style.setProperty(cssVarName, value as string);
    });
  };

  // Apply all color scales
  applyScale(colors.primary, "primary");
  applyScale(colors.second_primary, "second-primary");
  applyScale(colors.secondary, "secondary");
  applyScale(colors.tertiary, "tertiary");
  applyScale(colors.danger, "danger");
  applyScale(colors.warning, "warning");
  applyScale(colors.info, "info");
  applyScale(colors.neutral, "neutral");
  applyScale(colors.corporate_1, "corporate-1");
  applyScale(colors.corporate_2, "corporate-2");
  applyScale(colors.corporate_3, "corporate-3");
}
