"use client";

import React, { useState, useCallback } from "react";
import { Search, Clock, Hash, ChevronDown, ChevronUp } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { SemanticResult } from "@/types";

interface SearchHistoryEntry {
  query: string;
  timestamp: number;
  resultCount: number;
}

export default function SemanticSearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [minScore, setMinScore] = useState(0.7);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SemanticResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<SearchHistoryEntry[]>([]);
  const [selectedResult, setSelectedResult] = useState<SemanticResult | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.semanticSearch({
        query: query.trim(),
        top_k: topK,
        min_similarity: minScore,
      });
      setResults(res);
      setHistory((prev) => [
        { query: query.trim(), timestamp: Date.now(), resultCount: res.length },
        ...prev.slice(0, 9),
      ]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [query, topK, minScore]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const scoreColor = (score: number) =>
    score >= 0.9 ? "text-green-400" : score >= 0.75 ? "text-cyan-400" : "text-amber-400";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-bold font-mono text-slate-100 tracking-wider">
          SEMANTIC SEARCH
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Vector similarity search over inference embeddings
        </p>
      </div>

      {/* Search bar */}
      <div className="rounded-xl border border-[#1E293B] bg-[#111827] p-4 space-y-3">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search embeddings… (Enter to search)"
              className="w-full rounded-lg border border-[#1E293B] bg-[#080B0F] pl-10 pr-4 py-2.5 text-sm font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/20"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-5 py-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-sm font-mono font-medium hover:bg-cyan-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Searching…" : "Search"}
          </button>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-slate-500">
          <label className="flex items-center gap-2">
            Top-K:
            <input
              type="number"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              min={1}
              max={100}
              className="w-16 rounded border border-[#1E293B] bg-[#080B0F] px-2 py-1 text-slate-300 focus:outline-none text-center"
            />
          </label>
          <label className="flex items-center gap-2">
            Min Score:
            <input
              type="number"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              min={0}
              max={1}
              step={0.05}
              className="w-20 rounded border border-[#1E293B] bg-[#080B0F] px-2 py-1 text-slate-300 focus:outline-none text-center"
            />
          </label>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-2.5 text-sm text-red-400 font-mono">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Results */}
        <div className="xl:col-span-2 space-y-2">
          {results.length > 0 ? (
            <>
              <p className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                {results.length} results
              </p>
              <div className="space-y-2">
                {results.map((r) => (
                  <div
                    key={r.id}
                    className={cn(
                      "rounded-lg border bg-[#0D1117] overflow-hidden transition-colors cursor-pointer",
                      selectedResult?.id === r.id
                        ? "border-cyan-500/40"
                        : "border-[#1E293B] hover:border-[#2D4A6E]"
                    )}
                    onClick={() =>
                      setSelectedResult(selectedResult?.id === r.id ? null : r)
                    }
                  >
                    <div className="flex items-start gap-3 p-3">
                      <Hash className="size-3.5 text-slate-600 mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] font-mono text-slate-500 truncate">
                            {r.id}
                          </span>
                          <span className={cn("text-xs font-mono font-bold shrink-0", scoreColor(r.similarity_score))}>
                            {(r.similarity_score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <p className="text-sm text-slate-200 mt-1 line-clamp-2">
                          {r.content}
                        </p>
                        {r.model_id && (
                          <p className="text-[10px] font-mono text-slate-600 mt-1">
                            {r.model_id}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setExpandedId(expandedId === r.id ? null : r.id);
                        }}
                        className="shrink-0 text-slate-600 hover:text-slate-400 transition-colors"
                      >
                        {expandedId === r.id ? (
                          <ChevronUp className="size-4" />
                        ) : (
                          <ChevronDown className="size-4" />
                        )}
                      </button>
                    </div>

                    {expandedId === r.id && r.embedding && (
                      <div className="px-3 pb-3 border-t border-[#1E293B] pt-2">
                        <p className="text-[10px] font-mono text-slate-500 mb-1">
                          Embedding ({r.embedding.length}d)
                        </p>
                        <p className="text-[10px] font-mono text-slate-600 break-all line-clamp-3">
                          [{r.embedding.slice(0, 8).map((v) => v.toFixed(4)).join(", ")}…]
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            !loading && (
              <div className="flex flex-col items-center justify-center rounded-xl border border-[#1E293B] bg-[#111827] py-16">
                <Search className="size-10 text-slate-700 mb-3" />
                <p className="text-sm text-slate-600">
                  Enter a query to search embeddings
                </p>
              </div>
            )
          )}
        </div>

        {/* Side: embedding inspector + history */}
        <div className="space-y-3">
          {selectedResult && (
            <div className="rounded-xl border border-cyan-500/30 bg-[#111827] p-4 space-y-3">
              <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Embedding Inspector
              </p>
              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">ID</span>
                  <span className="text-slate-300 truncate max-w-[120px]">{selectedResult.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Similarity</span>
                  <span className={scoreColor(selectedResult.similarity_score)}>
                    {(selectedResult.similarity_score * 100).toFixed(2)}%
                  </span>
                </div>
                {selectedResult.model_id && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Model</span>
                    <span className="text-slate-300">{selectedResult.model_id}</span>
                  </div>
                )}
                {selectedResult.embedding && (
                  <div className="pt-2 border-t border-[#1E293B]">
                    <p className="text-slate-500 mb-1.5">
                      Vector ({selectedResult.embedding.length}d)
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {selectedResult.embedding.slice(0, 16).map((v, i) => (
                        <span
                          key={i}
                          className="text-[9px] bg-slate-800 rounded px-1 py-0.5"
                          style={{
                            color: v > 0 ? "#34D399" : "#F87171",
                          }}
                        >
                          {v.toFixed(3)}
                        </span>
                      ))}
                      {selectedResult.embedding.length > 16 && (
                        <span className="text-[9px] text-slate-600">
                          +{selectedResult.embedding.length - 16} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Search history */}
          <div className="rounded-xl border border-[#1E293B] bg-[#111827] p-4 space-y-2">
            <p className="text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="size-3" /> Search History
            </p>
            {history.length > 0 ? (
              <div className="space-y-1.5">
                {history.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => setQuery(h.query)}
                    className="w-full text-left rounded-lg px-2.5 py-2 hover:bg-slate-800/50 transition-colors space-y-0.5"
                  >
                    <p className="text-xs font-mono text-slate-300 truncate">
                      {h.query}
                    </p>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-slate-600">
                        {new Date(h.timestamp).toLocaleTimeString()}
                      </span>
                      <span className="text-[10px] font-mono text-cyan-500">
                        {h.resultCount} results
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-600 text-center py-3">
                No searches yet
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
