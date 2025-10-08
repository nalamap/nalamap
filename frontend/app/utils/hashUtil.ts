// Non-cryptographic 32-bit hash for quick UI keys, not for integrity
export function hashString(str: string): string {
  let hash = 0;
  if (str.length === 0) return hash.toString();
  for (let i = 0; i < str.length; i++) {
    const chr = str.charCodeAt(i);
    hash = (hash << 5) - hash + chr;
    hash |= 0; // convert to 32-bit int
  }
  return hash.toString();
}

// Convert ArrayBuffer of a hash to hex string
function toHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// Cryptographic SHA-256 of a File using Web Crypto API
export async function sha256OfFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", buf);
  return toHex(hash);
}

// Cryptographic SHA-256 of a string (UTF-8)
export async function sha256OfString(str: string): Promise<string> {
  const enc = new TextEncoder();
  const hash = await crypto.subtle.digest("SHA-256", enc.encode(str));
  return toHex(hash);
}
