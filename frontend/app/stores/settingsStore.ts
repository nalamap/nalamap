import { create } from 'zustand'

export interface GeoServerBackend {
    url: string
    username?: string
    password?: string
}

interface SettingsState {
    active_tools: string[]
    search_portals: string[]
    geoserver_backends: GeoServerBackend[]
    addTool: (tool: string) => void
    removeTool: (tool: string) => void
    addPortal: (portal: string) => void
    removePortal: (portal: string) => void
    addBackend: (backend: GeoServerBackend) => void
    removeBackend: (backend: GeoServerBackend) => void
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
            search_portals: state.search_portals.includes(portal)
                ? state.search_portals
                : [...state.search_portals, portal],
        })),

    removePortal: (portal) =>
        set((state) => ({
            search_portals: state.search_portals.filter((p) => p !== portal),
        })),

    addBackend: (backend) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.some((b) => b.url === backend.url)
                ? state.geoserver_backends
                : [...state.geoserver_backends, backend],
        })),

    removeBackend: (backend) =>
        set((state) => ({
            geoserver_backends: state.geoserver_backends.filter((b) => b.url !== backend.url),
        })),
}))