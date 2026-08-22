"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  MessageSquare, 
  Send, 
  Trash2, 
  Bot, 
  User, 
  ShieldAlert, 
  RefreshCw,
  Heart,
  Droplet,
  Activity,
  Thermometer,
  Gauge,
  Flame,
  Brain,
  Info,
  Paperclip,
  X,
  Search,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Plus
} from "lucide-react";
import { useVitalStream } from "@/hooks/useVitalStream";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  imageUrl?: string | null;
  timestamp: string;
}

interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
}

interface MediaFile {
  type: "image" | "video";
  base64: string;
  mime_type: string;
  preview: string;
}
import { useLocale, pct } from "@/lib/i18n";

export default function AIChatPage() {
  const { t, locale } = useLocale();
  const { currentTelemetry } = useVitalStream();
  
  // State variables
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedMedia, setSelectedMedia] = useState<MediaFile | null>(null);
  
  // Feature toggles
  const [searchEnabled, setSearchEnabled] = useState(false);
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  
  // Collapsed thought tracking (by message ID)
  const [collapsedThoughts, setCollapsedThoughts] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load all sessions on mount
  useEffect(() => {
    fetchSessions();
  }, []);

  // When session changes, load messages
  useEffect(() => {
    if (currentSessionId) {
      loadSessionMessages(currentSessionId);
    } else {
      setMessages([
        {
          id: "welcome",
          sender: "assistant",
          text: t("Merhaba! Ben ArgusLens Biyonik Lens klinik asistanıyım. Sağlığınız, anlık vital değerleriniz veya tıbbi sorularınız hakkında benimle konuşabilirsiniz. Size nasıl yardımcı olabilirim?"),
          timestamp: new Date().toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    }
    // `t` bağımlılıkta: dil değişince karşılama mesajı da yeni dilde yazılır.
  }, [currentSessionId, t]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const fetchSessions = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8090/api/v1/chat/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        // Automatically select the most recent session if not selected
        if (data.length > 0 && !currentSessionId) {
          setCurrentSessionId(data[0].session_id);
        }
      }
    } catch (err) {
      console.error("Failed to load chat sessions:", err);
    }
  };

  const loadSessionMessages = async (sid: string) => {
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8090/api/v1/chat/session/${sid}`);
      if (res.ok) {
        const data = await res.json();
        const formatted = data.messages.map((m: any, idx: number) => {
          let text = "";
          let imageUrl = null;
          if (Array.isArray(m.content)) {
            const textPart = m.content.find((p: any) => p.type === "text");
            text = textPart ? textPart.text : "";
            const imgPart = m.content.find((p: any) => p.type === "image_url");
            imageUrl = imgPart ? imgPart.image_url?.url : null;
          } else {
            text = m.content;
          }
          return {
            id: `msg-${idx}-${Date.now()}`,
            sender: m.role === "user" ? "user" : "assistant",
            text: text,
            imageUrl: imageUrl,
            timestamp: ""
          };
        });
        
        if (formatted.length === 0) {
          setMessages([
            {
              id: "empty",
              sender: "assistant",
              text: "Bu sohbet oturumu boş. Sorularınızı yazarak başlayabilirsiniz.",
              timestamp: ""
            }
          ]);
        } else {
          setMessages(formatted);
        }
      }
    } catch (err) {
      console.error("Failed to load session messages:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateNewChat = () => {
    const newId = `session-${Math.random().toString(36).substr(2, 9)}`;
    setCurrentSessionId(newId);
    setMessages([
      {
        id: "welcome-new",
        sender: "assistant",
        text: "Yeni sohbet oturumu başladı. Sağlık durumunuz hakkında sorularınızı sorabilirsiniz.",
        timestamp: new Date().toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  };

  const handleDeleteSession = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Bu sohbeti kalıcı olarak silmek istiyor musunuz?")) {
      try {
        const res = await fetch(`http://127.0.0.1:8090/api/v1/chat/session/${sid}`, {
          method: "DELETE"
        });
        if (res.ok) {
          if (currentSessionId === sid) {
            setCurrentSessionId("");
          }
          fetchSessions();
        }
      } catch (err) {
        console.error("Failed to delete session:", err);
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    let type: "image" | "video" = "image";
    let mime = file.type;
    
    if (!mime && file.name) {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "webp" || ext === "gif") {
        type = "image";
        mime = `image/${ext === "jpg" ? "jpeg" : ext}`;
      } else if (ext === "mp4" || ext === "webm" || ext === "ogg" || ext === "mov") {
        type = "video";
        mime = `video/${ext === "mov" ? "quicktime" : ext}`;
      }
    } else {
      type = file.type.startsWith("image/") ? "image" : "video";
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      setSelectedMedia({
        type: type,
        base64: (reader.result as string).split(",")[1] || "",
        mime_type: mime || "image/jpeg",
        preview: reader.result as string
      });
    };
    reader.readAsDataURL(file);
    
    // Clear input value so selecting the same file again triggers onChange
    e.target.value = "";
  };

  const handleSendMessage = async (textToSend: string) => {
    if (!textToSend.trim() && !selectedMedia && loading) return;

    const actualSessionId = currentSessionId || `session-${Math.random().toString(36).substr(2, 9)}`;
    if (!currentSessionId) {
      setCurrentSessionId(actualSessionId);
    }

    const userMsgId = `msg-${Date.now()}`;
    const userMsg: Message = {
      id: userMsgId,
      sender: "user",
      text: textToSend,
      imageUrl: selectedMedia ? selectedMedia.preview : null,
      timestamp: new Date().toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setLoading(true);

    const payload = {
      message: textToSend,
      session_id: actualSessionId,
      search_enabled: searchEnabled,
      thinking_enabled: thinkingEnabled,
      media: selectedMedia ? {
        type: selectedMedia.type,
        base64: selectedMedia.base64,
        mime_type: selectedMedia.mime_type
      } : null
    };

    setSelectedMedia(null);

    try {
      const response = await fetch("http://127.0.0.1:8090/api/v1/chat/converse", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("Chat engine failed.");
      }

      const data = await response.json();
      
      const assistantMsg: Message = {
        id: `msg-${Date.now() + 1}`,
        sender: "assistant",
        text: data.reply,
        timestamp: new Date().toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit' })
      };

      setMessages((prev) => [...prev, assistantMsg]);
      fetchSessions(); // Refresh sidebar lists
    } catch (error) {
      console.error(error);
      const errorMsg: Message = {
        id: `msg-err-${Date.now()}`,
        sender: "assistant",
        text: "Üzgünüm, şu anda yanıt alamıyorum. Lütfen bağlantınızı kontrol edip tekrar deneyin.",
        timestamp: new Date().toLocaleTimeString("tr-TR", { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Helper parser for thought and markdown content
  const parseThoughtAndReply = (text: string) => {
    const match = text.match(/<thought>([\s\S]*?)<\/thought>/);
    if (match) {
      const thought = match[1].trim();
      const reply = text.replace(/<thought>[\s\S]*?<\/thought>/, "").trim();
      return { thought, reply };
    }
    return { thought: null, reply: text };
  };

  // Render markdown paragraphs, headings, bullet points and structured tables
  const renderFormattedText = (text: string) => {
    const lines = text.split("\n");
    const elements: React.JSX.Element[] = [];
    let tableRows: string[][] = [];
    let isInsideTable = false;

    lines.forEach((line, lineIdx) => {
      const cleanLine = line.trim();

      // Check for table structure e.g. | Column 1 | Column 2 |
      if (cleanLine.startsWith("|") && cleanLine.endsWith("|")) {
        isInsideTable = true;
        const cells = cleanLine.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        
        // Skip separator rows like |---|---|
        const isSeparator = cells.every(c => c.match(/^-+$/));
        if (!isSeparator) {
          tableRows.push(cells);
        }
        return;
      } else if (isInsideTable) {
        // Table ended, render it
        if (tableRows.length > 0) {
          elements.push(
            <div key={`table-${lineIdx}`} className="overflow-x-auto my-3 border border-[#1E293B] rounded-lg">
              <table className="w-full text-[11px] font-mono border-collapse bg-[#0D1117]/80">
                <thead>
                  <tr className="bg-[#1E293B] border-b border-[#1E293B] text-slate-300">
                    {tableRows[0].map((cell, idx) => (
                      <th key={`th-${idx}`} className="px-3 py-2 text-left font-bold">{cell}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.slice(1).map((row, rowIdx) => (
                    <tr key={`tr-${rowIdx}`} className="border-b border-[#161D2D] hover:bg-[#1E293B]/20 text-slate-300">
                      {row.map((cell, idx) => (
                        <td key={`td-${idx}`} className="px-3 py-2">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        tableRows = [];
        isInsideTable = false;
      }

      // Format headers
      if (cleanLine.startsWith("###")) {
        elements.push(
          <h4 key={lineIdx} className="text-xs font-bold text-[#00D4FF] uppercase tracking-wider mt-3 mb-1.5 font-mono">
            {cleanLine.replace("###", "").trim()}
          </h4>
        );
      } else if (cleanLine.startsWith("##")) {
        elements.push(
          <h3 key={lineIdx} className="text-sm font-bold text-slate-100 mt-4 mb-2 border-b border-[#1E293B] pb-1 font-mono">
            {cleanLine.replace("##", "").trim()}
          </h3>
        );
      } else if (cleanLine.startsWith("•") || cleanLine.startsWith("-")) {
        // Format bullet points
        const textVal = cleanLine.replace(/^[•-]\s*/, "");
        elements.push(
          <li key={lineIdx} className="list-disc ml-5 my-1 text-slate-300 pl-1">
            {renderInlineFormatting(textVal)}
          </li>
        );
      } else if (cleanLine.match(/^\d+\.\s/)) {
        // Format numbered list
        const textVal = cleanLine.replace(/^\d+\.\s*/, "");
        const num = cleanLine.match(/^\d+/)?.[0] || "";
        elements.push(
          <div key={lineIdx} className="flex gap-2 my-1 text-slate-300 pl-1">
            <span className="font-bold text-[#00D4FF]">{num}.</span>
            <span>{renderInlineFormatting(textVal)}</span>
          </div>
        );
      } else if (cleanLine) {
        // Regular paragraphs
        elements.push(
          <p key={lineIdx} className="my-1.5 leading-relaxed text-slate-300">
            {renderInlineFormatting(cleanLine)}
          </p>
        );
      }
    });

    // Render remaining table if file ends with table
    if (isInsideTable && tableRows.length > 0) {
      elements.push(
        <div key="table-end" className="overflow-x-auto my-3 border border-[#1E293B] rounded-lg">
          <table className="w-full text-[11px] font-mono border-collapse bg-[#0D1117]/80">
            <thead>
              <tr className="bg-[#1E293B] border-b border-[#1E293B] text-slate-300">
                {tableRows[0].map((cell, idx) => (
                  <th key={`th-${idx}`} className="px-3 py-2 text-left font-bold">{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.slice(1).map((row, rowIdx) => (
                <tr key={`tr-${rowIdx}`} className="border-b border-[#161D2D] hover:bg-[#1E293B]/20 text-slate-300">
                  {row.map((cell, idx) => (
                    <td key={`td-${idx}`} className="px-3 py-2">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    return elements;
  };

  // Helper for inline parsing of links [Text](URL) and bold formatting **text**
  const renderInlineFormatting = (text: string): React.ReactNode[] => {
    const linkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    while ((match = linkRegex.exec(text)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(...renderBoldFormatting(text.substring(lastIndex, matchIndex)));
      }
      const linkText = match[1];
      const linkUrl = match[2];
      parts.push(
        <a 
          key={`link-${matchIndex}`} 
          href={linkUrl} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="text-[#00D4FF] hover:underline font-bold"
        >
          {linkText}
        </a>
      );
      lastIndex = linkRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(...renderBoldFormatting(text.substring(lastIndex)));
    }

    return parts;
  };

  const renderBoldFormatting = (text: string): React.ReactNode[] => {
    const parts = text.split(/\*\*([\s\S]*?)\*\*/g);
    return parts.map((part, i) => {
      if (i % 2 === 1) {
        return <strong key={i} className="font-bold text-slate-100">{part}</strong>;
      }
      return part;
    });
  };

  const toggleThought = (msgId: string) => {
    setCollapsedThoughts(prev => ({
      ...prev,
      [msgId]: !prev[msgId]
    }));
  };

  const quickPrompts = [
    { label: t("🔍 Vital Durumumu Yorumla"), text: t("Şu anki vital değerlerimi analiz edip bana genel sağlık raporumu açıklar mısın?") },
    { label: t("⚠️ NEWS2 Risk Raporu"), text: t("NEWS2 skorum kaç ve bu tıbbi olarak ne anlama geliyor? Risk altında mıyım?") },
    { label: t("💡 Stres & Göz Basıncı Tavsiyesi"), text: t("Stres seviyem ve göz içi basıncım (IOP) ne durumda? Bunları kontrol altında tutmak için ne önerirsin?") }
  ];

  const currentVitals = currentTelemetry?.vitals;
  const news2 = currentTelemetry?.news2;
  const analysis = currentTelemetry?.analysis;

  return (
    <div className="flex flex-col md:flex-row gap-4 h-[calc(100vh-100px)] min-h-[550px] text-slate-100 p-2">
      
      {/* 1. Left Sidebar: Chat Sessions History list */}
      <div className="card-lift w-full md:w-64 border border-[rgba(0,212,255,0.12)] bg-gradient-to-b from-[#0D1117] to-[#111827] rounded-2xl overflow-hidden flex flex-col shrink-0">
        <div className="p-3">
          <button
            onClick={handleCreateNewChat}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl border border-[rgba(0,212,255,0.3)] text-cyan-400 text-xs font-bold tracking-wide cursor-pointer transition-all duration-300 hover:bg-cyan-500/10 hover:shadow-[0_0_16px_rgba(0,212,255,0.15)]"
          >
            <Plus className="size-4" />{t("YENİ SOHBET")}</button>
          <p className="text-xs text-slate-500 uppercase tracking-widest mt-4 px-1">{t("Geçmiş")}</p>
        </div>

        {/* Sessions list */}
        <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-1">
          {sessions.length === 0 ? (
            <p className="text-[10px] text-slate-600 text-center py-8">{t("Kayıtlı sohbet bulunamadı.")}</p>
          ) : (
            sessions.map((s) => (
              <div
                key={s.session_id}
                onClick={() => setCurrentSessionId(s.session_id)}
                className={`group flex items-center justify-between rounded-[10px] py-2.5 px-3 text-xs cursor-pointer transition-all duration-300 ${
                  currentSessionId === s.session_id
                    ? "bg-cyan-500/10 border-l-2 border-cyan-500 text-cyan-400"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                }`}
              >
                <div className="flex items-center gap-2 truncate pr-2">
                  <MessageSquare className="size-3.5 shrink-0" />
                  <span className="truncate text-[11px] font-semibold">{s.title}</span>
                </div>
                <button
                  onClick={(e) => handleDeleteSession(s.session_id, e)}
                  className="opacity-0 group-hover:opacity-100 hover:text-red-400 p-0.5 rounded cursor-pointer transition-all duration-300"
                  title={t("Sil")}
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 2. Middle Column: Main Chat Window (70%) */}
      <div className="flex-1 flex flex-col border border-[rgba(0,212,255,0.12)] bg-gradient-to-b from-[#0D1117] to-[#111827] rounded-2xl overflow-hidden">

        {/* Chat Header */}
        <div className="flex items-center justify-between border-b border-[rgba(0,212,255,0.12)] px-5 py-3.5">
          <div className="flex items-center gap-3">
            <div className="size-11 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center shrink-0">
              <Bot className="size-8 text-cyan-400" strokeWidth={1.75} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-wide">{t("ARGUSLENS KLİNİK ASISTAN")}</h2>
              <p className="text-xs text-cyan-400">{t("GPT-4o Medikal Zeka")}</p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-[10px] font-bold tracking-widest text-cyan-400 shadow-[0_0_12px_rgba(0,212,255,0.15)]">
            <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse" />{t("ONLINE")}</span>
        </div>

        {/* Disclaimer warning */}
        <div className="bg-amber-500/5 border-l-2 border-amber-500 px-4 py-2.5 flex items-start gap-2 text-[10px] text-amber-500/90">
          <Info className="size-3.5 shrink-0 mt-0.5" />
          <span>
            <strong>{t("Klinik Triage Uyarısı:")}</strong>{t("Yapay zeka asistanının tıbbi önerileri teşhis amacı taşımaz. Acil durumlarda 112 Acil Yardım hattını arayınız.")}</span>
        </div>

        {/* Message history flow with visual thought formatting */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => {
            const { thought, reply } = parseThoughtAndReply(msg.text);
            const isThoughtCollapsed = collapsedThoughts[msg.id] ?? true;

            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-[85%] animate-[msgIn_0.4s_ease] ${
                  msg.sender === "user" ? "ml-auto flex-row-reverse" : ""
                }`}
              >
                {/* Avatar Icon */}
                <div className={`size-7 rounded-full flex items-center justify-center shrink-0 border ${
                  msg.sender === "user" 
                    ? "bg-cyan-500/10 border-cyan-500/20 text-cyan-400" 
                    : "bg-purple-500/10 border-purple-500/20 text-purple-400"
                }`}>
                  {msg.sender === "user" ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
                </div>

                {/* Text Bubble */}
                <div className="flex flex-col space-y-1">
                  {msg.imageUrl && (
                    <div className="max-w-[200px] rounded-xl overflow-hidden border border-[#1E293B] bg-black mb-1 self-end shadow-[0_4px_12px_rgba(0,0,0,0.25)]">
                      <img src={msg.imageUrl} alt="Attached Media" className="w-full h-auto object-cover max-h-[150px]" />
                    </div>
                  )}
                  <div className={`p-3.5 text-xs leading-relaxed ${
                    msg.sender === "user"
                      ? "bg-cyan-500/15 border border-cyan-500/20 text-cyan-50 rounded-[16px_0_16px_16px]"
                      : "bg-slate-800/50 border border-[rgba(255,255,255,0.06)] text-slate-300 rounded-[0_16px_16px_16px]"
                  }`}>
                    
                    {/* Render Thought Block if present */}
                    {thought && (
                      <div className="mb-3 border-l-2 border-purple-500/40 bg-purple-500/5 p-2 rounded-r-lg">
                        <button
                          onClick={() => toggleThought(msg.id)}
                          className="flex items-center gap-1.5 text-[9px] font-mono text-purple-400 font-bold hover:text-purple-300 cursor-pointer focus:outline-none"
                        >
                          <Brain className="size-3" />
                          DÜŞÜNME SÜRECİ (CO-T)
                          {isThoughtCollapsed ? <ChevronDown className="size-3" /> : <ChevronUp className="size-3" />}
                        </button>
                        {!isThoughtCollapsed && (
                          <div className="mt-2 text-[10px] text-slate-400 italic font-sans whitespace-pre-line leading-relaxed pr-2">
                            {thought}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Render rich Markdown content (tables, headings, lists) */}
                    <div>
                      {renderFormattedText(reply)}
                    </div>

                  </div>
                  {msg.timestamp && (
                    <span className={`text-xs text-slate-500 px-1 ${
                      msg.sender === "user" ? "text-right" : ""
                    }`}>
                      {msg.timestamp}
                    </span>
                  )}
                </div>

              </div>
            );
          })}

          {loading && (
            <div className="flex gap-3 max-w-[85%]">
              <div className="size-7 rounded-full bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center shrink-0">
                <Bot className="size-3.5" />
              </div>
              <div className="bg-slate-800/50 border border-[rgba(255,255,255,0.06)] p-3 rounded-[0_16px_16px_16px] text-xs text-slate-400 flex items-center gap-3 animate-[msgIn_0.4s_ease]">
                <span className="flex items-center gap-1">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="size-1.5 rounded-full bg-cyan-400"
                      style={{ animation: `typingDot 1.2s ease-in-out ${i * 0.2}s infinite` }}
                    />
                  ))}
                </span>{t("Klinik tıp veri tabanları ve vital veriler inceleniyor...")}</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Media Preview Box */}
        {selectedMedia && (
          <div className="px-4 py-2 border-t border-[rgba(255,255,255,0.06)] flex items-center gap-3">
            <div className="relative size-12 rounded border border-[#1E293B] overflow-hidden bg-black shrink-0">
              {selectedMedia.type === "image" ? (
                <img src={selectedMedia.preview} alt="Upload Preview" className="size-full object-cover" />
              ) : (
                <div className="size-full flex items-center justify-center text-[8px] font-mono text-slate-500">{t("VIDEO")}</div>
              )}
              <button
                onClick={() => setSelectedMedia(null)}
                className="absolute top-0 right-0 bg-red-500 text-white rounded-full p-0.5 cursor-pointer"
              >
                <X className="size-2.5" />
              </button>
            </div>
            <span className="text-[10px] font-mono text-slate-400">{t("Dosya yükleme sırasına eklendi")}</span>
          </div>
        )}

        {/* Quick Suggestions list */}
        <div className="px-4 py-2.5 border-t border-[rgba(255,255,255,0.06)] flex flex-wrap gap-2">
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(p.text)}
              disabled={loading}
              className="text-xs border border-slate-700 text-slate-400 hover:border-cyan-500 hover:text-cyan-400 px-3 py-1.5 rounded-[20px] cursor-pointer transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none"
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Feature toggles and controls */}
        <div className="px-4 py-2 border-t border-[rgba(255,255,255,0.06)] flex gap-4 text-[10px]">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input 
              type="checkbox"
              checked={thinkingEnabled}
              onChange={(e) => setThinkingEnabled(e.target.checked)}
              className="rounded border-[#1E293B] text-purple-600 focus:ring-purple-500 bg-[#080B0F]"
            />
            <span className="flex items-center gap-1 text-purple-400">
              <Brain className="size-3.5" /> {t("Derin Düşünme (CoT)")}
            </span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input 
              type="checkbox"
              checked={searchEnabled}
              onChange={(e) => setSearchEnabled(e.target.checked)}
              className="rounded border-[#1E293B] text-cyan-500 focus:ring-cyan-400 bg-[#080B0F]"
            />
            <span className="flex items-center gap-1 text-cyan-400">
              <Search className="size-3.5" />{t("Canlı Web Araştırması")}</span>
          </label>
        </div>

        {/* Message Input Section */}
        <div className="p-3 border-t border-[rgba(255,255,255,0.06)]">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept="image/*,video/*"
            className="hidden"
          />
          <div className="flex items-center gap-3 border border-[rgba(0,212,255,0.2)] rounded-[14px] px-4 py-3 bg-[#080B0F]/60 focus-within:border-cyan-400 focus-within:shadow-[0_0_16px_rgba(0,212,255,0.12)] transition-all duration-300">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              className="text-slate-500 hover:text-cyan-400 cursor-pointer disabled:opacity-50 transition-colors duration-300 shrink-0"
              title={t("Fotoğraf/Video Yükle")}
            >
              <Paperclip className="size-4" />
            </button>

            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage(inputText)}
              placeholder={t("Klinik hekime sorunuzu yazın...")}
              disabled={loading}
              className="flex-1 bg-transparent text-xs text-slate-100 placeholder-slate-500 focus:outline-none disabled:opacity-50"
            />
            <button
              onClick={() => handleSendMessage(inputText)}
              disabled={loading || (!inputText.trim() && !selectedMedia)}
              className="size-9 rounded-full bg-gradient-to-r from-cyan-500 to-sky-500 text-[#080B0F] flex items-center justify-center cursor-pointer disabled:opacity-40 disabled:pointer-events-none transition-all duration-300 hover:scale-105 hover:shadow-[0_0_16px_rgba(0,212,255,0.4)] shrink-0"
            >
              <Send className="size-4" />
            </button>
          </div>
        </div>

      </div>

      {/* 3. Right Sidebar: Live Vitals Context (30%) */}
      <div className="w-full md:w-80 flex flex-col space-y-3 shrink-0">
        
        {/* Connection health */}
        <div className="card-lift border border-[rgba(0,212,255,0.12)] bg-gradient-to-br from-[#0D1117] to-[#111827] rounded-2xl p-4 flex flex-col justify-between shrink-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">{t("Canlı Veri")}</span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-[9px] font-bold tracking-widest text-cyan-400">
              <span className="size-1.5 rounded-full bg-cyan-400 animate-pulse"></span>{t("ONLINE")}</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-3 rounded-lg bg-slate-800/30 px-3 py-2">{t("İletişim Kanalı:")}<span className="text-slate-300">{t("FastAPI WS Link (Live)")}</span>
          </div>
        </div>

        {/* Live Vitals metrics checklist */}
        <div className="card-lift border border-[rgba(0,212,255,0.12)] bg-gradient-to-b from-[#0D1117] to-[#111827] rounded-2xl p-4 flex-1 flex flex-col gap-2 overflow-y-auto">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest block border-b border-[rgba(255,255,255,0.06)] pb-2">{t("Anlık Klinik Bağlam")}</span>

          {currentVitals ? (
            <div className="space-y-2.5 py-1 text-[11px] font-mono">
              <div className="flex items-center justify-between border-b border-[#1E293B]/40 pb-1">
                <span className="text-slate-500 flex items-center gap-1"><Heart className="size-3 text-red-500" />{t("Nabız")}</span>
                <span className="text-red-400 font-bold">{currentVitals.heart_rate} bpm</span>
              </div>
              
              <div className="flex items-center justify-between border-b border-[#1E293B]/40 pb-1">
                <span className="text-slate-500 flex items-center gap-1"><Activity className="size-3 text-yellow-500" />{t("Tansiyon")}</span>
                <span className="text-yellow-400 font-bold">
                  {Math.round(currentVitals.systolic_bp)}/{Math.round(currentVitals.diastolic_bp)}
                </span>
              </div>

              <div className="flex items-center justify-between border-b border-[#1E293B]/40 pb-1">
                <span className="text-slate-500 flex items-center gap-1"><Droplet className="size-3 text-cyan-400" /> {t("Oksijen (SpO2)")}</span>
                <span className="text-cyan-400 font-bold">{pct(currentVitals.spo2, locale)}</span>
              </div>

              <div className="flex items-center justify-between border-b border-[#1E293B]/40 pb-1">
                <span className="text-slate-500 flex items-center gap-1"><Thermometer className="size-3 text-amber-500" />{t("Sıcaklık")}</span>
                <span className="text-amber-500 font-bold">{currentVitals.temperature} °C</span>
              </div>

              <div className="flex items-center justify-between border-b border-[#1E293B]/40 pb-1">
                <span className="text-slate-500 flex items-center gap-1"><Gauge className="size-3 text-[#00D4FF]" /> {t("Göz Basıncı (IOP)")}</span>
                <span className="text-[#00D4FF] font-bold">{currentVitals.eye_pressure} mmHg</span>
              </div>

              <div className="flex items-center justify-between border-b border-[#1E293B]/40 pb-1">
                <span className="text-slate-500 flex items-center gap-1"><Flame className="size-3 text-purple-400" /> {t("Stres (Kortizol)")}</span>
                <span className="text-purple-400 font-bold">{currentVitals.stress_level} mcg/dL</span>
              </div>
              
              {/* NEWS2 Summary badge */}
              <div className={`p-2.5 rounded-lg border mt-2 flex flex-col gap-1 ${
                (news2?.score ?? 0) >= 7 
                  ? "bg-red-500/10 border-red-500/20 text-red-400" 
                  : (news2?.score ?? 0) >= 5 
                    ? "bg-orange-500/10 border-orange-500/20 text-orange-400" 
                    : "bg-green-500/10 border-green-500/20 text-green-400"
              }`}>
                <div className="flex justify-between font-bold text-[10px]">
                  <span>{t("NEWS2 SCORE")}</span>
                  <span>{news2?.score ?? 0} ({t(news2?.status ?? "NORMAL")})</span>
                </div>
                <div className="text-[8px] text-slate-400 uppercase">
                  {t("AI Risk Seviyesi:")}{" "}
                  {pct(((analysis?.risk_score ?? 0) * 100).toFixed(0), locale)}
                </div>
              </div>

              <p className="text-[9px] text-slate-500 leading-normal bg-[#080B0F] p-2 rounded border border-[#1E293B] mt-2">{t("* Asistan, mesajlarınızı yanıtlarken yukarıda yer alan telemetri verilerini tıbbi karar mekanizmalarına RAG ile dahil eder.")}</p>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-[11px] py-10 gap-3">
              <span className="size-10 rounded-full border-2 border-cyan-500/50 border-t-transparent animate-spin opacity-50" />{t("Sinyal bekleniyor...")}</div>
          )}

        </div>

      </div>

    </div>
  );
}
