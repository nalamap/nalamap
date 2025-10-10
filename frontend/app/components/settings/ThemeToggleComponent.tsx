"use client";

import { useState, useEffect } from "react";
import { useSettingsStore } from "../../stores/settingsStore";
import { useMapStore } from "../../stores/mapStore";
import { Moon, Sun, Monitor, ChevronDown, ChevronUp } from "lucide-react";

const BASEMAPS = {
  light: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>',
  },
  dark: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution">CARTO</a>',
  },
};

export default function ThemeToggleComponent() {
  const theme = useSettingsStore((state) => state.theme);
  const setTheme = useSettingsStore((state) => state.setTheme);
  const setBasemap = useMapStore((state) => state.setBasemap);
  const [mounted, setMounted] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted) {
      // Apply theme class to document element
      document.documentElement.classList.toggle("dark", theme === "dark");
      // Switch basemap to match theme
      setBasemap(theme === "dark" ? BASEMAPS.dark : BASEMAPS.light);
    }
  }, [theme, mounted, setBasemap]);

  if (!mounted) {
    return null;
  }

  return (
    <div className="border border-primary-300 rounded bg-neutral-50 dark:bg-neutral-900 overflow-hidden">
      {/* Header - Clickable to expand/collapse */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 bg-primary-100 hover:bg-primary-200 dark:bg-primary-900 dark:hover:bg-primary-800 transition-colors"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h2 className="text-lg font-semibold text-primary-900 dark:text-primary-100">
              Theme Preference
            </h2>
            <span className="text-xs bg-info-100 dark:bg-info-900 text-info-800 dark:text-info-100 px-2 py-0.5 rounded-full font-medium">
              {theme === "dark" ? "Dark Mode" : "Light Mode"}
            </span>
          </div>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-primary-600" />
          ) : (
            <ChevronDown className="w-5 h-5 text-primary-600" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="p-4 space-y-4">
        {/* Theme Buttons */}
        <div className="grid grid-cols-2 gap-3">
          {/* Light Mode */}
          <button
            onClick={() => setTheme("light")}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === "light"
                ? "border-secondary-500 bg-secondary-50"
                : "border-primary-300 bg-neutral-50 hover:border-primary-400"
            }`}
          >
            <div className="flex flex-col items-center space-y-2">
              <Sun
                className={`w-8 h-8 ${
                  theme === "light" ? "text-secondary-600" : "text-primary-600"
                }`}
              />
              <div>
                <div
                  className={`text-sm font-medium ${
                    theme === "light" ? "text-secondary-900" : "text-primary-900"
                  }`}
                >
                  Light Mode
                </div>
                <div className="text-xs text-primary-600 mt-0.5">
                  Bright and clear
                </div>
              </div>
              {theme === "light" && (
                <div className="text-xs bg-secondary-600 text-neutral-50 px-2 py-0.5 rounded font-medium">
                  Active
                </div>
              )}
            </div>
          </button>

          {/* Dark Mode */}
          <button
            onClick={() => setTheme("dark")}
            className={`p-4 rounded-lg border-2 transition-all ${
              theme === "dark"
                ? "border-info-500 bg-info-50"
                : "border-primary-300 bg-neutral-50 hover:border-primary-400"
            }`}
          >
            <div className="flex flex-col items-center space-y-2">
              <Moon
                className={`w-8 h-8 ${
                  theme === "dark" ? "text-info-600" : "text-primary-600"
                }`}
              />
              <div>
                <div
                  className={`text-sm font-medium ${
                    theme === "dark" ? "text-info-900" : "text-primary-900"
                  }`}
                >
                  Dark Mode
                </div>
                <div className="text-xs text-primary-600 mt-0.5">
                  Easy on the eyes
                </div>
              </div>
              {theme === "dark" && (
                <div className="text-xs bg-info-600 text-neutral-50 px-2 py-0.5 rounded font-medium">
                  Active
                </div>
              )}
            </div>
          </button>
        </div>

        {/* Info */}
        <div className="bg-info-50 border border-info-200 rounded p-3 text-sm">
          <div className="flex items-start space-x-2">
            <Monitor className="w-4 h-4 text-info-600 mt-0.5 flex-shrink-0" />
            <div className="text-info-900">
              <p className="font-medium mb-1">Theme Settings</p>
              <ul className="text-xs space-y-1 text-info-800">
                <li>
                  • <strong>Light Mode</strong>: Traditional bright interface, best for well-lit environments
                </li>
                <li>
                  • <strong>Dark Mode</strong>: Reduces eye strain in low-light conditions
                </li>
                <li>
                  • Map basemap will automatically switch to match your theme
                </li>
                <li>
                  • Your preference is saved and persists across sessions
                </li>
              </ul>
            </div>
          </div>
        </div>
        </div>
      )}
    </div>
  );
}
