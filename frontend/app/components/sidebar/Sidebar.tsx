"use client";

import { useState } from "react";
import Link from "next/link";
import Head from "next/head";
import { User, Maximize, RefreshCcw, Settings, Home, Layers } from "lucide-react";

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

export default function Sidebar({ onLayerToggle }: { onLayerToggle?: () => void }) {
  return (
    <>
      <Head>
        <title>NaLaMapAI</title>
        <meta name="description" content="geospatial insights, with ease" />
      </Head>
      {/* Top Icon Section */}
      <div className="flex flex-col md:flex-col items-center justify-start md:py-4 py-2 md:space-y-4 space-y-3 h-full w-full bg-primary-800">
        {/* Home Icon */}
        <Link href="/">
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
        {/* Account Icon */}
        <button
          className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
          title="Account"
        >
          <User className="w-6 h-6 md:mr-0 mr-3" />
          <span className="md:hidden text-base">Account</span>
        </button>

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
          className="hover:bg-secondary-800 rounded focus:outline-none text-white transition-colors cursor-pointer w-full md:w-auto flex items-center md:justify-center justify-start md:px-2 px-4 py-3 md:py-2"
          title="Reset App"
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
