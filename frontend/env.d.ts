// Global runtime-injected config (populated by public/runtime-env.js at container start)
// This allows TypeScript to know about window.__RUNTIME_CONFIG__
export {};

declare global {
  interface Window {
    __RUNTIME_CONFIG__?: {
      NEXT_PUBLIC_API_BASE_URL?: string;
      NEXT_PUBLIC_BACKEND_URL?: string;
    };
  }
}
