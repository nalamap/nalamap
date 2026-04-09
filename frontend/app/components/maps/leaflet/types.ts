export interface ParsedWmsLayer {
  baseUrl: string;
  layers: string;
  format: string;
  transparent: boolean;
}

export interface ParsedWmtsLayer {
  wmtsLegendUrl: string;
  wmsLegendUrl: string;
  layerName: string;
  originalUrl: string;
  workspace?: string;
  fullLayerName?: string;
  wmtsKvpBase?: string;
  version?: string;
}

export interface ParsedWcsLayer extends ParsedWmsLayer {
  legendUrl: string;
  originalUrl: string;
}
