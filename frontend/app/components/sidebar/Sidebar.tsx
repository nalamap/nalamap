"use client"

import { useState } from 'react';
import Link from 'next/link';
import Head from 'next/head';
import { User, Maximize, RefreshCcw, Settings, Home } from 'lucide-react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faLinkedin, faDiscord } from '@fortawesome/free-brands-svg-icons';

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
        <title>NaLaMapAI</title>
        <meta name="description" content="geospatial insights, with ease" />
      </Head>
      {/* Top Icon Section */}
      <div className="flex flex-col items-center justify-start py-4 space-y-4 h-full w-full">
        {/* Home Icon */}
        <Link href="/">
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="Home">
            <Home className="w-6 h-6" />
          </button>
        </Link>
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
        <Link href="/settings">
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="Settings">
            <Settings className="w-6 h-6" />
          </button>
        </Link>

        {/* LinkedIn Icon */}
        <a href="http://linkedin.nalamap.org" target="_blank" rel="noopener noreferrer">
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="LinkedIn">
            <FontAwesomeIcon 
              icon={faLinkedin} 
              style={{ width: '1.5rem', height: '1.5rem' }}
            />
          </button>
        </a>

        {/* Discord Icon */}
        <a href="http://discord.nalamap.org" target="_blank" rel="noopener noreferrer">
          <button className="hover:bg-secondary-900 p-2 rounded focus:outline-none text-white" title="Discord">
            <FontAwesomeIcon 
              icon={faDiscord} 
              style={{ width: '1.5rem', height: '1.5rem' }}
            />
          </button>
        </a>
      </div>
    </>
  );
};
