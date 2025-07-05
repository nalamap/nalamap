'use client'

import { useState } from 'react';
import Link from 'next/link';
import Head from 'next/head';
import { User, Maximize, RefreshCcw, Settings } from 'lucide-react';

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

export default function Sidebar() {
  return (
    <>
      <Head>
        <title>GeoWeaverAI</title>
        <meta name="description" content="geospatial insights, with ease" />
      </Head>
      {/* Top Icon Section */}
      <div className="flex flex-col items-center justify-start py-4 space-y-4 h-full w-full">
        {/* Account Icon */}
        <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="Account">
          <User className="w-6 h-6" />
        </button>

        {/* Fullscreen Icon */}
        <button
          onClick={toggleFullscreen}
          className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white"
          title="Fullscreen Mode"
        >
          <Maximize className="w-6 h-6" />
        </button>

        {/* Reset Icon */}
        <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="Reset App">
          <RefreshCcw className="w-6 h-6" />
        </button>

        {/* Settings Icon */}
        <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="Settings">
          <Settings className="w-6 h-6" />
        </button>
      </div>
    </>
  );
};
