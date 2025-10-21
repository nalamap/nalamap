// stores/chatInterfaceStore.ts
import { create } from "zustand";
import { ChatMessage, GeoDataObject } from "../models/geodatamodel";

export type ToolUpdate = {
  name: string;
  status: "running" | "complete" | "error";
  timestamp: number;
  error?: string;
  input?: any; // Tool input parameters
};

export type ChatInterfaceState = {
  // state fields
  input: string;
  messages: ChatMessage[];
  geoDataList: GeoDataObject[];
  loading: boolean;
  error: string;

  // streaming state
  toolUpdates: ToolUpdate[];
  streamingMessage: string;
  isStreaming: boolean;

  // getters
  getInput: () => string;
  getMessages: () => ChatMessage[];
  getGeoDataList: () => GeoDataObject[];
  getLoading: () => boolean;
  getError: () => string;
  getToolUpdates: () => ToolUpdate[];
  getStreamingMessage: () => string;
  getIsStreaming: () => boolean;

  // setters / mutators
  setInput: (input: string) => void;
  addMessage: (message: ChatMessage) => void;
  setMessages: (messages: ChatMessage[]) => void;
  clearMessages: () => void;
  setGeoDataList: (list: GeoDataObject[]) => void;
  addGeoData: (item: GeoDataObject) => void;
  setLoading: (flag: boolean) => void;
  setError: (error: string) => void;
  clearError: () => void;

  // streaming actions
  addToolUpdate: (tool: Omit<ToolUpdate, "timestamp">) => void;
  updateToolStatus: (
    toolName: string,
    status: ToolUpdate["status"],
    error?: string,
  ) => void;
  appendStreamingToken: (token: string) => void;
  setStreamingMessage: (message: string) => void;
  clearStreamingMessage: () => void;
  clearToolUpdates: () => void;
  setIsStreaming: (flag: boolean) => void;
};

export const useChatInterfaceStore = create<ChatInterfaceState>((set, get) => ({
  // initial state
  input: "",
  messages: [],
  geoDataList: [],
  loading: false,
  error: "",

  // streaming state
  toolUpdates: [],
  streamingMessage: "",
  isStreaming: false,

  // getters
  getInput: () => get().input,
  getMessages: () => get().messages,
  getGeoDataList: () => get().geoDataList,
  getLoading: () => get().loading,
  getError: () => get().error,
  getToolUpdates: () => get().toolUpdates,
  getStreamingMessage: () => get().streamingMessage,
  getIsStreaming: () => get().isStreaming,

  // mutators
  setInput: (input) => set({ input }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [] }),

  setGeoDataList: (list) => set({ geoDataList: list }),
  addGeoData: (item) =>
    set((state) => ({ geoDataList: [...state.geoDataList, item] })),

  setLoading: (flag) => set({ loading: flag }),

  setError: (error) => set({ error }),
  clearError: () => set({ error: "" }),

  // streaming actions
  addToolUpdate: (tool) =>
    set((state) => ({
      toolUpdates: [
        ...state.toolUpdates,
        { ...tool, timestamp: Date.now() },
      ],
    })),

  updateToolStatus: (toolName, status, error) =>
    set((state) => ({
      toolUpdates: state.toolUpdates.map((tool) =>
        tool.name === toolName
          ? { ...tool, status, error, timestamp: Date.now() }
          : tool,
      ),
    })),

  appendStreamingToken: (token) =>
    set((state) => ({
      streamingMessage: state.streamingMessage + token,
    })),

  setStreamingMessage: (message) => set({ streamingMessage: message }),

  clearStreamingMessage: () => set({ streamingMessage: "" }),

  clearToolUpdates: () => set({ toolUpdates: [] }),

  setIsStreaming: (flag) => set({ isStreaming: flag }),
}));

// Expose store for testing in development/test environments
if (typeof window !== "undefined") {
  (window as any).useChatInterfaceStore = useChatInterfaceStore;
}
