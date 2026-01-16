"use client";

import Link from "next/link";
import Head from "next/head";
import { LogOut, Maximize, RefreshCcw, Settings, Home, Layers } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../context/AuthContext";
import { useChatInterfaceStore } from "../../stores/chatInterfaceStore";
import { useLayerStore } from "../../stores/layerStore";
import { useSettingsStore } from "../../stores/settingsStore";

const toggleFullscreen = () => {
  const elem = document.documentElement;

  if (!document.fullscreenElement) {
    if (elem.requestFullscreen) {
      elem.requestFullscreen();
    } else if ((elem as any).webkitRequestFullscreen) {
      (elem as any).webkitRequestFullscreen(); // Safari
    } else if ((elem as any).msRequestFullscreen) {
      (elem as any).msRequestFullscreen(); // IE11
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if ((document as any).webkitExitFullscreen) {
      (document as any).webkitExitFullscreen(); // Safari
    } else if ((document as any).msExitFullscreen) {
      (document as any).msExitFullscreen(); // IE11
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

export default function Sidebar({ onLayerToggle }: { onLayerToggle?: () => void }) {
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
      {/* Top Icon Section */}
      <div className="flex flex-col md:flex-col items-center justify-start md:py-4 py-2 md:space-y-4 space-y-3 h-full w-full bg-primary-800">
        {/* Home Icon */}
        <Link href="/map">
          <button
            className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
            title="Home"
          >
            <Home className="w-6 h-6 md:mr-0 mr-3" />
            <span className="md:hidden text-base">Home</span>
          </button>
        </Link>
        {/* Layer Management Icon */}
        {onLayerToggle && (
          <button
            onClick={onLayerToggle}
            className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
            title="Layer Management"
          >
            <Layers className="w-6 h-6 md:mr-0 mr-3" />
            <span className="md:hidden text-base">Layer Management</span>
          </button>
        )}
        {/* Sign out */}
        {user && (
          <button
            onClick={handleSignOut}
            className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
            title={`Sign out ${user.email}`}
          >
            <LogOut className="w-6 h-6 md:mr-0 mr-3" />
            <span className="md:hidden text-base">Sign out</span>
          </button>
        )}

        {/* Fullscreen Icon */}
        <button
          onClick={toggleFullscreen}
          className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
          title="Fullscreen Mode"
        >
          <Maximize className="w-6 h-6 md:mr-0 mr-3" />
          <span className="md:hidden text-base">Fullscreen Mode</span>
        </button>

        {/* Reset Icon */}
        <button
          onClick={handleReset}
          className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
          title="Reset App"
          data-testid="reset-button"
        >
          <RefreshCcw className="w-6 h-6 md:mr-0 mr-3" />
          <span className="md:hidden text-base">Reset App</span>
        </button>

        {/* Settings Icon */}
        <Link href="/settings">
          <button
            className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
            title="Settings"
          >
            <Settings className="w-6 h-6 md:mr-0 mr-3" />
            <span className="md:hidden text-base">Settings</span>
          </button>
        </Link>
      </div>
    </>
  );
}
