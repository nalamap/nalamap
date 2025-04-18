"use client";

import MapSwitcher from "./MapSwitcher";

interface Props {
  layers: any[];
}

export default function MapComponent({ layers }: Props) {
  return <MapSwitcher layers={layers} />;
}
