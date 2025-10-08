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
  const sidebarWidth = useUIStore((s) => s.sidebarWidth);
  
  const [widths, setWidths] = useState<number[]>(getLayoutWidths());
  const [layerCollapsed, setLayerCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Set initial collapsed state based on screen size
  useEffect(() => {
    const isMobile = window.innerWidth < 768; // md breakpoint
    setLayerCollapsed(isMobile);
    setChatCollapsed(isMobile);
  }, []);
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
      {/* Mobile menu toggle - moved to top-right to avoid Leaflet controls */}
      <button
        className="md:hidden fixed top-4 right-4 z-[25] p-3 bg-primary-800 rounded-md shadow-lg hover:bg-primary-700"
        onClick={() => setMobileMenuOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="w-8 h-8 text-white" />
      </button>
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-[30]"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div 
            className="fixed top-0 right-0 bottom-0 w-full max-w-xs bg-primary-800 z-[31] text-white flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-primary-700">
              <h2 className="text-lg font-semibold">Menu</h2>
              <button
                className="p-1 hover:bg-primary-700 rounded"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <Sidebar onLayerToggle={() => {
                setLayerCollapsed(!layerCollapsed);
                setMobileMenuOpen(false);
              }} />
            </div>
          </div>
        </div>
      )}
      <div className="flex h-screen w-screen overflow-hidden">
        {/* Sidebar / Menu */}
        <div
          style={{ flexBasis: `${widths[0]}%` }}
          className="hidden md:flex flex-none relative bg-primary-800"
        >
          <Sidebar onLayerToggle={() => setLayerCollapsed(!layerCollapsed)} />
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
              className="absolute top-2 right-2 p-1 bg-primary-200 rounded shadow z-10 hover:bg-primary-300"
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
          <button
            className="fixed bottom-4 p-3 bg-primary-800 rounded-full shadow-lg z-[25] hover:bg-primary-700 touch-manipulation"
            style={{ left: `calc(1rem + ${sidebarWidth}vw)` }}
            onClick={() => setLayerCollapsed(false)}
            aria-label="Open layer management"
          >
            <Layers className="w-9 h-9 text-white" />
          </button>
        )}

        {/* Map panel */}
        <div
          className="flex-1 relative"
        >
          <MapComponent />
          {!chatCollapsed && (
            <div
              className="absolute top-0 right-0 bottom-0 w-1 hover:bg-primary-400 cursor-ew-resize z-10"
              onMouseDown={(e) => onHandleMouseDown(e, 2)}
            />
          )}
        </div>

        {/* Chat panel */}
        {!chatCollapsed ? (
          <div
            style={{ flexBasis: `${widths[3]}%` }}
            className="flex-none relative min-w-[200px] bg-primary-50"
          >
            <button
              className="absolute top-2 left-2 p-1 bg-primary-200 rounded shadow z-10 hover:bg-primary-300"
              onClick={() => setChatCollapsed(true)}
            >
              <ChevronRight className="w-4 h-4 text-primary-700" />
            </button>
            <AgentInterface />
          </div>
        ) : (
          <button
            className="fixed bottom-4 right-4 p-3 bg-primary-800 rounded-full shadow-lg z-[25] hover:bg-primary-700 touch-manipulation"
            onClick={() => setChatCollapsed(false)}
            aria-label="Open chat"
          >
            <MessageCircle className="w-9 h-9 text-white" />
          </button>
        )}
      </div>
    </>
  );
}
