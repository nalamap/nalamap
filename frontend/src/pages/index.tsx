// src/pages/index.tsx
import type { NextPage } from 'next';
import Head from 'next/head';

const Home: NextPage = () => {
  return (
    <>
      <div className="container mx-auto p-4">
        <h1 className="text-3xl font-bold">GeoWeaverAI</h1>
        <nav className="mt-4">
          <ul className="flex space-x-4">
            <li>
              About
            </li>
            <li>
              Contact
            </li>
          </ul>
        </nav>
      </div>
    </>
  );
};

export default Home;