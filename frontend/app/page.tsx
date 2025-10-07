"use client";

import React, { useState, useRef, useEffect } from "react";
import Sidebar from "./components/sidebar/Sidebar";
import LayerManagement from "./components/sidebar/LayerManagement";
import MapComponent from "./components/maps/MapComponent";
import AgentInterface from "./components/chat/AgentInterface";
import { useUIStore } from "./stores/uiStore";
import {
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Layers,
  MessageCircle,
} from "lucide-react";

export default function Home() {
  const getLayoutWidths = useUIStore((s) => s.getLayoutWidths);
  const setLayoutWidths = useUIStore((s) => s.setLayoutWidths);
  
  const [widths, setWidths] = useState<number[]>(getLayoutWidths());
  const [layerCollapsed, setLayerCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const dragInfo = useRef<{
    active: boolean;
    handleIndex: number;
    startX: number;
    initialWidths: number[];
  }>({ active: false, handleIndex: 0, startX: 0, initialWidths: [0, 0, 0, 0] });

  // Persist widths to store when they change
  useEffect(() => {
    setLayoutWidths(widths as [number, number, number, number]);
  }, [widths, setLayoutWidths]);

  const onMouseMove = (e: MouseEvent) => {
    if (!dragInfo.current.active) return;
    const deltaX = e.clientX - dragInfo.current.startX;
    const deltaPercent = (deltaX / window.innerWidth) * 100;
    const idx = dragInfo.current.handleIndex;
    const newWidths = [...dragInfo.current.initialWidths];
    newWidths[idx] = dragInfo.current.initialWidths[idx] + deltaPercent;
    newWidths[idx + 1] = dragInfo.current.initialWidths[idx + 1] - deltaPercent;
    // enforce minimum widths: layer and chat panels have fixed pixel-based minima
    const minPanelPx = 200;
    const minLayerPct = (minPanelPx / window.innerWidth) * 100;
    const minChatPct = minLayerPct;
    const defaultMinPct = 2;
    const minLeft = idx === 1 ? minLayerPct : defaultMinPct;
    const minRight = idx === 2 ? minChatPct : defaultMinPct;
    if (newWidths[idx] < minLeft) {
      newWidths[idx + 1] += newWidths[idx] - minLeft;
      newWidths[idx] = minLeft;
    }
    if (newWidths[idx + 1] < minRight) {
      newWidths[idx] += newWidths[idx + 1] - minRight;
      newWidths[idx + 1] = minRight;
    }
    setWidths(newWidths);
  };

  const onMouseUp = () => {
    dragInfo.current.active = false;
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
  };

  const onHandleMouseDown = (e: React.MouseEvent, idx: number) => {
    e.preventDefault();
    dragInfo.current = {
      active: true,
      handleIndex: idx,
      startX: e.clientX,
      initialWidths: [...widths],
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  return (
    <>
      {/* Mobile menu toggle */}
      <button
        className="md:hidden fixed top-4 right-4 z-20 p-2 bg-primary-200 rounded-full hover:bg-primary-300"
        onClick={() => setMobileMenuOpen(true)}
      >
        <Menu className="w-6 h-6 text-primary-700" />
      </button>
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-20">
          <div className="fixed top-0 left-0 bottom-0 w-64 bg-primary-800 z-30 text-white p-4">
            <button
              className="absolute top-4 right-4"
              onClick={() => setMobileMenuOpen(false)}
            >
              <X className="w-6 h-6" />
            </button>
            <Sidebar />
          </div>
        </div>
      )}
      <div className="flex h-screen w-screen overflow-hidden">
        {/* Sidebar / Menu */}
        <div
          style={{ flexBasis: `${widths[0]}%` }}
          className="hidden md:flex flex-none relative bg-primary-800"
        >
          <Sidebar />
          <div
            className="absolute top-0 right-0 bottom-0 w-1 hover:bg-primary-400 cursor-ew-resize z-10"
            onMouseDown={(e) => onHandleMouseDown(e, 0)}
          />
        </div>

        {/* Layer panel */}
        {!layerCollapsed ? (
          <div
            style={{ flexBasis: `${widths[1]}%` }}
            className="flex-none relative min-w-[200px] bg-primary-100"
          >
            <button
              className="absolute top-2 left-2 p-1 bg-primary-200 rounded shadow z-10 hover:bg-primary-300"
              onClick={() => setLayerCollapsed(true)}
            >
              <ChevronLeft className="w-4 h-4 text-primary-700" />
            </button>
            <LayerManagement />
            <div
              className="absolute top-0 right-0 bottom-0 w-1 hover:bg-primary-400 cursor-ew-resize z-10"
              onMouseDown={(e) => onHandleMouseDown(e, 1)}
            />
          </div>
        ) : (
          <div
            className="flex-none flex items-center justify-center w-12 bg-primary-200 hover:bg-primary-300 cursor-pointer"
            onClick={() => setLayerCollapsed(false)}
          >
            <Layers className="w-6 h-6 text-primary-700" />
          </div>
        )}

        {/* Map panel */}
        <div
          style={{
            flexBasis: `${widths[2] + (chatCollapsed ? widths[3] : 0)}%`,
          }}
          className="flex-none relative"
        >
          <MapComponent />
          <div
            className="absolute top-0 right-0 bottom-0 w-1 hover:bg-primary-400 cursor-ew-resize z-10"
            onMouseDown={(e) => onHandleMouseDown(e, 2)}
          />
        </div>

        {/* Chat panel */}
        {!chatCollapsed ? (
          <div
            style={{ flexBasis: `${widths[3]}%` }}
            className="flex-none relative min-w-[200px] bg-primary-50"
          >
            <button
              className="absolute top-2 right-2 p-1 bg-primary-200 rounded shadow z-10 hover:bg-primary-300"
              onClick={() => setChatCollapsed(true)}
            >
              <ChevronRight className="w-4 h-4 text-primary-700" />
            </button>
            <AgentInterface />
          </div>
        ) : (
          <button
            className="fixed bottom-4 right-4 p-3 bg-primary-200 rounded-full shadow z-20 hover:bg-primary-300"
            onClick={() => setChatCollapsed(false)}
          >
            <MessageCircle className="w-6 h-6 text-primary-700" />
          </button>
        )}
      </div>
    </>
  );
}
