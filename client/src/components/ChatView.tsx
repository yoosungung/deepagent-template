import React, { useState, useEffect, useRef } from 'react'
import { Send, Terminal, HelpCircle, Loader, RefreshCw, Layers } from 'lucide-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface LogEntry {
  timestamp: string
  content: string
}

const INITIAL_ASSISTANT_MESSAGE =
  '안녕하세요! SI 에이전트 스캐폴딩 콘솔입니다. 메인 오케스트레이터 에이전트와 서브 에이전트(연구원, 작성자)를 사용해 VFS 파일 생성/수정 및 다양한 태스크를 진행할 수 있습니다. 어떤 작업을 도와드릴까요?'

function createInitialMessages(): Message[] {
  return [{ role: 'assistant', content: INITIAL_ASSISTANT_MESSAGE }]
}

/** SSE token payloads may be a string or structured content blocks from the LLM. */
function appendTokenContent(current: string, token: unknown): string {
  if (typeof token === 'string') return current + token
  if (Array.isArray(token)) {
    return current + token.map((block) => {
      if (typeof block === 'string') return block
      if (block && typeof block === 'object' && 'text' in block) {
        return String((block as { text?: string }).text ?? '')
      }
      return ''
    }).join('')
  }
  if (token && typeof token === 'object' && 'text' in token) {
    return current + String((token as { text?: string }).text ?? '')
  }
  return current
}

export default function ChatView() {
  const [threadId, setThreadId] = useState<string>('si-session-01')
  const [messages, setMessages] = useState<Message[]>(createInitialMessages)
  const [input, setInput] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  
  const chatEndRef = useRef<HTMLDivElement>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const activeEventSourceRef = useRef<EventSource | null>(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Scroll to bottom on new logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const addLog = (content: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev, { timestamp, content }])
  }

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)
    addLog(`[System] Sending message on thread "${threadId}"`)

    // Prepare container for agent streaming response
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    let activeEventSource: EventSource | null = null
    try {
      const url = `/api/agent/stream?thread_id=${encodeURIComponent(threadId)}&message=${encodeURIComponent(userMessage)}`
      activeEventSource = new EventSource(url)
      activeEventSourceRef.current = activeEventSource

      activeEventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'token') {
            setMessages(prev => {
              const updated = [...prev]
              const lastMsg = updated[updated.length - 1]
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content = appendTokenContent(lastMsg.content, data.content)
              }
              return updated
            })
          } else if (data.type === 'log') {
            addLog(data.content)
          } else if (data.type === 'done') {
            setLoading(false)
            addLog(`[System] Agent execution completed successfully.`)
            activeEventSource?.close()
            activeEventSourceRef.current = null
          } else if (data.type === 'error') {
            setLoading(false)
            addLog(`[Error] ${data.content}`)
            setMessages(prev => {
              const updated = [...prev]
              const lastMsg = updated[updated.length - 1]
              if (lastMsg && lastMsg.role === 'assistant') {
                lastMsg.content = `에러가 발생했습니다: ${data.content}`
              }
              return updated
            })
            activeEventSource?.close()
            activeEventSourceRef.current = null
          }
        } catch (err) {
          logger.error("SSE JSON parse error", err)
        }
      }

      activeEventSource.onerror = (err) => {
        addLog(`[System] Stream connection error. Retrying...`)
        logger.error("SSE connection error", err)
        setLoading(false)
        activeEventSource?.close()
        activeEventSourceRef.current = null
      }

    } catch (e: any) {
      addLog(`[System] Failed to connect: ${e.message}`)
      setLoading(false)
      if (activeEventSource) {
        activeEventSource.close()
        activeEventSourceRef.current = null
      }
    }
  }

  const resetChatSession = (logMessage: string) => {
    activeEventSourceRef.current?.close()
    activeEventSourceRef.current = null
    setLoading(false)
    setInput('')
    setMessages(createInitialMessages())
    setLogs([])
    addLog(logMessage)
  }

  const handleClear = () => {
    activeEventSourceRef.current?.close()
    activeEventSourceRef.current = null
    setLoading(false)
    setInput('')
    setMessages([
      {
        role: 'assistant',
        content: '대화 기록이 초기화되었습니다. 진행할 작업을 입력해주세요.'
      }
    ])
    setLogs([{ timestamp: new Date().toLocaleTimeString(), content: '[System] Conversation history cleared locally.' }])
  }

  const handleGenerateThreadId = () => {
    const newId = `si-session-${Math.random().toString(36).slice(2, 8)}`
    setThreadId(newId)
    resetChatSession(`[System] New thread "${newId}" — conversation reset.`)
  }

  return (
    <div className="flex flex-col h-full bg-[#161a23] border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
      {/* Top Header */}
      <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-cyan-400/10 text-cyan-400">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-bold text-white tracking-wide">Orchestrator Agent</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-[11px] text-zinc-400 font-medium uppercase tracking-wider">Multi-Agent Mode</span>
            </div>
          </div>
        </div>

        {/* Thread Controls */}
        <div className="flex items-center gap-2 bg-black/30 p-1.5 rounded-lg border border-white/5">
          <span className="text-[11px] text-zinc-400 px-2 font-mono">Thread:</span>
          <input
            type="text"
            value={threadId}
            onChange={(e) => setThreadId(e.target.value)}
            className="bg-transparent text-white text-xs font-mono w-28 focus:outline-none focus:ring-0 px-1 border-r border-white/10"
            title="LangGraph Conversation Thread ID"
          />
          <button 
            onClick={handleGenerateThreadId}
            className="p-1 text-zinc-400 hover:text-cyan-400 hover:bg-white/5 rounded transition-all"
            title="새 Thread ID 생성 및 대화 초기화"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Row: Chat and Developer Logs */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        
        {/* Left Side: Chat Room */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#0f1118]/60">
          {/* Chat Messages */}
          <div className="flex-1 p-5 overflow-y-auto space-y-4 scrollbar-gutter-stable overscroll-contain">
            {messages.map((msg, idx) => (
              <div 
                key={idx} 
                className={`flex gap-3 animate-fade-in ${msg.role === 'user' ? 'justify-end' : ''}`}
              >
                {msg.role !== 'user' && (
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-xs flex-shrink-0">
                    O
                  </div>
                )}
                
                <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed border ${
                  msg.role === 'user' 
                    ? 'bg-indigo-600 text-white border-indigo-500/30 rounded-tr-none' 
                    : 'bg-[#1e2330] text-zinc-200 border-white/5 rounded-tl-none shadow-md'
                }`}>
                  {msg.content ? (
                    <div className="whitespace-pre-wrap select-text">{msg.content}</div>
                  ) : (
                    <div className="flex items-center gap-2 text-zinc-400">
                      <Loader className="w-3.5 h-3.5 animate-spin" />
                      <span>에이전트가 생각하는 중...</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Chat Input */}
          <form onSubmit={handleSend} className="p-4 border-t border-white/5 bg-[#121620]">
            <div className="flex gap-2 bg-[#1b202e] rounded-xl border border-white/5 px-3.5 py-1.5 focus-within:border-cyan-400/40 focus-within:ring-1 focus-within:ring-cyan-400/10 transition-all">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="에이전트에게 지시할 작업을 입력하세요 (예: 연구원에게 SI 사업 동향 조사를 맡기고 결과를 보고서로 저장해줘)"
                className="flex-1 bg-transparent border-none focus:ring-0 focus:outline-none text-sm text-white placeholder-zinc-500 py-2.5"
                disabled={loading}
              />
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={handleClear}
                  className="px-3 py-1.5 text-xs text-zinc-400 hover:text-white rounded-lg hover:bg-white/5 transition-all"
                  title="Clear conversation"
                >
                  Clear
                </button>
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className={`p-2.5 rounded-lg transition-all ${
                    loading || !input.trim()
                      ? 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
                      : 'bg-cyan-400 text-slate-950 hover:bg-cyan-300 active:scale-95 shadow-lg shadow-cyan-400/10'
                  }`}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </form>
        </div>

        {/* Right Side: Log Console for Observability */}
        <div className="w-[320px] border-l border-white/5 bg-[#0a0c10] flex flex-col flex-shrink-0">
          <div className="px-4 py-3 border-b border-white/5 bg-slate-900/30 flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-400 font-semibold text-xs tracking-wider uppercase font-mono">
              <Terminal className="w-4 h-4" />
              <span>Developer Logs</span>
            </div>
            {logs.length > 0 && (
              <span className="text-[10px] bg-cyan-400/10 text-cyan-400 px-1.5 py-0.5 rounded font-mono">
                {logs.length}
              </span>
            )}
          </div>

          <div className="flex-1 p-4 overflow-y-auto space-y-2.5 scrollbar-gutter-stable font-mono text-[11px] text-zinc-400 select-text bg-[#07080b]">
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center text-zinc-600 gap-2 p-4">
                <HelpCircle className="w-8 h-8 opacity-40" />
                <p>에이전트가 작업을 시작하면 상세 실행 과정 및 도구 로깅이 이곳에 실시간으로 표시됩니다.</p>
              </div>
            ) : (
              logs.map((log, idx) => (
                <div key={idx} className="border-b border-white/[0.02] pb-1.5">
                  <span className="text-zinc-600 text-[10px] mr-1.5">[{log.timestamp}]</span>
                  <span className={
                    log.content.includes('[System]') ? 'text-zinc-500' :
                    log.content.includes('[Error]') ? 'text-rose-400 font-semibold' :
                    log.content.includes('Running tool') ? 'text-amber-400' :
                    log.content.includes('Starting:') ? 'text-indigo-400 font-medium' : 'text-zinc-300'
                  }>
                    {log.content}
                  </span>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </div>

      </div>
    </div>
  )
}

// Simple browser global logger mock helper
const logger = {
  error: (msg: string, ...args: any[]) => console.error(`[ChatView] ${msg}`, ...args)
}
