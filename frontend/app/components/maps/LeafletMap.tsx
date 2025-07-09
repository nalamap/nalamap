// app/components/maps/LeafletMap.tsx
"use client";

import dynamic from "next/dynamic";

// Only load the real LeafletMapClient in the browser
const LeafletMapClient = dynamic(
  () => import("./LeafletMapClient"),
  { ssr: false }
);

export default function LeafletMap(props: any) {
  return <LeafletMapClient {...props} />;
}
