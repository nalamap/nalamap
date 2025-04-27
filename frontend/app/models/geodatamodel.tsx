export interface ChatMessage {
    type: 'human' | 'ai' | 'system'
    content: string
    additional_kwargs?: Record<string, unknown>
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
    bounding_box?: any // string unterschiedliche Formate von bounding boxes
    layer_type?: string
    properties?: Record<string, string>
    visible?: boolean
    selected?: boolean;     // <— new flag
}

export interface GeoweaverRequest {
    messages?: ChatMessage[]
    query?: string
    geodata?: GeoDataObject[]
}

export interface GeoweaverResponse {
    messages?: ChatMessage[]
    query?: string
    geodata?: GeoDataObject[]
}
