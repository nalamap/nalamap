import { create } from 'zustand'

export interface GeoServerBackend {
    url: string
    username?: string
    password?: string
    enabled: boolean
}

export interface SearchPortal {
    url: string
    enabled: boolean
}

export interface ModelSettings {
    model_provider: string
    model_name: string
    max_tokens: number
    system_prompt: string
}

export interface ToolConfig {
    name: string
    enabled: boolean
    prompt_override: string
}

export interface SettingsSnapshot {
    active_tools: string[]
    search_portals: SearchPortal[]
    geoserver_backends: GeoServerBackend[]
    model_settings: ModelSettings
    tools: ToolConfig[]
}

interface SettingsState extends SettingsSnapshot {
    // Portal & Backend actions
    addPortal: (portal: string) => void
    removePortal: (portal: string) => void
    togglePortal: (url: string) => void
    addBackend: (backend: Omit<GeoServerBackend, 'enabled'>) => void
    removeBackend: (url: string) => void
    toggleBackend: (url: string) => void

    // Model actions
    setModelProvider: (provider: string) => void
    setModelName: (name: string) => void
    setMaxTokens: (tokens: number) => void
    setSystemPrompt: (prompt: string) => void

    // Tools actions
    addToolConfig: (name: string) => void
    removeToolConfig: (name: string) => void
    toggleToolConfig: (name: string) => void
    setToolPromptOverride: (name: string, override: string) => void

    // Available options
    available_tools: string[]
    setAvailableTools: (tools: string[]) => void
    available_search_portals: string[]
    setAvailableSearchPortals: (portals: string[]) => void
    available_model_providers: string[]
    setAvailableModelProviders: (providers: string[]) => void
    available_model_names: string[]
    setAvailableModelNames: (names: string[]) => void

    // Bulk
    getSettings: () => SettingsSnapshot
    setSettings: (settings: SettingsSnapshot) => void
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
    // initial state
    active_tools: ['search', 'geocode', 'geoprocess'],
    search_portals: [],
    geoserver_backends: [],
    model_settings: {
        model_provider: 'openai',
        model_name: 'gpt-4',
        max_tokens: 1024,
        system_prompt: ''
    },
    tools: [],

    // available options
    available_tools: [],
    available_search_portals: [],
    available_model_providers: [],
    available_model_names: [],

    // Portal & Backend
    addPortal: (portal) =>
        set((state) => ({
            search_portals: state.search_portals.some((p) => p.url === portal)
                ? state.search_portals
                : [...state.search_portals, { url: portal, enabled: true }],
        })),
    removePortal: (url) => set((state) => ({ search_portals: state.search_portals.filter((p) => p.url !== url) })),
    togglePortal: (url) =>
        set((state) => ({
            search_portals: state.search_portals.map((p) => (p.url === url ? { ...p, enabled: !p.enabled } : p)),
        })),
    addBackend: (backend) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.some((b) => b.url === backend.url)
                ? state.geoserver_backends
                : [...state.geoserver_backends, { ...backend, enabled: true }],
        })),
    removeBackend: (url) => set((state) => ({ geoserver_backends: state.geoserver_backends.filter((b) => b.url !== url) })),
    toggleBackend: (url) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.map((b) => (b.url === url ? { ...b, enabled: !b.enabled } : b)),
        })),

    // Model actions
    setModelProvider: (provider) => set((state) => ({ model_settings: { ...state.model_settings, model_provider: provider } })),
    setModelName: (name) => set((state) => ({ model_settings: { ...state.model_settings, model_name: name } })),
    setMaxTokens: (tokens) => set((state) => ({ model_settings: { ...state.model_settings, max_tokens: tokens } })),
    setSystemPrompt: (prompt) => set((state) => ({ model_settings: { ...state.model_settings, system_prompt: prompt } })),

    // Tools actions
    addToolConfig: (name) =>
        set((state) => ({ tools: state.tools.some((t) => t.name === name) ? state.tools : [...state.tools, { name, enabled: true, prompt_override: '' }] })),
    removeToolConfig: (name) => set((state) => ({ tools: state.tools.filter((t) => t.name !== name) })),
    toggleToolConfig: (name) =>
        set((state) => ({ tools: state.tools.map((t) => (t.name === name ? { ...t, enabled: !t.enabled } : t)) })),
    setToolPromptOverride: (name, override) =>
        set((state) => ({ tools: state.tools.map((t) => (t.name === name ? { ...t, prompt_override: override } : t)) })),

    // Available options setters
    setAvailableTools: (tools) => set({ available_tools: tools }),
    setAvailableSearchPortals: (portals) => set({ available_search_portals: portals }),
    setAvailableModelProviders: (providers) => set({ available_model_providers: providers }),
    setAvailableModelNames: (names) => set({ available_model_names: names }),

    // Bulk
    getSettings: () => ({
        active_tools: get().active_tools,
        search_portals: get().search_portals,
        geoserver_backends: get().geoserver_backends,
        model_settings: get().model_settings,
        tools: get().tools,
    }),
    setSettings: (settings) =>
        set(() => ({
            active_tools: settings.active_tools,
            search_portals: settings.search_portals,
            geoserver_backends: settings.geoserver_backends,
            model_settings: settings.model_settings,
            tools: settings.tools,
        })),
}))
