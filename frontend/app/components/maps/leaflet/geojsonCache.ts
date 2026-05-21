import Logger from "../../../utils/logger";

interface CacheEntry {
  data: any;
  timestamp: number;
  size: number;
}

export class GeoJSONCache {
  private cache = new Map<string, CacheEntry>();
  private maxSize = 50 * 1024 * 1024; // 50MB cache limit
  private maxAge = 30 * 60 * 1000; // 30 minutes
  private currentSize = 0;

  set(url: string, data: any): void {
    // Estimate size (rough approximation)
    const size = JSON.stringify(data).length;

    // Evict old entries if cache is full
    while (this.currentSize + size > this.maxSize && this.cache.size > 0) {
      this.evictOldest();
    }

    const entry: CacheEntry = {
      data,
      timestamp: Date.now(),
      size,
    };

    this.cache.set(url, entry);
    this.currentSize += size;

    Logger.log(
      `[GeoJSONCache] Cached ${url} (${(size / 1024).toFixed(2)} KB). Cache size: ${(this.currentSize / 1024 / 1024).toFixed(2)} MB`,
    );
  }

  get(url: string): any | null {
    const entry = this.cache.get(url);
    if (!entry) return null;

    // Check if entry is expired
    if (Date.now() - entry.timestamp > this.maxAge) {
      this.delete(url);
      return null;
    }

    Logger.log(`[GeoJSONCache] Cache HIT for ${url}`);
    return entry.data;
  }

  delete(url: string): void {
    const entry = this.cache.get(url);
    if (entry) {
      this.cache.delete(url);
      this.currentSize -= entry.size;
      Logger.log(
        `[GeoJSONCache] Deleted ${url}. Cache size: ${(this.currentSize / 1024 / 1024).toFixed(2)} MB`,
      );
    }
  }

  private evictOldest(): void {
    let oldest: [string, CacheEntry] | null = null;

    for (const [url, entry] of this.cache.entries()) {
      if (!oldest || entry.timestamp < oldest[1].timestamp) {
        oldest = [url, entry];
      }
    }

    if (oldest) {
      this.delete(oldest[0]);
      Logger.log(`[GeoJSONCache] Evicted oldest entry: ${oldest[0]}`);
    }
  }

  clear(): void {
    this.cache.clear();
    this.currentSize = 0;
    Logger.log("[GeoJSONCache] Cache cleared");
  }

  getCacheStats(): { entries: number; size: number; maxSize: number } {
    return {
      entries: this.cache.size,
      size: this.currentSize,
      maxSize: this.maxSize,
    };
  }
}

export const geoJSONCache = new GeoJSONCache();

// Expose cache to window for debugging in development.
if (typeof window !== "undefined") {
  (window as any).geoJSONCache = geoJSONCache;
  Logger.log("[GeoJSONCache] Cache exposed to window.geoJSONCache for debugging");
}
