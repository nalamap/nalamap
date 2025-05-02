"use client";

import MapSwitcher from "./MapSwitcher";

interface Props {
  layers: any[];
}

export default function MapComponent({ layers }: Props) {
  return (
    <div className="w-full h-full">
      <MapSwitcher layers={layers} />
    </div>
  );
}
