// src/components/common/Sidebar.tsx
import { useState } from 'react';
import Link from 'next/link';
import Head from 'next/head';
import { useMapContext } from '../../contexts/MapContext';

const Sidebar: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { mapType, toggleMapType } = useMapContext();

  const toggleSidebar = () => {
    setIsExpanded((prev) => !prev);
  };

  return (
    <>
      <Head>
        <title>GeoWeaverAI</title>
        <meta name="description" content="geospatial insights, with ease" />
      </Head>
      <aside
        className={`flex flex-col h-screen transition-all duration-300 text-white bg-second-primary ${isExpanded ? 'w-64' : 'w-20'
          }`}
      >
        {/* Profile/User Icon at the Top */}
        <div className="flex items-center justify-center p-4 border-b border-darkgreen-700">
          {/* Replace with your actual profile image or icon */}
          <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center text-blue-800 font-bold">
          </div>
        </div>

        {/* Main Navigation Section */}
        <nav className="flex flex-col flex-1">
          <div className="flex flex-col items-center">
            {/* Burger Toggle Button */}
            <button
              onClick={toggleSidebar}
              className="p-4 hover:bg-secondary-900 focus:outline-none"
            >
              <svg
                className="w-6 h-6 mx-auto"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                {isExpanded ? (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                )}
              </svg>
            </button>

            {/* History Button */}
            <button className="p-4 hover:bg-secondary-900 focus:outline-none">
              Last requests
            </button>
          </div>

          {/* Expanded Menu Items */}
          {isExpanded && (
            <div className="mt-4 flex flex-col space-y-2 items-center">
              <button
                onClick={toggleMapType}
                className="p-4 hover:bg-secondary-900 focus:outline-none"
              >
                Toggle Map
              </button>
              <Link className="p-4 hover:bg-secondary-900 focus:outline-none" href="/last-requests">
                Last Requests
              </Link>
              <Link className="p-4 hover:bg-secondary-900 focus:outline-none" href="/about">
                About
              </Link>
              <Link className="p-4 hover:bg-secondary-900 focus:outline-none" href="/contact">
                Contact
              </Link>
            </div>
          )}
        </nav>
      </aside>
    </>
  );
};

export default Sidebar;