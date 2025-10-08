/**
 * Logging utility for development and production environments
 * Automatically suppresses logs in production unless explicitly enabled
 */

const isDevelopment = process.env.NODE_ENV === "development";
const isTest = process.env.NODE_ENV === "test";

// Allow force-enabling logs in production via environment variable
const forceLogging = process.env.NEXT_PUBLIC_ENABLE_LOGGING === "true";

const shouldLog = isDevelopment || isTest || forceLogging;

export class Logger {
  /**
   * Log general information (development only)
   */
  static log(...args: any[]): void {
    if (shouldLog) {
      console.log(...args);
    }
  }

  /**
   * Log warnings (always shown, but can be configured)
   */
  static warn(...args: any[]): void {
    if (shouldLog) {
      console.warn(...args);
    }
  }

  /**
   * Log errors (always shown in all environments)
   */
  static error(...args: any[]): void {
    // Always show errors, even in production
    console.error(...args);
  }

  /**
   * Log debug information (development only)
   */
  static debug(...args: any[]): void {
    if (isDevelopment) {
      console.debug(...args);
    }
  }

  /**
   * Log with custom prefix for component identification
   */
  static component(componentName: string, ...args: any[]): void {
    if (shouldLog) {
      console.log(`[${componentName}]`, ...args);
    }
  }

  /**
   * Log performance metrics (development only)
   */
  static perf(label: string, startTime: number): void {
    if (isDevelopment) {
      const duration = Date.now() - startTime;
      console.log(`⏱️ ${label}: ${duration}ms`);
    }
  }

  /**
   * Group logs together (development only)
   */
  static group(label: string, callback: () => void): void {
    if (shouldLog) {
      console.group(label);
      callback();
      console.groupEnd();
    }
  }

  /**
   * Log table data (development only)
   */
  static table(data: any): void {
    if (shouldLog) {
      console.table(data);
    }
  }
}

// Export convenience functions
export const { log, warn, error, debug, component, perf, group, table } =
  Logger;

export default Logger;
