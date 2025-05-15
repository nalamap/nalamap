import { create } from 'zustand'

interface SettingsState {
    active_tools: string[]
    search_portals: any[]
    addTool: (tool: string) => void
    removeTool: (tool: string) => void
    addPortal: (portal: any) => void
    removePortal: (portal: any) => void
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
    active_tools: ['search', 'geocode', 'geoprocess'],
    search_portals: [],

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
}))