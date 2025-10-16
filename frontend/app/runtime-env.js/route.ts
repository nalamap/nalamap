import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";
import Logger from "../utils/logger";

export async function GET() {
  try {
    // Try to read from the runtime environment path first
    const runtimeEnvPath = process.env.RUNTIME_ENV_PATH;
    let filePath = "/app/public/runtime-env.js"; // default

    if (runtimeEnvPath) {
      filePath = runtimeEnvPath;
    }

    try {
      const content = await readFile(filePath, "utf-8");
      return new NextResponse(content, {
        headers: {
          "Content-Type": "application/javascript",
          "Cache-Control": "no-cache, no-store, must-revalidate",
        },
      });
    } catch (fileError) {
      // If file doesn't exist, create fallback config
      const fallbackConfig = `window.__RUNTIME_CONFIG__ = {
  NEXT_PUBLIC_API_BASE_URL: "${process.env.NEXT_PUBLIC_API_BASE_URL || "/api"}",
  NEXT_PUBLIC_API_UPLOAD_URL: "${process.env.NEXT_PUBLIC_API_UPLOAD_URL || "/api/upload"}",
  NEXT_PUBLIC_BACKEND_URL: "${process.env.NEXT_PUBLIC_BACKEND_URL || "http://backend:8000"}",
  NEXT_PUBLIC_EMBEDDING_INTERPOLATION_ENABLED: "${process.env.NEXT_PUBLIC_EMBEDDING_INTERPOLATION_ENABLED || "false"}",
  NEXT_PUBLIC_EMBEDDING_POLLING_INTERVAL_MS: "${process.env.NEXT_PUBLIC_EMBEDDING_POLLING_INTERVAL_MS || "3000"}",
  NEXT_PUBLIC_EMBEDDING_DEFAULT_VELOCITY: "${process.env.NEXT_PUBLIC_EMBEDDING_DEFAULT_VELOCITY || "3"}"
};`;

      return new NextResponse(fallbackConfig, {
        headers: {
          "Content-Type": "application/javascript",
          "Cache-Control": "no-cache, no-store, must-revalidate",
        },
      });
    }
  } catch (error) {
    Logger.error("Error serving runtime environment:", error);

    // Return minimal fallback
    const fallbackConfig = `window.__RUNTIME_CONFIG__ = {
  NEXT_PUBLIC_API_BASE_URL: "/api",
  NEXT_PUBLIC_API_UPLOAD_URL: "/api/upload", 
  NEXT_PUBLIC_BACKEND_URL: "http://backend:8000",
  NEXT_PUBLIC_EMBEDDING_INTERPOLATION_ENABLED: "false",
  NEXT_PUBLIC_EMBEDDING_POLLING_INTERVAL_MS: "3000",
  NEXT_PUBLIC_EMBEDDING_DEFAULT_VELOCITY: "3"
};`;

    return new NextResponse(fallbackConfig, {
      headers: {
        "Content-Type": "application/javascript",
        "Cache-Control": "no-cache, no-store, must-revalidate",
      },
    });
  }
}
