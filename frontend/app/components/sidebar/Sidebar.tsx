"use client";

import Link from "next/link";
import Head from "next/head";
import { LogOut, Maximize, RefreshCcw, Settings, Home, Layers } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";
import { useChatInterfaceStore } from "../../stores/chatInterfaceStore";
import { useLayerStore } from "../../stores/layerStore";
import { useSettingsStore } from "../../stores/settingsStore";

type BrowserFullscreenElement = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void> | void;
  msRequestFullscreen?: () => Promise<void> | void;
};

type BrowserFullscreenDocument = Document & {
  webkitExitFullscreen?: () => Promise<void> | void;
  msExitFullscreen?: () => Promise<void> | void;
};

const toggleFullscreen = () => {
  const elem = document.documentElement as BrowserFullscreenElement;
  const browserDocument = document as BrowserFullscreenDocument;

  if (!document.fullscreenElement) {
    if (elem.requestFullscreen) {
      elem.requestFullscreen();
    } else if (elem.webkitRequestFullscreen) {
      elem.webkitRequestFullscreen(); // Safari
    } else if (elem.msRequestFullscreen) {
      elem.msRequestFullscreen(); // IE11
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if (browserDocument.webkitExitFullscreen) {
      browserDocument.webkitExitFullscreen(); // Safari
    } else if (browserDocument.msExitFullscreen) {
      browserDocument.msExitFullscreen(); // IE11
    }
  }
};

const handleReset = () => {
  if (
    !window.confirm(
      "Are you sure you want to reset the app? This will clear all chat history, layers, and settings."
    )
  ) {
    return;
  }

  try {
    // Clear chat interface store
    useChatInterfaceStore.getState().clearMessages();
    useChatInterfaceStore.getState().clearToolUpdates();
    useChatInterfaceStore.getState().clearStreamingMessage();
    useChatInterfaceStore.getState().setInput("");
    useChatInterfaceStore.getState().setGeoDataList([]);
    useChatInterfaceStore.getState().clearError();

    // Clear layer store
    useLayerStore.getState().resetLayers();

    // Reset settings
    useSettingsStore.getState().resetColorSettings();

    // Clear all localStorage (except items we want to preserve)
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key));

    // Reload the page to ensure clean state
    window.location.reload();
  } catch (error) {
    console.error("Error during reset:", error);
    alert("An error occurred while resetting the app. Please try refreshing the page.");
  }
};

export default function Sidebar({
  onLayerToggle,
  compact = false,
}: {
  onLayerToggle?: () => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleSignOut = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <>
      <Head>
        <title>NaLaMapAI</title>
        <meta name="description" content="geospatial insights, with ease" />
      </Head>
      <div className={`obsidian-nav ${compact ? "obsidian-nav-compact" : ""}`}>
        <div className="obsidian-nav-brand">
          <span className="obsidian-kicker">{compact ? "NM" : "NaLaMap"}</span>
          {!compact && <span className="obsidian-nav-brand-title">Command Rail</span>}
          {!compact && user?.email && (
            <span className="obsidian-nav-brand-copy">{user.email}</span>
          )}
        </div>
        {/* Home Icon */}
        <Link href="/map">
          <button
            className="obsidian-nav-button"
            title="Home"
          >
            <Home className="h-5 w-5 shrink-0" />
            <span className="obsidian-nav-button-label">Home</span>
          </button>
        </Link>
        {/* Layer Management Icon */}
        {onLayerToggle && (
          <button
            onClick={onLayerToggle}
            className="obsidian-nav-button"
            title="Layer Management"
          >
            <Layers className="h-5 w-5 shrink-0" />
            <span className="obsidian-nav-button-label">Layer Management</span>
          </button>
        )}
        {/* Sign out */}
        {user && (
          <button
            onClick={handleSignOut}
            className="obsidian-nav-button"
            title={`Sign out ${user.email}`}
          >
            <LogOut className="h-5 w-5 shrink-0" />
            <span className="obsidian-nav-button-label">Sign out</span>
          </button>
        )}

        {/* Fullscreen Icon */}
        <button
          onClick={toggleFullscreen}
          className="obsidian-nav-button"
          title="Fullscreen Mode"
        >
          <Maximize className="h-5 w-5 shrink-0" />
          <span className="obsidian-nav-button-label">Fullscreen Mode</span>
        </button>

        {/* Reset Icon */}
        <button
          onClick={handleReset}
          className="obsidian-nav-button"
          title="Reset App"
          data-testid="reset-button"
        >
          <RefreshCcw className="h-5 w-5 shrink-0" />
          <span className="obsidian-nav-button-label">Reset App</span>
        </button>

        {/* Settings Icon */}
        <Link href="/settings">
          <button
            className="obsidian-nav-button"
            title="Settings"
          >
            <Settings className="h-5 w-5 shrink-0" />
            <span className="obsidian-nav-button-label">Settings</span>
          </button>
        </Link>
      </div>
    </>
  );
}
