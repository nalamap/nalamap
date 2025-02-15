// src/components/common/Header.tsx
import Link from 'next/link';
import Head from 'next/head';

const Header = () => {
  return (
    <>
    <Head>
      <title>GeoWeaverAI</title>
      <meta name="description" content="geospatial insights, with ease" />
    </Head>
    <header className="bg-gray-800 text-white p-2">
      <div className="container mx-auto flex justify-between items-center">
        <h1 className="text-l font-bold">ageoi</h1>
        <nav>
          <ul className="flex space-x-4">
            <li>
              <Link href="/">
              Home
              </Link>
            </li>
            <li>
              <Link href="/about">
                About
              </Link>
            </li>
            <li>
              <Link href="/contact">
                Contact
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </header>
    </>
  );
};

export default Header;
