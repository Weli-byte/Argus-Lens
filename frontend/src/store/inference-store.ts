import { create } from "zustand";
import { produce } from "immer";
import type { InferenceResult, InferenceQueueStatus } from "@/types";

const MAX_HISTORY = 100;

interface InferenceState {
  currentResult: InferenceResult | null;
  resultHistory: InferenceResult[];
  queueStatus: InferenceQueueStatus | null;
  activePrompt: string;
  fps: number;
  isStreaming: boolean;
  frameDropRate: number;
  totalFrames: number;
  droppedFrames: number;
}

interface InferenceActions {
  setResult: (r: InferenceResult) => void;
  updateQueueStatus: (s: InferenceQueueStatus) => void;
  setPrompt: (p: string) => void;
  setStreaming: (v: boolean) => void;
  setFps: (fps: number) => void;
  setFrameDropRate: (rate: number) => void;
  incrementDropped: () => void;
  incrementTotal: () => void;
  reset: () => void;
}

const initial: InferenceState = {
  currentResult: null,
  resultHistory: [],
  queueStatus: null,
  activePrompt: "",
  fps: 0,
  isStreaming: false,
  frameDropRate: 0,
  totalFrames: 0,
  droppedFrames: 0,
};

export const useInferenceStore = create<InferenceState & InferenceActions>(
  (set) => ({
    ...initial,

    setResult: (r) =>
      set(
        produce((state: InferenceState) => {
          state.currentResult = r;
          state.resultHistory.push(r);
          if (state.resultHistory.length > MAX_HISTORY) {
            state.resultHistory.shift();
          }
          state.totalFrames++;
        })
      ),

    updateQueueStatus: (s) => set({ queueStatus: s }),
    setPrompt: (p) => set({ activePrompt: p }),
    setStreaming: (v) => set({ isStreaming: v }),
    setFps: (fps) => set({ fps }),
    setFrameDropRate: (rate) => set({ frameDropRate: rate }),

    incrementDropped: () =>
      set(
        produce((state: InferenceState) => {
          state.droppedFrames++;
        })
      ),

    incrementTotal: () =>
      set(
        produce((state: InferenceState) => {
          state.totalFrames++;
        })
      ),

    reset: () => set(initial),
  })
);
