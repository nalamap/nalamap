import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: "standalone",
  
  // Allow Playwright to make cross-origin requests during testing  
  allowedDevOrigins: ['http://127.0.0.1:3000', 'http://localhost:3000'],
  
  // Increase body size limit for server actions to match nginx (100MB)
  experimental: {
    serverActions: {
      bodySizeLimit: '100mb'
    }
  }
};

export default nextConfig;
