import { useState } from 'react'
import ChatView from './components/ChatView.tsx'
import AdminView from './components/AdminView.tsx'
import { Cpu, MessageSquare, HardDrive } from 'lucide-react'

type TabId = 'agent' | 'vfs'

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('agent')

  return (
    <div className="flex flex-col h-screen max-h-screen bg-[#0b0c10] text-[#c5c6c7] font-sans overflow-hidden select-none">
      {/* Global Navigation Bar */}
      <header className="h-16 border-b border-white/5 bg-slate-950/80 backdrop-blur-md px-6 flex items-center justify-between flex-shrink-0 z-10">
        <div className="flex items-center gap-3">
          <div className="relative p-2 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 text-white shadow-lg shadow-cyan-500/10">
            <Cpu className="w-5 h-5" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-slate-950"></span>
          </div>
          <div>
            <h1 className="font-extrabold text-white tracking-wide text-base leading-none font-outfit">
              SI Agent Scaffolding
            </h1>
            <span className="text-[10px] text-zinc-500 font-mono tracking-widest uppercase mt-1 block">
              Agent Console v1.0.0
            </span>
          </div>
        </div>

        {/* Specs Badge */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-full border border-white/5 font-mono text-[10px] text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
            <span>LLM: OpenAI / Anthropic</span>
          </div>
          <div className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-full border border-white/5 font-mono text-[10px] text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
            <span>DB Memory: Postgres VFS</span>
          </div>
        </div>
      </header>

      <main className="flex-1 flex flex-col overflow-hidden min-h-0 bg-gradient-to-b from-[#0b0c10] to-[#07080b]">
        {/* Tab bar */}
        <div className="flex-shrink-0 px-6 pt-4 pb-0">
          <div
            className="inline-flex p-1 rounded-xl bg-white/5 border border-white/5"
            role="tablist"
            aria-label="Console views"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'agent'}
              onClick={() => setActiveTab('agent')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'agent'
                  ? 'bg-gradient-to-r from-cyan-500/20 to-indigo-500/20 text-white border border-cyan-500/30 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              Orchestrator Agent
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'vfs'}
              onClick={() => setActiveTab('vfs')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'vfs'
                  ? 'bg-gradient-to-r from-indigo-500/20 to-violet-500/20 text-white border border-indigo-500/30 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'
              }`}
            >
              <HardDrive className="w-4 h-4" />
              VFS Admin
            </button>
          </div>
        </div>

        {/* Tab panels — both mounted to preserve state when switching */}
        <div className="flex-1 min-h-0 p-6 pt-4">
          <section
            role="tabpanel"
            aria-hidden={activeTab !== 'agent'}
            className={`h-full min-h-0 ${activeTab === 'agent' ? 'block' : 'hidden'}`}
          >
            <ChatView />
          </section>
          <section
            role="tabpanel"
            aria-hidden={activeTab !== 'vfs'}
            className={`h-full min-h-0 ${activeTab === 'vfs' ? 'block' : 'hidden'}`}
          >
            <AdminView />
          </section>
        </div>
      </main>
    </div>
  )
}
