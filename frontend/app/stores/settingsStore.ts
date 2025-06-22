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

interface SettingsState {
    active_tools: string[]
    search_portals: SearchPortal[]
    geoserver_backends: GeoServerBackend[]
    addTool: (tool: string) => void
    removeTool: (tool: string) => void
    addPortal: (portal: string) => void
    removePortal: (portal: string) => void
    togglePortal: (url: string) => void
    addBackend: (backend: Omit<GeoServerBackend, 'enabled'>) => void
    removeBackend: (url: string) => void
    toggleBackend: (url: string) => void
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
    active_tools: ['search', 'geocode', 'geoprocess'],
    search_portals: [],
    geoserver_backends: [],

    addTool: (tool) =>
        set((state) => ({
            active_tools: state.active_tools.includes(tool)
                ? state.active_tools
                : [...state.active_tools, tool],
        })),

    removeTool: (tool) =>
        set((state) => ({
            active_tools: state.active_tools.filter((t) => t !== tool),
        })),

    addPortal: (portal) =>
        set((state) => ({
            search_portals: state.search_portals.some((p) => p.url === portal)
                ? state.search_portals
                : [...state.search_portals, { url: portal, enabled: true }],
        })),

    removePortal: (portal) =>
        set((state) => ({
            search_portals: state.search_portals.filter((p) => p.url !== portal),
        })),

    togglePortal: (url) =>
        set((state) => ({
            search_portals: state.search_portals.map((p) =>
                p.url === url ? { ...p, enabled: !p.enabled } : p
            ),
        })),

    addBackend: (backend) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.some((b) => b.url === backend.url)
                ? state.geoserver_backends
                : [...state.geoserver_backends, { ...backend, enabled: true }],
        })),

    removeBackend: (url) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.filter((b) => b.url !== url),
        })),

    toggleBackend: (url) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.map((b) =>
                b.url === url ? { ...b, enabled: !b.enabled } : b
            ),
        })),
}))
