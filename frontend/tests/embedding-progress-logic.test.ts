/**
 * Unit tests for embedding progress interpolation logic
 * 
 * This tests the core interpolation algorithm without UI dependencies
 */

import { test, expect } from '@playwright/test';

// Type definitions matching the actual implementation
interface InterpolatedProgress {
  encoded: number; // Baseline from real backend data
  displayEncoded: number; // Interpolated value for display
  percentage: number;
  velocity: number; // layers per second
  lastUpdate: number; // timestamp
}

interface EmbeddingStatus {
  total: number;
  encoded: number;
  percentage: number;
  state: string;
  in_progress: boolean;
  complete: boolean;
  error: string | null;
}

const DEFAULT_VELOCITY = 1.5;

/**
 * Simulates the fetchEmbeddingStatus update logic
 */
function updateInterpolatedProgress(
  prev: InterpolatedProgress | undefined,
  newStatus: EmbeddingStatus,
  prevEmbeddingStatus: EmbeddingStatus | undefined,
  now: number
): InterpolatedProgress {
  if (newStatus.state === "processing" && newStatus.in_progress) {
    if (prev && prev.lastUpdate) {
      const timeDelta = (now - prev.lastUpdate) / 1000; // seconds
      const prevRealEncoded = prevEmbeddingStatus?.encoded || prev.encoded;
      const layersDelta = newStatus.encoded - prevRealEncoded;
      const velocity = timeDelta > 0 && layersDelta > 0 ? layersDelta / timeDelta : 0;

      const newVelocity = velocity > 0 
        ? velocity 
        : (prev.velocity > 0 ? prev.velocity : DEFAULT_VELOCITY);

      return {
        encoded: newStatus.encoded,
        displayEncoded: newStatus.encoded,
        percentage: newStatus.percentage,
        velocity: newVelocity,
        lastUpdate: now,
      };
    } else {
      return {
        encoded: newStatus.encoded,
        displayEncoded: newStatus.encoded,
        percentage: newStatus.percentage,
        velocity: DEFAULT_VELOCITY,
        lastUpdate: now,
      };
    }
  } else {
    return {
      encoded: newStatus.encoded,
      displayEncoded: newStatus.encoded,
      percentage: newStatus.percentage,
      velocity: 0,
      lastUpdate: now,
    };
  }
}

/**
 * Simulates the animation frame update logic
 */
function animateProgress(
  interp: InterpolatedProgress,
  status: EmbeddingStatus,
  now: number
): InterpolatedProgress {
  if (
    status &&
    status.state === "processing" &&
    status.in_progress &&
    interp.velocity > 0
  ) {
    const timeSinceRealUpdate = (now - interp.lastUpdate) / 1000;
    const predictedProgress = interp.encoded + interp.velocity * timeSinceRealUpdate;
    const cappedProgress = Math.min(predictedProgress, status.total);
    const cappedPercentage = status.total > 0 ? (cappedProgress / status.total) * 100 : 0;

    return {
      encoded: interp.encoded, // Keep baseline
      displayEncoded: cappedProgress,
      percentage: Math.min(cappedPercentage, 99.9),
      velocity: interp.velocity,
      lastUpdate: interp.lastUpdate,
    };
  }
  return interp;
}

test.describe('Embedding Progress Interpolation Logic', () => {
  test('should maintain linear interpolation without backward jumps', () => {
    const url = 'https://test.com';
    let interpolated: InterpolatedProgress | undefined;
    let embeddingStatus: EmbeddingStatus | undefined;

    // T=0: Initial update - 0 layers encoded
    let now = Date.now();
    const status1: EmbeddingStatus = {
      total: 100,
      encoded: 0,
      percentage: 0,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status1, embeddingStatus, now);
    embeddingStatus = status1;

    expect(interpolated.encoded).toBe(0);
    expect(interpolated.displayEncoded).toBe(0);
    expect(interpolated.velocity).toBe(DEFAULT_VELOCITY);

    // T=5000ms: Simulate 5 seconds of animation (should predict ~7.5 layers at 1.5/sec)
    now += 5000;
    interpolated = animateProgress(interpolated, embeddingStatus, now);
    
    const predictedAt5s = interpolated.displayEncoded;
    expect(predictedAt5s).toBeGreaterThan(5); // Should have progressed
    expect(predictedAt5s).toBeLessThan(10); // But not too much
    expect(interpolated.encoded).toBe(0); // Baseline unchanged

    // T=5000ms: Real update arrives - 15 layers encoded (3 layers/sec actual velocity)
    const status2: EmbeddingStatus = {
      total: 100,
      encoded: 15,
      percentage: 15,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status2, embeddingStatus, now);
    embeddingStatus = status2;

    expect(interpolated.encoded).toBe(15);
    expect(interpolated.displayEncoded).toBe(15); // Reset to real value
    expect(interpolated.velocity).toBe(3); // Measured velocity: 15 layers / 5 seconds
    expect(interpolated.lastUpdate).toBe(now);

    // T=7500ms: Animate 2.5 seconds later (should predict 15 + 3*2.5 = 22.5 layers)
    now += 2500;
    interpolated = animateProgress(interpolated, embeddingStatus, now);
    
    expect(interpolated.displayEncoded).toBeCloseTo(22.5, 1);
    expect(interpolated.encoded).toBe(15); // Baseline still 15

    // T=10000ms: Real update arrives - 30 layers (still 3 layers/sec)
    now += 2500;
    const status3: EmbeddingStatus = {
      total: 100,
      encoded: 30,
      percentage: 30,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status3, embeddingStatus, now);
    embeddingStatus = status3;

    // CRITICAL: Should not jump backward - display was at ~22.5-27.5, now resets to 30
    expect(interpolated.encoded).toBe(30);
    expect(interpolated.displayEncoded).toBe(30);
    // Velocity should remain ~3
    expect(interpolated.velocity).toBeGreaterThanOrEqual(2.5);
    expect(interpolated.velocity).toBeLessThanOrEqual(3.5);

    // T=12500ms: Animate 2.5 seconds later (should predict 30 + 3*2.5 = 37.5)
    now += 2500;
    interpolated = animateProgress(interpolated, embeddingStatus, now);
    
    expect(interpolated.displayEncoded).toBeCloseTo(37.5, 1);
    expect(interpolated.encoded).toBe(30); // Baseline unchanged
  });

  test('should not accelerate exponentially', () => {
    const url = 'https://test.com';
    let interpolated: InterpolatedProgress | undefined;
    let embeddingStatus: EmbeddingStatus | undefined;

    // Initial state
    let now = Date.now();
    const status: EmbeddingStatus = {
      total: 100,
      encoded: 0,
      percentage: 0,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status, embeddingStatus, now);
    embeddingStatus = status;

    // Track display values over time
    const displayValues: number[] = [interpolated.displayEncoded];

    // Simulate 30 animation frames at 100ms intervals
    for (let i = 0; i < 30; i++) {
      now += 100;
      interpolated = animateProgress(interpolated, embeddingStatus, now);
      displayValues.push(interpolated.displayEncoded);
    }

    // Check that progress is linear (no exponential growth)
    const velocities: number[] = [];
    for (let i = 1; i < displayValues.length; i++) {
      const velocity = (displayValues[i] - displayValues[i - 1]) / 0.1; // per second
      velocities.push(velocity);
    }

    // All velocities should be similar (within 20% of first velocity)
    const firstVelocity = velocities[0];
    const avgVelocity = velocities.reduce((a, b) => a + b, 0) / velocities.length;
    
    for (const v of velocities) {
      expect(Math.abs(v - avgVelocity)).toBeLessThan(avgVelocity * 0.2);
    }

    // Final display value after 3 seconds should be close to velocity * time
    const expectedProgress = interpolated.velocity * 3;
    expect(displayValues[displayValues.length - 1]).toBeCloseTo(expectedProgress, 0);
  });

  test('should handle velocity changes smoothly', () => {
    let interpolated: InterpolatedProgress | undefined;
    let embeddingStatus: EmbeddingStatus | undefined;

    // Phase 1: Slow processing (1 layer/sec)
    let now = Date.now();
    const status1: EmbeddingStatus = {
      total: 100,
      encoded: 0,
      percentage: 0,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status1, embeddingStatus, now);
    embeddingStatus = status1;

    now += 5000;
    const status2: EmbeddingStatus = {
      total: 100,
      encoded: 5, // 1 layer/sec
      percentage: 5,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status2, embeddingStatus, now);
    embeddingStatus = status2;

    expect(interpolated.velocity).toBeCloseTo(1, 1);

    // Phase 2: Processing speeds up (5 layers/sec)
    now += 5000;
    const status3: EmbeddingStatus = {
      total: 100,
      encoded: 30, // 25 layers in 5 seconds = 5 layers/sec
      percentage: 30,
      state: 'processing',
      in_progress: true,
      complete: false,
      error: null,
    };
    interpolated = updateInterpolatedProgress(interpolated, status3, embeddingStatus, now);
    embeddingStatus = status3;

    expect(interpolated.velocity).toBeCloseTo(5, 1);

    // Verify animation uses new velocity
    now += 2000;
    interpolated = animateProgress(interpolated, embeddingStatus, now);
    
    // Should predict 30 + 5*2 = 40
    expect(interpolated.displayEncoded).toBeCloseTo(40, 0);
  });
});
