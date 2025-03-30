'use client'

import { useState } from 'react';
import Link from 'next/link';
import Head from 'next/head';

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
        <div className="flex flex-col items-center py-4 space-y-4 border-b border-darkgreen-700">
          {/* Account Icon */}
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none" title="Account">
            <span className="text-2xl">👤</span>
          </button>

          {/* Fullscreen Icon */}
          <button
            onClick={toggleFullscreen}
            className="hover:bg-secondary-900 p-2 rounded focus:outline-none"
            title="Fullscreen Mode"
          >
            <span className="text-2xl">🖥️</span>
          </button>


          {/* Reset Icon */}
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none" title="Reset App">
            <span className="text-2xl">🔄</span>
          </button>

          {/* Settings Icon */}
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none" title="Settings">
            <span className="text-2xl">⚙️</span>
          </button>
        </div>
    </>
  );
};

