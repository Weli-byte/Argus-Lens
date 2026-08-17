"use client";

import { useEffect, useRef, useCallback } from "react";
import { getWSClient } from "@/lib/ws-client";
import { useInferenceStore } from "@/store/inference-store";
import type { InferenceResult } from "@/types";
import { movingAverage } from "@/lib/utils";

const FPS_WINDOW = 30;

export function useInferenceStream() {
  const setResult = useInferenceStore((s) => s.setResult);
  const setFps = useInferenceStore((s) => s.setFps);
  const setFrameDropRate = useInferenceStore((s) => s.setFrameDropRate);
  const setStreaming = useInferenceStore((s) => s.setStreaming);
  const updateQueueStatus = useInferenceStore((s) => s.updateQueueStatus);
  const isStreaming = useInferenceStore((s) => s.isStreaming);
  const currentResult = useInferenceStore((s) => s.currentResult);
  const fps = useInferenceStore((s) => s.fps);
  const queueStatus = useInferenceStore((s) => s.queueStatus);
  const frameDropRate = useInferenceStore((s) => s.frameDropRate);

  const frameTimestamps = useRef<number[]>([]);
  const dropCountRef = useRef(0);
  const totalCountRef = useRef(0);

  const startStream = useCallback(
    (prompt: string, fpsTarget: number = 30) => {
      const client = getWSClient();
      client.send("start_stream", { prompt, fps_target: fpsTarget });
      setStreaming(true);
    },
    [setStreaming]
  );

  const stopStream = useCallback(() => {
    const client = getWSClient();
    client.send("stop_stream", {});
    setStreaming(false);
  }, [setStreaming]);

  useEffect(() => {
    const client = getWSClient();

    const unsubInference = client.on<InferenceResult>(
      "inference_result",
      (result) => {
        const now = Date.now();
        frameTimestamps.current.push(now);
        if (frameTimestamps.current.length > FPS_WINDOW) {
          frameTimestamps.current.shift();
        }

        // Calculate FPS from inter-frame timestamps
        if (frameTimestamps.current.length >= 2) {
          const times = frameTimestamps.current;
          const intervals: number[] = [];
          for (let i = 1; i < times.length; i++) {
            intervals.push(times[i] - times[i - 1]);
          }
          const avgInterval = movingAverage(intervals, FPS_WINDOW);
          setFps(avgInterval > 0 ? Math.round(1000 / avgInterval) : 0);
        }

        totalCountRef.current++;
        setResult(result);
      }
    );

    const unsubDrop = client.on<{ frame_id: string }>("frame_dropped", () => {
      dropCountRef.current++;
      const rate =
        totalCountRef.current > 0
          ? dropCountRef.current / totalCountRef.current
          : 0;
      setFrameDropRate(rate);
    });

    const unsubQueue = client.on("queue_status", (s) => {
      updateQueueStatus(s as Parameters<typeof updateQueueStatus>[0]);
    });

    return () => {
      unsubInference();
      unsubDrop();
      unsubQueue();
    };
  }, [setResult, setFps, setFrameDropRate, updateQueueStatus]);

  return { isStreaming, fps, currentResult, queueStatus, frameDropRate, startStream, stopStream };
}
