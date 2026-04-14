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
  const setLayerPanelCollapsed = useUIStore((s) => s.setLayerPanelCollapsed);
  
  // Initialize with default values to avoid hydration mismatch
  const [widths, setWidths] = useState<number[]>([4, 18, 56, 22]);
  const [layerCollapsed, setLayerCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Load persisted widths after mount to avoid hydration mismatch
  useEffect(() => {
    setWidths(getLayoutWidths());
  }, [getLayoutWidths]);

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
        className="obsidian-mobile-trigger obsidian-mobile-only top-4 right-4"
        onClick={() => setMobileMenuOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="h-7 w-7" />
      </button>
      {mobileMenuOpen && (
        <div 
          className="obsidian-overlay"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div 
            className="obsidian-drawer"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="obsidian-panel-header">
              <div>
                <p className="obsidian-kicker mb-2">Navigation</p>
                <h2 className="obsidian-heading text-lg">Menu</h2>
              </div>
              <button
                className="obsidian-icon-button"
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
      <div className="obsidian-shell">
        {/* Sidebar / Menu */}
        <div
          style={{ flexBasis: `${widths[0]}%` }}
          className="obsidian-rail hidden md:flex flex-none"
        >
          <Sidebar compact onLayerToggle={() => setLayerCollapsed(!layerCollapsed)} />
          <div
            className="obsidian-resize-handle"
            onMouseDown={(e) => onHandleMouseDown(e, 0)}
          />
        </div>

        {/* Layer panel */}
        {!layerCollapsed ? (
          <div
            style={{ flexBasis: `${widths[1]}%` }}
            className="obsidian-surface-panel flex-none min-w-[200px]"
          >
            <button
              className="obsidian-icon-button absolute top-3 right-3 z-10"
              onClick={() => {
                setLayerCollapsed(true);
                setLayerPanelCollapsed(true);
              }}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <LayerManagement />
            <div
              className="obsidian-resize-handle"
              onMouseDown={(e) => onHandleMouseDown(e, 1)}
            />
          </div>
        ) : (
          <button
            className="obsidian-fab fixed bottom-4 p-3 touch-manipulation"
            style={{ left: `calc(1rem + ${sidebarWidth}vw)` }}
            onClick={() => {
              setLayerCollapsed(false);
              setLayerPanelCollapsed(false);
            }}
            aria-label="Open layer management"
          >
            <Layers className="h-8 w-8" />
          </button>
        )}

        {/* Map panel */}
        <div
          className="obsidian-main-panel obsidian-map-stage flex-1"
        >
          <MapComponent />
          {!chatCollapsed && (
            <div
              className="obsidian-resize-handle"
              onMouseDown={(e) => onHandleMouseDown(e, 2)}
            />
          )}
        </div>

        {/* Chat panel */}
        {!chatCollapsed ? (
          <div
            style={{ flexBasis: `${widths[3]}%` }}
            className="obsidian-surface-panel flex-none min-w-[200px]"
          >
            <button
              className="obsidian-icon-button absolute top-3 left-3 z-10"
              onClick={() => setChatCollapsed(true)}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <AgentInterface />
          </div>
        ) : (
          <button
            className="obsidian-fab fixed bottom-4 right-4 p-3 touch-manipulation"
            onClick={() => setChatCollapsed(false)}
            aria-label="Open chat"
          >
            <MessageCircle className="h-8 w-8" />
          </button>
        )}
      </div>
    </>
  );
}
