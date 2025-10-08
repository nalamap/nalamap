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

  // Apply primary colors
  Object.entries(colors.primary).forEach(([key, value]) => {
    const cssVarName = `--primary-${key.replace("shade_", "")}`;
    root.style.setProperty(cssVarName, value);
  });

  // Apply second primary colors
  Object.entries(colors.second_primary).forEach(([key, value]) => {
    const cssVarName = `--second-primary-${key.replace("shade_", "")}`;
    root.style.setProperty(cssVarName, value);
  });

  // Apply secondary colors
  Object.entries(colors.secondary).forEach(([key, value]) => {
    const cssVarName = `--secondary-${key.replace("shade_", "")}`;
    root.style.setProperty(cssVarName, value);
  });

  // Apply tertiary colors
  Object.entries(colors.tertiary).forEach(([key, value]) => {
    const cssVarName = `--tertiary-${key.replace("shade_", "")}`;
    root.style.setProperty(cssVarName, value);
  });
}
