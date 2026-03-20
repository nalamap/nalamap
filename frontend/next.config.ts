import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  
  // Allow Playwright to make cross-origin requests during testing  
  allowedDevOrigins: [
    'http://127.0.0.1:3000',
    'http://localhost:3000',
    'http://0.0.0.0:3000',
  ],
  
  // Disable ESLint during production builds (errors will still be caught in development)
  eslint: {
    ignoreDuringBuilds: true,
  },
  
  // Disable TypeScript type checking during production builds (use separate CI check)
  typescript: {
    ignoreBuildErrors: true,
  },
  
  // Keep the Next.js server-action parser aligned with the upload ceiling.
  experimental: {
    serverActions: {
      bodySizeLimit: '2000mb'
    }
  },
  
  // Rewrite /map to root page (nginx serves loading page at /, redirects to /map when ready)
  async rewrites() {
    return [
      {
        source: '/map',
        destination: '/',
      },
    ];
  },
};

export default nextConfig;
