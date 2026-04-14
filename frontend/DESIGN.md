# Design System Specification: Geospatial Intelligence Framework
 
## 1. Overview & Creative North Star: "The Obsidian Lens"
This design system is built for the "Obsidian Lens" creative north star. In geospatial intelligence, clarity is paramount, but the interface must never feel like a spreadsheet. We move away from the "generic SaaS" aesthetic by adopting a high-end editorial approach.
 
The system treats the screen as a dark, infinite void—a deep obsidian canvas—where data is illuminated through layered transparency and precision optics. We break the rigid, boxed-in grid by utilizing intentional asymmetry, varying tonal depths, and glassmorphic overlays that allow the map (the "source of truth") to remain present even behind the UI.
 
---
 
## 2. Color & Tonal Architecture
The palette is rooted in a deep, nocturnal spectrum. We rely on the **Material Design 3 tonal system** but apply it with editorial restraint.
 
The system operates in a **dark** color mode, focusing on deep tones and illuminated data. The primary color, `#00dbf3`, supports interactive elements, while the secondary, `#00eefc`, offers complementary support. An accent is provided by the tertiary color, `#008df4`, and the overall foundation is set by a very dark neutral, `#10141a`.
 
### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning. Boundaries must be defined solely through:
1. **Tonal Shifts:** Placing a `surface_container_low` card against a `surface` background.
2. **Negative Space:** Using the spacing scale to create psychological "moats" between functional groups.
 
### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. Each layer deeper into the data should be visually "higher" or "brighter."
* **Level 0 (The Void):** `surface` (#10141a) – Used for the furthest background.
* **Level 1 (The Canvas):** `surface_container_low` (#181c22) – Main layout sections.
* **Level 2 (The Tool):** `surface_container` (#1c2026) – Floating sidebars or secondary panels.
* **Level 3 (The Object):** `surface_container_high` (#262a31) – Active cards and focused modules.
 
### The "Glass & Gradient" Rule
Floating map controls and temporary overlays must use **Glassmorphism**.
* **Recipe:** Background color `surface_variant` at 60% opacity + `backdrop-blur: 12px`.
* **Signature Textures:** Use a subtle linear gradient (from `primary` to `primary_container`) for main CTAs to simulate a "lit-from-within" glow rather than a flat fill.
 
---
 
## 3. Typography: Technical Elegance
We contrast the humanistic clarity of **Inter** with the geometric, high-tech personality of **Space Grotesk**.
 
*   **Display & Headlines (Space Grotesk):** Used for data titles, coordinates, and section headers. The tabular figures in Space Grotesk feel like instrumentation.
*   *Example:* `headline-lg` (2rem) for dashboard titles.
*   **UI & Metadata (Inter):** Used for all interactive elements, labels, and body text. Inter's high x-height ensures legibility over complex map backgrounds.
*   *Example:* `label-md` (0.75rem) for map legend details.
*   **Editorial Contrast:** Use `display-lg` (3.5rem) sparingly for high-impact metrics (e.g., "94% Accuracy") to create a visual anchor point in a sea of small-scale data.
 
---
 
## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are too "dirty" for a high-clarity intelligence platform. We use **Ambient Shadows** and **Tonal Lift**.
 
*   **The Layering Principle:** Instead of a shadow, place a `surface_container_highest` element on a `surface_dim` background. The contrast provides the lift.
*   **Ambient Shadows:** For elements that *must* float (e.g., contextual menus), use an ultra-diffused shadow: `box-shadow: 0 16px 40px rgba(0, 219, 233, 0.08)`. The shadow color is a low-opacity tint of `surface_tint`, not black.
*   **The "Ghost Border" Fallback:** If accessibility requires a border, use `outline_variant` at **15% opacity**. It should be felt, not seen.
 
---
 
## 5. Components & Interface Objects
 
### Buttons & Interaction
*   **Primary Action:** A gradient fill using `primary` to `primary_container`. No border. White or `on_primary` text.
*   **Secondary Action:** Ghost style. Transparent background with a `Ghost Border` and `primary` text.
*   **Interaction State:** On hover, primary buttons should increase their "glow" (increase shadow spread), not just change color.
 
### Advanced Map Controls
*   **Style:** Glassmorphic containers.
*   **Layout:** Vertical stacks positioned at the corners.
*   **Visuals:** Use `label-sm` for keyboard shortcuts (e.g., "Z" for zoom) rendered in `secondary` text.
 
### Project Cards & Experience Tiles
*   **Constraint:** Absolutely no divider lines.
*   **Separation:** Content within cards must be separated by 16px or 24px of white space.
*   **Header:** Use `title-md` in Space Grotesk for the project name.
*   **Footer:** A `surface_container_lowest` footer bar that houses action chips, creating a subtle internal "recessed" feel.
 
### Input Fields
*   **State:** Default state is a `surface_container_highest` fill with no border.
*   **Focus:** The `outline` token at 100% opacity only appears on focus, creating a "lens focus" effect.
*   **Typography:** All user-input text should be Inter `body-md`.
 
---
 
## 6. Shape and Form
The geometry of our UI elements contributes to the overall brand personality.
 
*   **Roundedness:** A moderate roundedness (level `2`) is applied to corners, offering a soft yet defined aesthetic. This avoids harsh edges while maintaining a clean appearance. For main containers, a larger radius of `0.75rem` (xl) is preferred, while small UI elements like checkboxes use a default `0.25rem` radius, creating a "nested" visual language.
 
## 7. Spacing
Spacing plays a crucial role in readability, visual hierarchy, and user experience.
 
*   **Spacing:** We utilize a **spacious** level of spacing (level `3`), providing an open and comfortable amount of whitespace within and between UI elements. This creates an editorial feel, ensuring a clean layout that prevents crowding.
 
---
 
## 8. Do’s and Don’ts
 
### Do
*   **Do** use asymmetrical layouts. A sidebar that doesn't reach the bottom of the screen feels more "bespoke" and less like a template.
*   **Do** use `primary_fixed_dim` for data visualization lines to ensure they "pop" against the dark background.
*   **Do** use `0.75rem` (xl) corner radius for main containers and `0.25rem` (default) for small UI elements like checkboxes to create a "nested" visual language.
 
### Don't
*   **Don't** use pure black (#000000). Use `surface` (#10141a) to maintain tonal depth and reduce eye strain.
*   **Don't** use 1px dividers. If you need to separate content, use a 4px gap of the background color or a shift in surface container tiers.
*   **Don't** use standard "drop shadows." Use the ambient, tinted shadows specified in Section 4.
*   **Don't** crowd the map. Ensure UI panels have at least 24px of "breathing room" from the edge of the viewport.