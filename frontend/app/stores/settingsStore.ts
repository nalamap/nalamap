import { create } from "zustand";
import { getApiBase } from "@/app/utils/apiBase";
import Logger from "../utils/logger";

export interface ExampleGeoServer {
  url: string;
  name: string;
  description: string;
  username?: string;
  password?: string;
}

export interface GeoServerBackend {
  url: string;
  name?: string;
  description?: string;
  username?: string;
  password?: string;
  enabled: boolean;
}

export interface SearchPortal {
  url: string;
  enabled: boolean;
}

export interface ModelOption {
  name: string;
  max_tokens: number;
}

export interface ToolOption {
  default_prompt: string;
  settings: Record<string, any>;
}

export interface ToolConfig {
  name: string;
  enabled: boolean;
  prompt_override: string;
}

export interface ModelSettings {
  model_provider: string;
  model_name: string;
  max_tokens: number;
  system_prompt: string;
}

export interface ColorScale {
  shade_50: string;
  shade_100: string;
  shade_200: string;
  shade_300: string;
  shade_400: string;
  shade_500: string;
  shade_600: string;
  shade_700: string;
  shade_800: string;
  shade_900: string;
  shade_950: string;
}

export interface ColorSettings {
  primary: ColorScale;
  second_primary: ColorScale;
  secondary: ColorScale;
  tertiary: ColorScale;
}

export interface SettingsSnapshot {
  search_portals?: SearchPortal[]; // DEPRECATED: No longer used in the application
  geoserver_backends: GeoServerBackend[];
  model_settings: ModelSettings;
  tools: ToolConfig[];
  tool_options: Record<string, ToolOption>;
  model_options: Record<string, ModelOption[]>;
  color_settings?: ColorSettings; // User-customizable colors
  session_id?: string;
}

export interface SettingsState extends SettingsSnapshot {
  // Initialization
  initialized: boolean;
  initializeIfNeeded: () => Promise<void>;
  initializeSettingsFromRemote: (opts: {
    system_prompt: string;
    tool_options: Record<string, ToolOption>;
    example_geoserver_backends: ExampleGeoServer[];
    model_options: Record<string, ModelOption[]>;
    color_settings: ColorSettings;
    session_id: string;
  }) => void;

  // Portal & Backend actions (kept for backward compatibility, but deprecated)
  addPortal: (portal: string) => void;
  removePortal: (url: string) => void;
  togglePortal: (url: string) => void;
  addBackend: (
    backend: Omit<GeoServerBackend, "enabled"> & { enabled?: boolean },
  ) => void;
  removeBackend: (url: string) => void;
  toggleBackend: (url: string) => void;

  // Model actions
  setModelProvider: (provider: string) => void;
  setModelName: (name: string) => void;
  setMaxTokens: (tokens: number) => void;
  setSystemPrompt: (prompt: string) => void;

  // Tool config actions
  addToolConfig: (name: string) => void;
  removeToolConfig: (name: string) => void;
  toggleToolConfig: (name: string) => void;
  setToolPromptOverride: (name: string, override: string) => void;

  // Available options
  available_tools: string[];
  setAvailableTools: (tools: string[]) => void;
  available_example_geoservers: ExampleGeoServer[];
  setAvailableExampleGeoServers: (geoservers: ExampleGeoServer[]) => void;
  available_model_providers: string[];
  setAvailableModelProviders: (providers: string[]) => void;
  available_model_names: string[];
  setAvailableModelNames: (names: string[]) => void;

  // Fetched options
  tool_options: Record<string, ToolOption>;
  setToolOptions: (opts: Record<string, ToolOption>) => void;
  model_options: Record<string, ModelOption[]>;
  setModelOptions: (opts: Record<string, ModelOption[]>) => void;

  // Color settings
  color_settings?: ColorSettings;
  setColorSettings: (colors: ColorSettings) => void;
  updateColorScale: (
    scaleName: keyof ColorSettings,
    shade: keyof ColorScale,
    color: string,
  ) => void;
  resetColorSettings: () => void;

  // Bulk
  getSettings: () => SettingsSnapshot;
  setSettings: (settings: SettingsSnapshot) => void;

  // Session
  setSessionId: (id?: string | null) => void;
}

// Module-level flag to prevent concurrent initialization requests
let initializationInProgress = false;

export const useSettingsStore = create<SettingsState>((set, get) => ({
  // Initialization
  initialized: false,

  initializeIfNeeded: async () => {
    const state = get();
    
    // Double-check: return if already initialized OR if initialization is in progress
    if (state.initialized || initializationInProgress) return;
    
    // Set flag immediately to block concurrent calls
    initializationInProgress = true;

    try {
      // API endpoint via shared resolver
      const API_BASE_URL = getApiBase();

      const res = await fetch(`${API_BASE_URL}/settings/options`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error(res.statusText);
      const opts = await res.json();
      get().initializeSettingsFromRemote(opts);
      set({ initialized: true });
    } catch (err) {
      Logger.error("Failed to initialize settings", err);
    } finally {
      // Reset flag after completion (success or failure)
      initializationInProgress = false;
    }
  },
  initializeSettingsFromRemote: (opts) => {
    const {
      setSystemPrompt,
      setAvailableTools,
      setToolOptions,
      addToolConfig,
      setAvailableExampleGeoServers,
      setAvailableModelProviders,
      setModelProvider,
      setModelOptions,
      setAvailableModelNames,
      setModelName,
      setMaxTokens,
      setColorSettings,
      model_settings,
      available_tools,
      available_example_geoservers,
      model_options,
      color_settings,
      setSessionId,
    } = get();

    if (opts.session_id) {
      setSessionId(opts.session_id);
    }

    // Initialize color settings if not already set
    if (!color_settings && opts.color_settings) {
      setColorSettings(opts.color_settings);
    }

    if (
      (!model_settings.system_prompt || model_settings.system_prompt === "") &&
      opts.system_prompt
    ) {
      setSystemPrompt(opts.system_prompt);
    }

    if (available_tools.length === 0) {
      const tools = Object.keys(opts.tool_options);
      setAvailableTools(tools);
      setToolOptions(opts.tool_options);
      tools.forEach(addToolConfig);
    }

    if (available_example_geoservers.length === 0) {
      setAvailableExampleGeoServers(opts.example_geoserver_backends);
    }

    if (Object.keys(model_options).length === 0) {
      setModelOptions(opts.model_options);
      const providers = Object.keys(opts.model_options);
      setAvailableModelProviders(providers);
      const defaultProvider = providers[0];
      setModelProvider(defaultProvider);
      const models = opts.model_options[defaultProvider];
      const names = models.map((m) => m.name);
      setAvailableModelNames(names);
      setModelName(names[0]);
      setMaxTokens(models[0].max_tokens);
    }
  },
  // initial
  search_portals: [],
  geoserver_backends: [],
  model_settings: {
    model_provider: "",
    model_name: "",
    max_tokens: 0,
    system_prompt: "",
  },
  tools: [],

  session_id: undefined,
  setSessionId: (id) => set({ session_id: id ?? undefined }),

  // available
  available_tools: [],
  available_example_geoservers: [],
  available_model_providers: [],
  available_model_names: [],

  // fetched slices
  tool_options: {},
  model_options: {},

  // portal & backend
  addPortal: (portal) =>
    set((state) => ({
      search_portals: (state.search_portals || []).some((p) => p.url === portal)
        ? state.search_portals
        : [...(state.search_portals || []), { url: portal, enabled: true }],
    })),
  removePortal: (url) =>
    set((state) => ({
      search_portals: (state.search_portals || []).filter((p) => p.url !== url),
    })),
  togglePortal: (url) =>
    set((state) => ({
      search_portals: (state.search_portals || []).map((p) =>
        p.url === url ? { ...p, enabled: !p.enabled } : p,
      ),
    })),

  addBackend: (backend) =>
    set((state) => {
      const existingIndex = state.geoserver_backends.findIndex(
        (b) => b.url === backend.url,
      );
      if (existingIndex >= 0) {
        const next = [...state.geoserver_backends];
        const previous = next[existingIndex];
        next[existingIndex] = {
          ...previous,
          ...backend,
          enabled: backend.enabled ?? previous.enabled,
        };
        return { geoserver_backends: next };
      }
      return {
        geoserver_backends: [
          ...state.geoserver_backends,
          {
            ...backend,
            enabled: backend.enabled ?? true,
          },
        ],
      };
    }),
  removeBackend: (url) =>
    set((state) => ({
      geoserver_backends: state.geoserver_backends.filter((b) => b.url !== url),
    })),
  toggleBackend: (url) =>
    set((state) => ({
      geoserver_backends: state.geoserver_backends.map((b) =>
        b.url === url ? { ...b, enabled: !b.enabled } : b,
      ),
    })),

  // model
  setModelProvider: (provider) =>
    set((state) => ({
      model_settings: { ...state.model_settings, model_provider: provider },
    })),
  setModelName: (name) =>
    set((state) => ({
      model_settings: { ...state.model_settings, model_name: name },
    })),
  setMaxTokens: (tokens) =>
    set((state) => ({
      model_settings: { ...state.model_settings, max_tokens: tokens },
    })),
  setSystemPrompt: (prompt) =>
    set((state) => ({
      model_settings: { ...state.model_settings, system_prompt: prompt },
    })),

  // tools
  addToolConfig: (name) =>
    set((state) => ({
      tools: state.tools.some((t) => t.name === name)
        ? state.tools
        : [
            ...state.tools,
            {
              name,
              enabled: true,
              prompt_override: state.tool_options[name]?.default_prompt || "",
            },
          ],
    })),
  removeToolConfig: (name) =>
    set((state) => ({ tools: state.tools.filter((t) => t.name !== name) })),
  toggleToolConfig: (name) =>
    set((state) => ({
      tools: state.tools.map((t) =>
        t.name === name ? { ...t, enabled: !t.enabled } : t,
      ),
    })),
  setToolPromptOverride: (name, override) =>
    set((state) => ({
      tools: state.tools.map((t) =>
        t.name === name ? { ...t, prompt_override: override } : t,
      ),
    })),

  // available options
  setAvailableTools: (tools) => set({ available_tools: tools }),
  setAvailableExampleGeoServers: (geoservers) =>
    set({ available_example_geoservers: geoservers }),
  setAvailableModelProviders: (providers) =>
    set({ available_model_providers: providers }),
  setAvailableModelNames: (names) => set({ available_model_names: names }),

  // fetched slices
  setToolOptions: (opts) => set({ tool_options: opts }),
  setModelOptions: (opts) => set({ model_options: opts }),

  // color settings
  color_settings: undefined,
  setColorSettings: (colors) => set({ color_settings: colors }),
  updateColorScale: (scaleName, shade, color) =>
    set((state) => {
      if (!state.color_settings) return state;
      return {
        color_settings: {
          ...state.color_settings,
          [scaleName]: {
            ...state.color_settings[scaleName],
            [shade]: color,
          },
        },
      };
    }),
  resetColorSettings: () => set({ color_settings: undefined }),

  // bulk
  getSettings: () => ({
    search_portals: get().search_portals || [],
    geoserver_backends: get().geoserver_backends,
    model_settings: get().model_settings,
    tools: get().tools,
    tool_options: get().tool_options,
    model_options: get().model_options,
    color_settings: get().color_settings,
    session_id: get().session_id,
  }),
  setSettings: (settings) =>
    set((state) => ({
      search_portals: settings.search_portals || [],
      geoserver_backends: settings.geoserver_backends,
      model_settings: settings.model_settings,
      tools: settings.tools,
      tool_options: settings.tool_options,
      model_options: settings.model_options,
      color_settings: settings.color_settings,
      session_id: state.session_id,
    })),
}));

// Expose store to window for E2E testing
if (typeof window !== "undefined") {
  (window as any).useSettingsStore = useSettingsStore;
  console.log("[SettingsStore] Exposed to window for testing");
}
