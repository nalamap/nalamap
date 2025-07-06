"use client";

import Sidebar from './components/sidebar/Sidebar';
import LayerManagement from './components/sidebar/LayerManagement';
import MapComponent from './components/maps/MapComponent';
import AgentInterface from './components/chat/AgentInterface';

interface Message {
  role: "user" | "agent";
  content: string;
}

export default function Home() {
  return (
    <div className="relative h-screen w-screen overflow-hidden">
      {/* Menubar Panel - left side, 4% width */}
      <div className="fixed left-0 top-0 bottom-0 w-[4%] z-[2]" style={{ backgroundColor: 'rgb(64, 64, 64)' }}>
        <Sidebar />
      </div>
      
      {/* Layer Management Panel - left 4%, 18% width */}
      <div className="fixed left-[4%] top-0 w-[18%] h-full" style={{ backgroundColor: 'rgb(255, 255, 255)' }}>
        <LayerManagement />
      </div>
      
      {/* Map Panel - center, 56% width */}
      <div className="fixed top-0 left-[22%] right-[22%] bottom-0 w-[56%]">
        <MapComponent />
      </div>
      
      {/* Chat Panel - right side, 22% width */}
      <div className="fixed right-0 top-0 w-[22%] h-full z-[2]" style={{ backgroundColor: 'rgb(255, 255, 255)' }}>
        <AgentInterface />
      </div>
    </div>
  );
}
