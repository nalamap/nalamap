// Hook to call backend LLM for color suggestions
export async function suggestColor(name: string, metadata?: Record<string, any>): Promise<string> {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api';
  try {
    const res = await fetch(`${API_BASE_URL}/suggest_color`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, metadata }),
    });
    const data = await res.json();
    return data.color;
  } catch (err) {
    console.error('Error suggesting color:', err);
    // fallback to default pastel
    const letters = '89ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
      color += letters[Math.floor(Math.random() * letters.length)];
    }
    return color;
  }
}