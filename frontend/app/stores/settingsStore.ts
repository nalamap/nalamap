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

export interface ModelOption {
    name: string
    max_tokens: number
}

export interface ToolOption {
    default_prompt: string
    settings: Record<string, any>
}

export interface ToolConfig {
    name: string
    enabled: boolean
    prompt_override: string
}

export interface ModelSettings {
    model_provider: string
    model_name: string
    max_tokens: number
    system_prompt: string
}

export interface SettingsSnapshot {
    search_portals: SearchPortal[]
    geoserver_backends: GeoServerBackend[]
    model_settings: ModelSettings
    tools: ToolConfig[]
    tool_options: Record<string, ToolOption>
    model_options: Record<string, ModelOption[]>
}

export interface SettingsState extends SettingsSnapshot {
    // Initialization
    initialized: boolean
    initializeIfNeeded: () => Promise<void>
    initializeSettingsFromRemote: (opts: {
        system_prompt: string
        tool_options: Record<string, ToolOption>
        search_portals: string[]
        model_options: Record<string, ModelOption[]>
    }) => void

    // Portal & Backend actions
    addPortal: (portal: string) => void
    removePortal: (url: string) => void
    togglePortal: (url: string) => void
    addBackend: (backend: Omit<GeoServerBackend, 'enabled'>) => void
    removeBackend: (url: string) => void
    toggleBackend: (url: string) => void

    // Model actions
    setModelProvider: (provider: string) => void
    setModelName: (name: string) => void
    setMaxTokens: (tokens: number) => void
    setSystemPrompt: (prompt: string) => void

    // Tool config actions
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

    // Fetched options
    tool_options: Record<string, ToolOption>
    setToolOptions: (opts: Record<string, ToolOption>) => void
    model_options: Record<string, ModelOption[]>
    setModelOptions: (opts: Record<string, ModelOption[]>) => void

    // Bulk
    getSettings: () => SettingsSnapshot
    setSettings: (settings: SettingsSnapshot) => void
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
    // Initialization
    initialized: false,

    initializeIfNeeded: async () => {
        const state = get()
        if (state.initialized) return

        try {
            // API endpont
            const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

            const res = await fetch(`${API_BASE_URL}/settings/options`)
            if (!res.ok) throw new Error(res.statusText)
            const opts = await res.json()
            get().initializeSettingsFromRemote(opts)
            set({ initialized: true })
        } catch (err) {
            console.error('Failed to initialize settings', err)
        }
    },
    initializeSettingsFromRemote: (opts) => {
        const {
            setSystemPrompt,
            setAvailableTools,
            setToolOptions,
            addToolConfig,
            setAvailableSearchPortals,
            setAvailableModelProviders,
            setModelProvider,
            setModelOptions,
            setAvailableModelNames,
            setModelName,
            setMaxTokens,
            model_settings,
            available_tools,
            available_search_portals,
            model_options
        } = get()

        if ((!model_settings.system_prompt || model_settings.system_prompt === '') && opts.system_prompt) {
            setSystemPrompt(opts.system_prompt)
        }

        if (available_tools.length === 0) {
            const tools = Object.keys(opts.tool_options)
            setAvailableTools(tools)
            setToolOptions(opts.tool_options)
            tools.forEach(addToolConfig)
        }

        if (available_search_portals.length === 0) {
            setAvailableSearchPortals(opts.search_portals)
        }

        if (Object.keys(model_options).length === 0) {
            setModelOptions(opts.model_options)
            const providers = Object.keys(opts.model_options)
            setAvailableModelProviders(providers)
            const defaultProvider = providers[0]
            setModelProvider(defaultProvider)
            const models = opts.model_options[defaultProvider]
            const names = models.map(m => m.name)
            setAvailableModelNames(names)
            setModelName(names[0])
            setMaxTokens(models[0].max_tokens)
        }
    },
    // initial
    search_portals: [],
    geoserver_backends: [],
    model_settings: {
        model_provider: '',
        model_name: '',
        max_tokens: 0,
        system_prompt: ''
    },
    tools: [],

    // available
    available_tools: [],
    available_search_portals: [],
    available_model_providers: [],
    available_model_names: [],

    // fetched slices
    tool_options: {},
    model_options: {},

    // portal & backend
    addPortal: (portal) => set(state => ({
        search_portals: state.search_portals.some(p => p.url === portal)
            ? state.search_portals
            : [...state.search_portals, { url: portal, enabled: true }]
    })),
    removePortal: (url) => set(state => ({ search_portals: state.search_portals.filter(p => p.url !== url) })),
    togglePortal: (url) => set(state => ({
        search_portals: state.search_portals.map(p => p.url === url ? { ...p, enabled: !p.enabled } : p)
    })),

    addBackend: (backend) => set(state => ({
        geoserver_backends: state.geoserver_backends.some(b => b.url === backend.url)
            ? state.geoserver_backends
            : [...state.geoserver_backends, { ...backend, enabled: true }]
    })),
    removeBackend: (url) => set(state => ({ geoserver_backends: state.geoserver_backends.filter(b => b.url !== url) })),
    toggleBackend: (url) => set(state => ({
        geoserver_backends: state.geoserver_backends.map(b => b.url === url ? { ...b, enabled: !b.enabled } : b)
    })),

    // model
    setModelProvider: (provider) => set(state => ({ model_settings: { ...state.model_settings, model_provider: provider } })),
    setModelName: (name) => set(state => ({ model_settings: { ...state.model_settings, model_name: name } })),
    setMaxTokens: (tokens) => set(state => ({ model_settings: { ...state.model_settings, max_tokens: tokens } })),
    setSystemPrompt: (prompt) => set(state => ({ model_settings: { ...state.model_settings, system_prompt: prompt } })),

    // tools
    addToolConfig: (name) => set(state => ({
        tools: state.tools.some(t => t.name === name)
            ? state.tools
            : [...state.tools, { name, enabled: true, prompt_override: state.tool_options[name]?.default_prompt || '' }]
    })),
    removeToolConfig: (name) => set(state => ({ tools: state.tools.filter(t => t.name !== name) })),
    toggleToolConfig: (name) => set(state => ({
        tools: state.tools.map(t => t.name === name ? { ...t, enabled: !t.enabled } : t)
    })),
    setToolPromptOverride: (name, override) => set(state => ({
        tools: state.tools.map(t => t.name === name ? { ...t, prompt_override: override } : t)
    })),

    // available options
    setAvailableTools: (tools) => set({ available_tools: tools }),
    setAvailableSearchPortals: (portals) => set({ available_search_portals: portals }),
    setAvailableModelProviders: (providers) => set({ available_model_providers: providers }),
    setAvailableModelNames: (names) => set({ available_model_names: names }),

    // fetched slices
    setToolOptions: (opts) => set({ tool_options: opts }),
    setModelOptions: (opts) => set({ model_options: opts }),

    // bulk
    getSettings: () => ({
        search_portals: get().search_portals,
        geoserver_backends: get().geoserver_backends,
        model_settings: get().model_settings,
        tools: get().tools,
        tool_options: get().tool_options,
        model_options: get().model_options,
    }),
    setSettings: (settings) => set(() => ({
        search_portals: settings.search_portals,
        geoserver_backends: settings.geoserver_backends,
        model_settings: settings.model_settings,
        tools: settings.tools,
        tool_options: settings.tool_options,
        model_options: settings.model_options,
    })),
}))
