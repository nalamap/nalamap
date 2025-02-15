// src/services/api.tsx

// Define the shape of the map context
export interface MapContext {
    selectedMap: string;
    // Add any other properties relevant to your map context
  }
  
  // Define the expected structure of the API response
  export interface ApiResponse {
    responseMessage: string;
    mapContext: MapContext;
  }
  
  // Define the structure of the API request payload
  export interface ApiRequest {
    message: string;
    context: MapContext;
  }
  
  // Base URL for your FastAPI backend
  const API_BASE_URL = 'http://localhost:8000/api'; // Update if needed
  
  /**
   * Sends a message and context to the FastAPI backend endpoint.
   *
   * @param request - Object containing a message and map context.
   * @returns A promise that resolves with the API response containing a response message and updated map context.
   */
  export async function sendMessageAndContext(request: ApiRequest): Promise<ApiResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/endpoint`, {  // Ensure your FastAPI endpoint matches this path
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(request)
      });
  
      if (!response.ok) {
        throw new Error(`Network response was not ok: ${response.statusText}`);
      }
  
      const data: ApiResponse = await response.json();
      return data;
    } catch (error) {
      console.error('Error calling backend API:', error);
      throw error;
    }
  }
  