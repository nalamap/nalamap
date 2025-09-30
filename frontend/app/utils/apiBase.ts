// Utility to resolve the API base URL at runtime.
// Order of precedence:
// 1. Runtime injected window.__RUNTIME_CONFIG__ (single image multi-env deploys)
// 2. Build-time NEXT_PUBLIC_API_BASE_URL
// 3. Fallback to localhost dev default
export function getApiBase(): string {
  if (typeof window !== 'undefined') {
    const runtime = (window as any).__RUNTIME_CONFIG__?.NEXT_PUBLIC_API_BASE_URL;
    if (runtime && runtime.trim() !== '') return runtime;
  }
  if (process.env.NEXT_PUBLIC_API_BASE_URL && process.env.NEXT_PUBLIC_API_BASE_URL.trim() !== '') {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  return 'http://localhost:8000/api';
}

export function getUploadUrl(): string {
  if (typeof window !== 'undefined') {
    const runtime = (window as any).__RUNTIME_CONFIG__?.NEXT_PUBLIC_API_UPLOAD_URL;
    if (runtime && runtime.trim() !== '') return runtime;
  }
  if (process.env.NEXT_PUBLIC_API_UPLOAD_URL && process.env.NEXT_PUBLIC_API_UPLOAD_URL.trim() !== '') {
    return process.env.NEXT_PUBLIC_API_UPLOAD_URL;
  }
  return 'http://localhost:8000/api/upload';
}
