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
    rules: {
      // Downgraded pending nalamap/nalamap#238 (162 pre-existing
      // occurrences); keeps the frontend-quality CI gate green without
      // masking other rules. Mirrors the override landing on the S0
      // (deps_s0_ci_dependabot) branch's .eslintrc.json.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
]);