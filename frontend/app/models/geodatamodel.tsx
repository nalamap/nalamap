export interface ChatMessage {
  id?: string;
  type: "human" | "ai" | "system" | "tool" | "function";
  content: string;
  additional_kwargs?: Record<string, any>;
  tool_calls?: any;
}

export interface ProcessingMetadata {
  operation: string; // e.g., "buffer", "area", "overlay"
  crs_used: string; // e.g., "EPSG:32633"
  crs_name: string; // e.g., "WGS 84 / UTM zone 33N"
  auto_selected: boolean; // true if auto-selected, false if user-specified
  selection_reason?: string; // e.g., "Local extent - UTM zone 33N"
  origin_layers?: string[]; // Names of input layers used to generate this result
}

export interface LayerStyle {
  // Common stroke properties for all geometry types
  stroke_color?: string;
  stroke_weight?: number;
  stroke_opacity?: number;
  stroke_dash_array?: string; // e.g., "5,5" for dashed lines
  stroke_dash_offset?: number;

  // Fill properties for polygons and circles
  fill_color?: string;
  fill_opacity?: number;
  fill_pattern?: string; // For pattern fills (future enhancement)

  // Point/marker specific properties
  radius?: number;
  marker_symbol?: string; // For custom markers (future enhancement)

  // Line-specific properties
  line_cap?: string; // "round", "square", "butt"
  line_join?: string; // "round", "bevel", "miter"

  // Advanced visual properties
  blur?: number; // Gaussian blur effect
  shadow_color?: string; // Drop shadow color
  shadow_offset_x?: number; // Shadow offset
  shadow_offset_y?: number; // Shadow offset
  shadow_blur?: number; // Shadow blur radius

  // Animation properties (future enhancement)
  animation_duration?: number; // Animation duration in seconds
  animation_type?: string; // "pulse", "spin", "bounce", etc.

  // Conditional styling (future enhancement)
  style_conditions?: Record<string, any>; // For data-driven styling
}

export interface GeoDataObject {
  id: string;
  data_source_id: string;
  data_type: string;
  data_origin: string;

  data_source: string;
  data_link: string;
  name: string;

  title?: string;
  description?: string;
  llm_description?: string;
  score?: number;
  bounding_box?: string | number[]; // Can be WKT POLYGON string or array [minX, minY, maxX, maxY]
  layer_type?: string;
  properties?: Record<string, string>;

  visible?: boolean;
  selected?: boolean; // <— new flag
  style?: LayerStyle; // <— new style property
  // Optional integrity metadata for locally stored files
  sha256?: string;
  size?: number;
  // Optional processing metadata (CRS selection, operations applied)
  processing_metadata?: ProcessingMetadata;
}

export interface NaLaMapRequest {
  messages?: ChatMessage[];
  query?: string;
  geodata_last_results?: GeoDataObject[];
  geodata_layers?: GeoDataObject[];
  //global_geodata?: GeoDataObject[]
  options?: Record<string, unknown[]>;
}

export interface NaLaMapResponse {
  messages?: ChatMessage[];
  results_title?: string;
  geodata_results?: GeoDataObject[];
  geodata_layers?: GeoDataObject[];
  //global_geodata?: GeoDataObject[]
  options?: Record<string, unknown[]>;
}
