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

export interface ExampleMCPServer {
  url: string;
  name: string;
  description: string;
}

export interface GeoServerBackend {
  url: string;
  name?: string;
  description?: string;
  username?: string;
  password?: string;
  enabled: boolean;
  allow_insecure?: boolean; // Allow insecure connections (expired/self-signed SSL certs)
}

export interface MCPServer {
  url: string;
  name?: string;
  description?: string;
  enabled: boolean;
  api_key?: string; // Optional API key for authentication
  headers?: Record<string, string>; // Optional custom headers for auth
}

export interface SearchPortal {
  url: string;
  enabled: boolean;
}

export interface ModelOption {
  name: string;
  max_tokens: number;
  input_cost_per_million?: number | null;
  output_cost_per_million?: number | null;
  cache_cost_per_million?: number | null;
  description?: string | null;
  supports_tools?: boolean;
  supports_vision?: boolean;
  // Phase 1: Enhanced model selection metadata
  context_window?: number;
  supports_parallel_tool_calls?: boolean;
  tool_calling_quality?: string; // "none" | "basic" | "good" | "excellent"
  reasoning_capability?: string; // "basic" | "intermediate" | "advanced" | "expert"
}

export interface ToolOption {
  default_prompt: string;
  settings: Record<string, any>;
  enabled: boolean; // whether the tool is enabled by default
  group?: string | null; // tools in the same group are mutually exclusive
  display_name?: string | null; // user-friendly name for UI
  category?: string | null; // tool category (geocoding, geoprocessing, etc.)
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
  message_window_size?: number | null; // Optional: Max recent messages to keep (default: 20 from env)
  enable_parallel_tools?: boolean; // Optional: Enable parallel tool execution (default: false, experimental)
  enable_performance_metrics?: boolean; // Optional: Enable performance metrics tracking (default: false)
  // Dynamic Tool Selection (Week 3)
  enable_dynamic_tools?: boolean; // Optional: Enable dynamic tool selection (default: false)
  tool_selection_strategy?: string; // Optional: Strategy for tool selection (default: "conservative")
  tool_similarity_threshold?: number; // Optional: Minimum similarity score 0.0-1.0 (default: 0.3)
  max_tools_per_query?: number | null; // Optional: Maximum tools to load per query (default: null = unlimited)
  // Conversation Summarization (Week 3)
  use_summarization?: boolean; // Optional: Enable automatic conversation summarization (default: false)
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
  danger: ColorScale;
  warning: ColorScale;
  info: ColorScale;
  neutral: ColorScale;
  corporate_1: ColorScale;
  corporate_2: ColorScale;
  corporate_3: ColorScale;
}

export interface SettingsSnapshot {
  search_portals?: SearchPortal[]; // DEPRECATED: No longer used in the application
  geoserver_backends: GeoServerBackend[];
  mcp_servers?: MCPServer[]; // MCP server configuration
  model_settings: ModelSettings;
  tools: ToolConfig[];
  tool_options: Record<string, ToolOption>;
  model_options: Record<string, ModelOption[]>;
  color_settings?: ColorSettings; // User-customizable colors
  theme?: "light" | "dark"; // Theme preference
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
    example_mcp_servers: ExampleMCPServer[];
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
  toggleBackendInsecure: (url: string) => void;

  // MCP server actions
  addMCPServer: (
    server: Omit<MCPServer, "enabled"> & { enabled?: boolean },
  ) => void;
  removeMCPServer: (url: string) => void;
  toggleMCPServer: (url: string) => void;

  // Model actions
  setModelProvider: (provider: string) => void;
  setModelName: (name: string) => void;
  setMaxTokens: (tokens: number) => void;
  setSystemPrompt: (prompt: string) => void;
  setMessageWindowSize: (size: number | null) => void;
  setEnableParallelTools: (enabled: boolean) => void;
  setEnablePerformanceMetrics: (enabled: boolean) => void;
  // Dynamic Tool Selection (Week 3)
  setEnableDynamicTools: (enabled: boolean) => void;
  setToolSelectionStrategy: (strategy: string) => void;
  setToolSimilarityThreshold: (threshold: number) => void;
  setMaxToolsPerQuery: (max: number | null) => void;
  // Conversation Summarization (Week 3)
  setUseSummarization: (enabled: boolean) => void;

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
  available_example_mcp_servers: ExampleMCPServer[];
  setAvailableExampleMCPServers: (servers: ExampleMCPServer[]) => void;
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

  // Theme settings
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
  toggleTheme: () => void;

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
      setAvailableExampleMCPServers,
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
      available_example_mcp_servers,
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

    if (available_example_mcp_servers.length === 0) {
      setAvailableExampleMCPServers(opts.example_mcp_servers);
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
  mcp_servers: [],
  model_settings: {
    model_provider: "",
    model_name: "",
    max_tokens: 0,
    system_prompt: "",
    message_window_size: null, // null = use backend default (20)
    enable_parallel_tools: false, // Default: disabled (experimental)
    enable_performance_metrics: false, // Default: disabled
    // Dynamic Tool Selection (Week 3)
    enable_dynamic_tools: false, // Default: disabled
    tool_selection_strategy: "conservative", // Default strategy
    tool_similarity_threshold: 0.3, // Default threshold
    max_tools_per_query: null, // null = unlimited
  },
  tools: [],

  session_id: undefined,
  setSessionId: (id) => set({ session_id: id ?? undefined }),

  // available
  available_tools: [],
  available_example_geoservers: [],
  available_example_mcp_servers: [],
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
  toggleBackendInsecure: (url) =>
    set((state) => ({
      geoserver_backends: state.geoserver_backends.map((b) =>
        b.url === url ? { ...b, allow_insecure: !b.allow_insecure } : b,
      ),
    })),

  // mcp servers
  addMCPServer: (server) =>
    set((state) => {
      const existingIndex = (state.mcp_servers || []).findIndex(
        (s) => s.url === server.url,
      );
      if (existingIndex >= 0) {
        const next = [...(state.mcp_servers || [])];
        const previous = next[existingIndex];
        next[existingIndex] = {
          ...previous,
          ...server,
          enabled: server.enabled ?? previous.enabled,
        };
        return { mcp_servers: next };
      }
      return {
        mcp_servers: [
          ...(state.mcp_servers || []),
          {
            ...server,
            enabled: server.enabled ?? true,
          },
        ],
      };
    }),
  removeMCPServer: (url) =>
    set((state) => ({
      mcp_servers: (state.mcp_servers || []).filter((s) => s.url !== url),
    })),
  toggleMCPServer: (url) =>
    set((state) => ({
      mcp_servers: (state.mcp_servers || []).map((s) =>
        s.url === url ? { ...s, enabled: !s.enabled } : s,
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
  setMessageWindowSize: (size) =>
    set((state) => ({
      model_settings: { ...state.model_settings, message_window_size: size },
    })),
  setEnableParallelTools: (enabled) =>
    set((state) => ({
      model_settings: { ...state.model_settings, enable_parallel_tools: enabled },
    })),
  setEnablePerformanceMetrics: (enabled) =>
    set((state) => ({
      model_settings: { ...state.model_settings, enable_performance_metrics: enabled },
    })),
  
  // Dynamic Tool Selection (Week 3)
  setEnableDynamicTools: (enabled: boolean) =>
    set((state) => ({
      model_settings: { ...state.model_settings, enable_dynamic_tools: enabled },
    })),
  setToolSelectionStrategy: (strategy: string) =>
    set((state) => ({
      model_settings: { ...state.model_settings, tool_selection_strategy: strategy },
    })),
  setToolSimilarityThreshold: (threshold: number) =>
    set((state) => ({
      model_settings: { ...state.model_settings, tool_similarity_threshold: threshold },
    })),
  setMaxToolsPerQuery: (max: number | null) =>
    set((state) => ({
      model_settings: { ...state.model_settings, max_tools_per_query: max },
    })),

  // Conversation Summarization (Week 3)
  setUseSummarization: (enabled: boolean) =>
    set((state) => ({
      model_settings: { ...state.model_settings, use_summarization: enabled },
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
              enabled: state.tool_options[name]?.enabled ?? true, // Use enabled from tool_options
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
  setAvailableExampleMCPServers: (servers) =>
    set({ available_example_mcp_servers: servers }),
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

  // theme settings
  theme: (typeof window !== "undefined" && localStorage.getItem("theme") === "dark") ? "dark" : "light",
  setTheme: (theme) => {
    set({ theme });
    if (typeof window !== "undefined") {
      localStorage.setItem("theme", theme);
      document.documentElement.classList.toggle("dark", theme === "dark");
    }
  },
  toggleTheme: () => {
    const newTheme = get().theme === "light" ? "dark" : "light";
    get().setTheme(newTheme);
  },

  // bulk
  getSettings: () => ({
    search_portals: get().search_portals || [],
    geoserver_backends: get().geoserver_backends,
    model_settings: get().model_settings,
    tools: get().tools,
    tool_options: get().tool_options,
    model_options: get().model_options,
    color_settings: get().color_settings,
    theme: get().theme,
    session_id: get().session_id,
  }),
  setSettings: (settings) =>
    set((state) => {
      const newState = {
        search_portals: settings.search_portals || [],
        geoserver_backends: settings.geoserver_backends,
        model_settings: settings.model_settings,
        tools: settings.tools,
        tool_options: settings.tool_options,
        model_options: settings.model_options,
        color_settings: settings.color_settings,
        theme: settings.theme || state.theme,
        session_id: state.session_id,
      };
      // Apply theme if changed
      if (settings.theme && settings.theme !== state.theme) {
        state.setTheme(settings.theme);
      }
      return newState;
    }),
}));

// Expose store to window for E2E testing
if (typeof window !== "undefined") {
  (window as any).useSettingsStore = useSettingsStore;
  console.log("[SettingsStore] Exposed to window for testing");
}
