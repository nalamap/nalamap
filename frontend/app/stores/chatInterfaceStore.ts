// stores/chatInterfaceStore.ts
import { create } from "zustand";
import { ChatMessage, GeoDataObject } from "../models/geodatamodel";

export type ChatInterfaceState = {
  // state fields
  input: string;
  messages: ChatMessage[];
  geoDataList: GeoDataObject[];
  loading: boolean;
  error: string;

  // getters
  getInput: () => string;
  getMessages: () => ChatMessage[];
  getGeoDataList: () => GeoDataObject[];
  getLoading: () => boolean;
  getError: () => string;

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
};

export const useChatInterfaceStore = create<ChatInterfaceState>((set, get) => ({
  // initial state
  input: "",
  messages: [],
  geoDataList: [],
  loading: false,
  error: "",

  // getters
  getInput: () => get().input,
  getMessages: () => get().messages,
  getGeoDataList: () => get().geoDataList,
  getLoading: () => get().loading,
  getError: () => get().error,

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
}));
