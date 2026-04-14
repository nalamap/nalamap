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
    <div className="obsidian-panel settings-panel">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="obsidian-panel-header settings-panel-header"
      >
        <div className="flex items-center gap-3">
          <h2 className="obsidian-heading text-lg">Theme Preference</h2>
          <span className="obsidian-chip">
            {theme === "dark" ? "Dark Mode" : "Light Mode"}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="h-5 w-5" />
        ) : (
          <ChevronDown className="h-5 w-5" />
        )}
      </button>

      {expanded && (
        <div className="obsidian-panel-body settings-panel-body space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <button
              type="button"
              onClick={() => setTheme("light")}
              className={`obsidian-toggle-card text-left ${
                theme === "light" ? "obsidian-toggle-card-active" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                  <Sun className="h-8 w-8 text-secondary-500" />
                  <div>
                    <div className="obsidian-heading text-base">Light Mode</div>
                    <div className="obsidian-muted text-sm">
                      Bright and clear for well-lit environments.
                    </div>
                  </div>
                </div>
                {theme === "light" && <span className="obsidian-chip">Active</span>}
              </div>
            </button>

            <button
              type="button"
              onClick={() => setTheme("dark")}
              className={`obsidian-toggle-card text-left ${
                theme === "dark" ? "obsidian-toggle-card-active" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                  <Moon className="h-8 w-8 text-info-400" />
                  <div>
                    <div className="obsidian-heading text-base">Dark Mode</div>
                    <div className="obsidian-muted text-sm">
                      Lower glare and better map emphasis in dimmer settings.
                    </div>
                  </div>
                </div>
                {theme === "dark" && <span className="obsidian-chip">Active</span>}
              </div>
            </button>
          </div>

          <div className="obsidian-note obsidian-note-info text-sm">
            <div className="flex items-start gap-3">
              <Monitor className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="obsidian-strong mb-2">Theme Settings</p>
                <ul className="obsidian-muted list-disc space-y-1 pl-4 text-xs leading-6">
                  <li>Map basemaps switch automatically to match the active theme.</li>
                  <li>Your preference is stored and restored across sessions.</li>
                  <li>Dark mode aligns best with the current Obsidian Lens design system.</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
