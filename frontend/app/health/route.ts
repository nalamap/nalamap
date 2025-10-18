import { NextResponse } from "next/server";

/**
 * Lightweight health check endpoint for Next.js frontend
 * Returns immediately with minimal processing - used by nginx health checks
 * and the loading page to determine when the frontend is ready
 */
export async function GET() {
  return NextResponse.json(
    { 
      status: "ok",
      service: "frontend",
      timestamp: Date.now()
    },
    {
      status: 200,
      headers: {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Content-Type": "application/json",
      },
    }
  );
}
