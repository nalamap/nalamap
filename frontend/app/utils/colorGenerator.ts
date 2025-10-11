/**
 * Color generation utilities for automatic shade generation
 * Generates a full 11-shade color scale from a single base color
 */

import { ColorScale } from "../stores/settingsStore";

/**
 * Convert hex color to HSL
 */
function hexToHSL(hex: string): { h: number; s: number; l: number } {
  // Remove # if present
  hex = hex.replace(/^#/, "");

  // Parse RGB values
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

    switch (max) {
      case r:
        h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
        break;
      case g:
        h = ((b - r) / d + 2) / 6;
        break;
      case b:
        h = ((r - g) / d + 4) / 6;
        break;
    }
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100),
  };
}

/**
 * Convert HSL to hex color
 */
function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;

  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0;
  let g = 0;
  let b = 0;

  if (h >= 0 && h < 60) {
    r = c;
    g = x;
    b = 0;
  } else if (h >= 60 && h < 120) {
    r = x;
    g = c;
    b = 0;
  } else if (h >= 120 && h < 180) {
    r = 0;
    g = c;
    b = x;
  } else if (h >= 180 && h < 240) {
    r = 0;
    g = x;
    b = c;
  } else if (h >= 240 && h < 300) {
    r = x;
    g = 0;
    b = c;
  } else if (h >= 300 && h < 360) {
    r = c;
    g = 0;
    b = x;
  }

  const toHex = (val: number) => {
    const hex = Math.round((val + m) * 255).toString(16);
    return hex.length === 1 ? "0" + hex : hex;
  };

  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * Generate a complete color scale from a base color (500 shade)
 * Uses lightness adjustments to create lighter and darker shades
 */
export function generateColorScale(baseColor: string): ColorScale {
  const hsl = hexToHSL(baseColor);
  
  // Lightness values for each shade (calibrated for good contrast)
  const lightnessMap: Record<keyof ColorScale, number> = {
    shade_50: 96,   // Very light
    shade_100: 92,  // Light
    shade_200: 84,  // Light
    shade_300: 72,  // Light-medium
    shade_400: 60,  // Medium-light
    shade_500: hsl.l, // Base color (user selected)
    shade_600: Math.max(hsl.l - 10, 35),  // Medium-dark
    shade_700: Math.max(hsl.l - 20, 28),  // Dark
    shade_800: Math.max(hsl.l - 30, 20),  // Darker
    shade_900: Math.max(hsl.l - 40, 15),  // Very dark
    shade_950: Math.max(hsl.l - 50, 8),   // Darkest
  };

  // For very light base colors, adjust the scale
  if (hsl.l > 70) {
    lightnessMap.shade_50 = 98;
    lightnessMap.shade_100 = 95;
    lightnessMap.shade_200 = 90;
    lightnessMap.shade_300 = 80;
    lightnessMap.shade_400 = hsl.l;
    lightnessMap.shade_500 = Math.max(hsl.l - 10, 50);
    lightnessMap.shade_600 = Math.max(hsl.l - 20, 40);
    lightnessMap.shade_700 = Math.max(hsl.l - 30, 30);
    lightnessMap.shade_800 = Math.max(hsl.l - 40, 20);
    lightnessMap.shade_900 = Math.max(hsl.l - 50, 15);
    lightnessMap.shade_950 = Math.max(hsl.l - 60, 8);
  }

  // For very dark base colors, adjust the scale
  if (hsl.l < 30) {
    lightnessMap.shade_50 = Math.min(hsl.l + 60, 96);
    lightnessMap.shade_100 = Math.min(hsl.l + 50, 90);
    lightnessMap.shade_200 = Math.min(hsl.l + 40, 80);
    lightnessMap.shade_300 = Math.min(hsl.l + 30, 70);
    lightnessMap.shade_400 = Math.min(hsl.l + 20, 60);
    lightnessMap.shade_500 = hsl.l;
  }

  // Saturation adjustments for lighter shades (less saturated)
  const saturationMap: Record<keyof ColorScale, number> = {
    shade_50: Math.max(hsl.s - 40, 20),
    shade_100: Math.max(hsl.s - 30, 30),
    shade_200: Math.max(hsl.s - 20, 40),
    shade_300: Math.max(hsl.s - 10, 50),
    shade_400: Math.max(hsl.s - 5, 60),
    shade_500: hsl.s,
    shade_600: Math.min(hsl.s + 5, 100),
    shade_700: Math.min(hsl.s + 10, 100),
    shade_800: Math.min(hsl.s + 10, 100),
    shade_900: Math.min(hsl.s + 10, 100),
    shade_950: Math.min(hsl.s + 10, 100),
  };

  return {
    shade_50: hslToHex(hsl.h, saturationMap.shade_50, lightnessMap.shade_50),
    shade_100: hslToHex(hsl.h, saturationMap.shade_100, lightnessMap.shade_100),
    shade_200: hslToHex(hsl.h, saturationMap.shade_200, lightnessMap.shade_200),
    shade_300: hslToHex(hsl.h, saturationMap.shade_300, lightnessMap.shade_300),
    shade_400: hslToHex(hsl.h, saturationMap.shade_400, lightnessMap.shade_400),
    shade_500: hslToHex(hsl.h, saturationMap.shade_500, lightnessMap.shade_500),
    shade_600: hslToHex(hsl.h, saturationMap.shade_600, lightnessMap.shade_600),
    shade_700: hslToHex(hsl.h, saturationMap.shade_700, lightnessMap.shade_700),
    shade_800: hslToHex(hsl.h, saturationMap.shade_800, lightnessMap.shade_800),
    shade_900: hslToHex(hsl.h, saturationMap.shade_900, lightnessMap.shade_900),
    shade_950: hslToHex(hsl.h, saturationMap.shade_950, lightnessMap.shade_950),
  };
}
