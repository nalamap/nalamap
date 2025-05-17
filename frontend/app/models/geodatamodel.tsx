export interface ChatMessage {
    id?: string
    type: 'human' | 'ai' | 'system' | 'tool' | 'function'
    content: string
    additional_kwargs?: Record<string, any>
    tool_calls?: any
}

export interface GeoDataObject {
    id: string
    data_source_id: string
    data_type: string
    data_origin: string
    data_source: string
    data_link: string
    name: string
    title?: string
    description?: string
    llm_description?: string
    score?: number
    bounding_box?: string | number[] // Can be WKT POLYGON string or array [minX, minY, maxX, maxY]
    layer_type?: string
    properties?: Record<string, string>
    visible?: boolean
    selected?: boolean;     // <— new flag
}

export interface GeoweaverRequest {
    messages?: ChatMessage[]
    query?: string
    geodata_last_results?: GeoDataObject[]
    geodata_layers?: GeoDataObject[]
    global_geodata?: GeoDataObject[]
    options?: Map<string, Set<string>>
}

export interface GeoweaverResponse {
    messages?: ChatMessage[]
    results_title?: string
    geodata_results?: GeoDataObject[]
    geodata_layers?: GeoDataObject[]
    global_geodata?: GeoDataObject[]
}
