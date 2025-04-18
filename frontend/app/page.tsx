"use client";

import { useState } from "react";
import Sidebar from './components/Sidebar';
import LayerManagement from './components/LayerManagement';
import MapComponent from './components/MapComponent';
import AgentInterface from './components/AgentInterface';

export default function Home() {
  const [layers, setLayers] = useState<any[]>([]);
  const [conversation, setConversation] = useState<{ role: "user" | "agent"; content: string }[]>([]);

  return (
    <div className="flex h-screen">
      <Sidebar />
      <LayerManagement />
      <MapComponent layers={layers} />
      <AgentInterface
        onLayerSelect={(selected) => setLayers((prev) => [...prev, ...selected])}
        conversation={conversation}
        setConversation={setConversation}
      />
    </div>
  );
}
