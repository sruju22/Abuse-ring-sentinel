import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  X,
  Send,
  RotateCcw,
  AlertTriangle,
  Bot,
  User,
  ShieldAlert,
  Clock,
  Network,
  ExternalLink,
  ChevronRight,
  Info,
  Key,
} from 'lucide-react';
import { api } from '../../services/api';

export default function InvestigationCopilot({
  isOpen,
  onClose,
  accountId,
  investigationMode = 'predictive',
  accountData = null,
  timelineData = null,
  onNavigateTab,
}) {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const [providerStatus, setProviderStatus] = useState(null);
  const [activeAccountContext, setActiveAccountContext] = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom on new messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  // Load provider status once
  useEffect(() => {
    api.copilot
      .getStatus()
      .then((res) => setProviderStatus(res))
      .catch((err) => console.error('Error fetching copilot status:', err));
  }, []);

  // When account or investigationMode changes, reset session and load initial brief
  useEffect(() => {
    if (!accountId) return;

    // Check if account or mode actually changed
    const contextKey = `${accountId}:${investigationMode}`;
    if (activeAccountContext === contextKey) return;

    setActiveAccountContext(contextKey);
    setMessages([]);
    setLoading(true);

    // Fetch suggested questions and initial brief in parallel
    Promise.all([
      api.copilot.getSuggestedQuestions(accountId, investigationMode),
      api.copilot.getBrief(accountId, investigationMode),
    ])
      .then(([questionsRes, briefRes]) => {
        setSuggestedQuestions(questionsRes.suggested_questions || []);
        if (briefRes && briefRes.response) {
          setMessages([
            {
              id: 'brief-' + Date.now(),
              role: 'assistant',
              content: briefRes.response,
              citations: briefRes.citations || [],
              isConfigError: briefRes.is_configuration_error || false,
            },
          ]);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error initializing Copilot for', accountId, err);
        setMessages([
          {
            id: 'err-' + Date.now(),
            role: 'assistant',
            content: `### Telemetry Connection Error\n\nCould not load automated brief for **${accountId}** (${err.message || 'Server error'}).`,
            citations: [],
            isError: true,
          },
        ]);
        setLoading(false);
      });
  }, [accountId, investigationMode]);

  // Send inquiry message
  const handleSendMessage = async (msgToSend = null) => {
    const text = (msgToSend !== null ? msgToSend : inputMessage).trim();
    if (!text || loading || !accountId) return;

    const userMsg = {
      id: 'usr-' + Date.now(),
      role: 'user',
      content: text,
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInputMessage('');
    setLoading(true);

    // Format previous turns for context preservation
    const historyPayload = messages
      .filter((m) => !m.isConfigError && !m.isError)
      .slice(-4)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }));

    try {
      const res = await api.copilot.chat({
        accountId,
        mode: investigationMode,
        message: text,
        history: historyPayload,
      });

      setMessages([
        ...newMessages,
        {
          id: 'ast-' + Date.now(),
          role: 'assistant',
          content: res.response,
          citations: res.citations || [],
          isConfigError: res.is_configuration_error || false,
        },
      ]);

      if (res.suggested_questions && res.suggested_questions.length > 0) {
        setSuggestedQuestions(res.suggested_questions);
      }
    } catch (err) {
      console.error('Error during copilot chat:', err);
      setMessages([
        ...newMessages,
        {
          id: 'err-' + Date.now(),
          role: 'assistant',
          content: `### Analysis Interrupted\n\nUnable to process query for **${accountId}**: ${err.message || 'Unknown network error'}.`,
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
    if (accountId) {
      setLoading(true);
      api.copilot
        .getBrief(accountId, investigationMode)
        .then((briefRes) => {
          if (briefRes && briefRes.response) {
            setMessages([
              {
                id: 'brief-' + Date.now(),
                role: 'assistant',
                content: briefRes.response,
                citations: briefRes.citations || [],
                isConfigError: briefRes.is_configuration_error || false,
              },
            ]);
          }
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  };

  const renderFormattedMarkdown = (text) => {
    if (!text) return null;

    // Split text by lines and parse standard markdown features
    const lines = text.split('\n');
    return (
      <div className="space-y-1 text-xs leading-relaxed text-[#252B29]">
        {lines.map((line, idx) => {
          const trimmed = line.trim();

          // Heading 3
          if (trimmed.startsWith('### ')) {
            return (
              <h4 key={idx} className="text-[10px] font-bold uppercase tracking-wider text-[#147D69] mt-2 mb-0.5 font-sans border-b border-[#E2E0D8]/60 pb-0.5 flex items-center gap-1">
                <span>{trimmed.replace('### ', '')}</span>
              </h4>
            );
          }

          // Bullet list items
          if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
            const rawContent = trimmed.replace(/^[-•]\s*/, '');
            return (
              <div key={idx} className="flex items-start gap-1.5 pl-0.5 py-0.5 text-[11px] text-[#3D4543]">
                <span className="text-[#147D69] font-black text-[12px] leading-none mt-0.5">•</span>
                <span
                  dangerouslySetInnerHTML={{
                    __html: formatInlineMarkdown(rawContent),
                  }}
                />
              </div>
            );
          }

          // Numbered list
          if (/^\d+\.\s/.test(trimmed)) {
            const num = trimmed.match(/^(\d+\.)\s/)[1];
            const rawContent = trimmed.replace(/^\d+\.\s/, '');
            return (
              <div key={idx} className="flex items-start gap-1.5 pl-0.5 py-0.5 text-[11px] text-[#3D4543]">
                <span className="font-mono text-[#147D69] font-bold text-[10px] mt-0.5">{num}</span>
                <span
                  dangerouslySetInnerHTML={{
                    __html: formatInlineMarkdown(rawContent),
                  }}
                />
              </div>
            );
          }

          // Code blocks / mono callouts
          if (trimmed.startsWith('```') || trimmed.endsWith('```')) {
            return null; // hide raw delimiter lines
          }

          // Blockquote
          if (trimmed.startsWith('> ')) {
            return (
              <div
                key={idx}
                className="pl-2 py-0.5 border-l-2 border-[#147D69] text-[10.5px] text-[#737A76] bg-[#F7F6F2] rounded-r my-1"
                dangerouslySetInnerHTML={{
                  __html: formatInlineMarkdown(trimmed.replace('> ', '')),
                }}
              />
            );
          }

          if (!trimmed) {
            return null;
          }

          return (
            <p
              key={idx}
              className="text-[11.5px] text-[#252B29] leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: formatInlineMarkdown(trimmed),
              }}
            />
          );
        })}
      </div>
    );
  };

  // Helper for bold and code tags
  const formatInlineMarkdown = (str) => {
    return str
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-[#252B29]">$1</strong>')
      .replace(/`([^`]+)`/g, '<code class="font-mono text-[10px] bg-[#EAE8E0] text-[#147D69] px-1 py-0.5 rounded font-semibold">$1</code>');
  };

  if (!isOpen) return null;

  // Extract focal account risk tier
  const prob = accountData?.ml_prediction?.calibrated_probability;
  const riskTier = accountData?.ml_prediction?.risk_tier || 'CRITICAL';

  return (
    <aside
      className="fixed top-14 right-0 bottom-0 w-full sm:w-[440px] bg-white border-l border-[#E2E0D8] shadow-2xl z-40 flex flex-col font-sans transition-transform duration-200 ease-in-out"
      aria-label="AI Investigation Copilot"
    >
      {/* 1. Header Bar */}
      <div className="h-14 px-4 border-b border-[#E2E0D8] bg-gradient-to-r from-[#F7F6F2] to-white flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#147D69] to-[#0E5E4E] flex items-center justify-center text-white shadow-sm shrink-0 border border-emerald-400/30">
            <Sparkles className="w-4 h-4 text-emerald-200" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-[#252B29] truncate font-sans">
                Investigation Copilot
              </h3>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-[#147D69]/10 text-[#147D69] border border-[#147D69]/20 uppercase">
                {investigationMode === 'predictive' ? 't \u2264 T_obs' : '30D Retro'}
              </span>
            </div>
            <div className="flex items-center gap-1 text-[10px] font-mono text-[#737A76] truncate">
              <span>{accountId || 'No Account Selected'}</span>
              {prob != null && (
                <span
                  className={`font-semibold ml-1 ${
                    riskTier === 'CRITICAL'
                      ? 'text-[#C64B43]'
                      : riskTier === 'HIGH'
                      ? 'text-[#D58A27]'
                      : 'text-[#147D69]'
                  }`}
                >
                  ({riskTier} P = {prob.toFixed(4)})
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleClearHistory}
            title="Reset conversation"
            className="p-1.5 text-[#737A76] hover:text-[#252B29] hover:bg-[#EAE8E0] rounded-md transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onClose}
            title="Close Copilot (Esc)"
            className="p-1.5 text-[#737A76] hover:text-[#C64B43] hover:bg-[#C64B43]/10 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 2. Messages View Area */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-3 bg-[#FBFBFA]/60">
        {/* Grounded Investigation Mode Pill */}
        <div className="px-2.5 py-1 rounded bg-[#F7F6F2] border border-[#E2E0D8] text-[9.5px] text-[#737A76] font-sans flex items-center gap-1.5 shrink-0">
          <Sparkles className="w-3 h-3 text-[#147D69] shrink-0" />
          <span className="truncate">
            <strong className="text-[#252B29]">Grounded AI:</strong> CatBoost Platt-calibrated probability &amp; verified graph evidence.
          </span>
        </div>

        {/* Message Stream */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.role === 'user' ? 'items-end' : 'items-start'
            }`}
          >
            <div className="flex items-center gap-1.5 mb-1 px-1">
              {msg.role === 'user' ? (
                <>
                  <span className="text-[10px] font-semibold text-[#737A76]">Investigator</span>
                  <User className="w-3 h-3 text-[#737A76]" />
                </>
              ) : (
                <>
                  <Bot className="w-3 h-3 text-[#147D69]" />
                  <span className="text-[10px] font-bold text-[#147D69]">Copilot Intelligence</span>
                </>
              )}
            </div>

            <div
              className={`p-2.5 px-3 rounded-xl max-w-[96%] shadow-xs text-xs font-sans ${
                msg.role === 'user'
                  ? 'bg-[#147D69] text-white rounded-tr-none'
                  : msg.isConfigError
                  ? 'bg-amber-50/90 border border-amber-200 text-[#252B29] rounded-tl-none'
                  : msg.isError
                  ? 'bg-[#C64B43]/10 border border-[#C64B43]/25 text-[#252B29] rounded-tl-none'
                  : 'bg-white border border-[#E2E0D8] text-[#252B29] rounded-tl-none shadow-xs'
              }`}
            >
              {msg.role === 'user' ? (
                <p className="text-xs font-sans leading-relaxed text-white whitespace-pre-wrap">
                  {msg.content}
                </p>
              ) : (
                renderFormattedMarkdown(msg.content)
              )}

              {/* Citations & Direct Deep-Links */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 pt-1.5 border-t border-[#E2E0D8]/60 flex items-center flex-wrap gap-1">
                  <span className="text-[9px] uppercase font-bold text-[#737A76] tracking-wider mr-1">
                    Evidence Links:
                  </span>
                  {msg.citations.map((c, i) => (
                    <button
                      key={i}
                      onClick={() => onNavigateTab && onNavigateTab(c.target_tab || 'evidence')}
                      title={`Navigate to ${c.target_tab} view`}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#F7F6F2] hover:bg-[#EAE8E0] border border-[#E2E0D8] text-[9.5px] font-mono text-[#147D69] transition-all hover:border-[#147D69]/40 cursor-pointer"
                    >
                      <span>{c.label}</span>
                      <ChevronRight className="w-2.5 h-2.5 text-[#737A76]" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex flex-col items-start space-y-1">
            <div className="flex items-center gap-1.5 px-1">
              <Bot className="w-3 h-3 text-[#147D69]" />
              <span className="text-[10px] font-bold text-[#147D69]">Copilot Analyzing...</span>
            </div>
            <div className="p-2.5 px-3 bg-white border border-[#E2E0D8] rounded-xl rounded-tl-none text-[#737A76] text-xs flex items-center gap-2 shadow-xs">
              <div className="w-3 h-3 border-2 border-[#147D69] border-t-transparent rounded-full animate-spin shrink-0" />
              <span className="text-[11px] font-sans">Synthesizing CatBoost risk telemetry and evidence graph...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 3. Suggested Prompt Chips */}
      {suggestedQuestions.length > 0 && (
        <div className="px-3 py-2 bg-[#F7F6F2] border-t border-[#E2E0D8] shrink-0">
          <div className="flex items-center gap-1 text-[9.5px] font-bold uppercase tracking-wider text-[#737A76] mb-1.5">
            <Sparkles className="w-2.5 h-2.5 text-[#147D69]" />
            <span>Quick Investigation Questions:</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {suggestedQuestions.map((q, idx) => (
              <button
                key={idx}
                disabled={loading}
                onClick={() => handleSendMessage(q)}
                className="text-[10px] font-medium font-sans text-[#252B29] bg-white hover:bg-emerald-50 hover:text-[#147D69] hover:border-emerald-300 border border-[#E2E0D8] rounded-md px-2.5 py-1 transition-all text-left shadow-xs hover:shadow disabled:opacity-50 cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 4. Chat Input Field */}
      <div className="p-3 bg-white border-t border-[#E2E0D8] shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="relative flex items-center"
        >
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            disabled={loading || !accountId}
            placeholder={
              accountId
                ? `Ask about ${accountId}'s risk, evidence, or peers...`
                : 'Select an account to ask copilot...'
            }
            className="w-full bg-[#F7F6F2] border border-[#E2E0D8] rounded-lg pl-3 pr-10 py-2 text-xs text-[#252B29] placeholder-[#9BA09D] focus:outline-none focus:border-[#147D69] focus:ring-1 focus:ring-[#147D69] transition-all font-sans disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!inputMessage.trim() || loading || !accountId}
            className="absolute right-1.5 p-1.5 bg-[#147D69] hover:bg-[#117A62] disabled:bg-[#E2E0D8] text-white disabled:text-[#9BA09D] rounded-md transition-all shadow-xs disabled:shadow-none cursor-pointer disabled:cursor-not-allowed"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>

        <div className="flex items-center justify-between text-[9px] text-[#9BA09D] font-mono mt-1 px-1">
          <span>Enter to submit • Grounded in {accountId || 'None'}</span>
          <span>Shift+Enter for newline</span>
        </div>
      </div>
    </aside>
  );
}
