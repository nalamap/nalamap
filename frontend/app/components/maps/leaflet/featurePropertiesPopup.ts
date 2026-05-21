export const FEATURE_PROPERTIES_POPUP_OPTIONS = {
  maxWidth: 600,
  maxHeight: 400,
  autoPan: true,
  autoPanPadding: [50, 50] as [number, number],
  keepInView: true,
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatFeaturePropertyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function getFeatureTooltipValue(
  properties?: Record<string, unknown> | null,
): string | null {
  if (!properties) {
    return null;
  }

  const [firstValue] = Object.values(properties);
  if (firstValue === null || firstValue === undefined) {
    return null;
  }

  return formatFeaturePropertyValue(firstValue);
}

export function buildFeaturePropertiesPopupContent(
  properties?: Record<string, unknown> | null,
): string | null {
  if (!properties) {
    return null;
  }

  const rows = Object.entries(properties)
    .map(
      ([key, value]) => `
        <tr>
          <th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc; vertical-align: top;">${escapeHtml(key)}</th>
          <td style="padding: 4px; border-bottom: 1px solid #ccc; white-space: pre-wrap;">${escapeHtml(formatFeaturePropertyValue(value))}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <div style="padding: 4px; font-family: sans-serif;">
      <table style="border-collapse: collapse; width: 100%;">
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}
