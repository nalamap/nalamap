// src/pages/_app.tsx
import '../styles/globals.css';
import type { AppProps } from 'next/app';
import Header from '../components/common/Header';
import Sidebar from '../components/common/Sidebar';

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <>
      <Header />
      <Sidebar />
      <Component {...pageProps} />
    </>
  );
}

export default MyApp;