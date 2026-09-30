import { defineConfig } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  {
    // `next lint` only ever linted the app/ (and, if present, pages/,
    // components/, lib/, src/) directories. Playwright specs under tests/
    // and e2e-tests/ were never part of that scope; keep it that way now
    // that `eslint .` would otherwise sweep the whole repo in.
    ignores: ["tests/**", "e2e-tests/**"],
  },
  {
    extends: [...nextCoreWebVitals, ...nextTypescript],
  },
]);