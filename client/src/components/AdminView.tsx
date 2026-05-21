import React, { useState, useEffect } from 'react'
import { Folder, FileText, ChevronRight, ChevronDown, Trash2, Plus, Upload, Download, Save, X, HardDrive } from 'lucide-react'

interface VfsEntry {
  path: string
  is_dir: boolean
  size: number
  modified_at: string
}

export default function AdminView() {
  const [entries, setEntries] = useState<VfsEntry[]>([])
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    '/': true
  })
  
  // Selected file states
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string>('')
  const [originalContent, setOriginalContent] = useState<string>('')
  const [saving, setSaving] = useState<boolean>(false)
  const [loadingFile, setLoadingFile] = useState<boolean>(false)

  // Creation states
  const [newPath, setNewPath] = useState<string>('')
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false)
  const [isNewFolder, setIsNewFolder] = useState<boolean>(false)

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadPath, setUploadPath] = useState<string>('')
  
  useEffect(() => {
    fetchVfsList()
  }, [])

  const fetchVfsList = async () => {
    try {
      const res = await fetch('/api/vfs/list?path=/')
      if (res.ok) {
        const data = await res.json()
        setEntries(data.entries || [])
      }
    } catch (err) {
      console.error('Failed to fetch VFS items', err)
    }
  }

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => ({
      ...prev,
      [path]: !prev[path]
    }))
  }

  /** Parent directory paths that must be expanded for `path` to show in the tree. */
  const parentDirPaths = (path: string): string[] => {
    const normalized = path.endsWith('/') ? path.slice(0, -1) : path
    const segments = normalized.split('/').filter(Boolean)
    const parents: string[] = []
    for (let i = 1; i < segments.length; i++) {
      parents.push('/' + segments.slice(0, i).join('/') + '/')
    }
    return parents
  }

  const isEntryVisible = (entry: VfsEntry): boolean => {
    if (entry.path === '/') return false
    return parentDirPaths(entry.path).every(
      (parent) => expandedFolders[parent] !== false
    )
  }

  const handleSelectFile = async (path: string) => {
    setLoadingFile(true)
    setSelectedFile(path)
    try {
      const res = await fetch(`/api/vfs/read?path=${encodeURIComponent(path)}`)
      if (res.ok) {
        const data = await res.json()
        setFileContent(data.content || '')
        setOriginalContent(data.content || '')
      } else {
        alert('파일을 불러오는데 실패했습니다.')
      }
    } catch (err) {
      console.error('Error reading VFS file', err)
    } finally {
      setLoadingFile(false)
    }
  }

  const handleSaveFile = async () => {
    if (!selectedFile) return
    setSaving(true)
    try {
      const res = await fetch('/api/vfs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent,
          overwrite: true
        })
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        alert(`저장 도중 오류가 발생했습니다: ${errorData.detail || res.statusText}`)
      } else {
        setOriginalContent(fileContent)
        addConsoleLog(`[VFS] File saved: ${selectedFile}`)
      }
    } catch (err) {
      console.error('Error saving file', err)
      alert('네트워크 오류가 발생했습니다.')
    } finally {
      setSaving(false)
      fetchVfsList()
    }
  }

  const handleDeleteFile = async (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`정말로 '${path}' 항목을 삭제하시겠습니까?`)) return
    
    try {
      const res = await fetch(`/api/vfs/delete?path=${encodeURIComponent(path)}`, {
        method: 'DELETE'
      })
      if (res.ok) {
        addConsoleLog(`[VFS] Deleted file/folder: ${path}`)
        if (selectedFile === path) {
          setSelectedFile(null)
          setFileContent('')
        }
        fetchVfsList()
      } else {
        alert('삭제에 실패했습니다.')
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleCreateEntry = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPath.trim()) return

    // Ensure path starts with /
    let formattedPath = newPath.trim()
    if (!formattedPath.startsWith('/')) {
      formattedPath = '/' + formattedPath
    }

    if (isNewFolder && !formattedPath.endsWith('/')) {
      formattedPath += '/'
    }

    try {
      const res = await fetch('/api/vfs/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: formattedPath,
          content: isNewFolder ? '' : '# ' + formattedPath.split('/').pop()
        })
      })
      if (res.ok) {
        addConsoleLog(`[VFS] Created ${isNewFolder ? 'directory' : 'file'}: ${formattedPath}`)
        setNewPath('')
        setShowCreateModal(false)
        fetchVfsList()
        if (!isNewFolder) {
          handleSelectFile(formattedPath)
        }
      } else {
        const data = await res.json()
        alert(`생성 실패: ${data.detail || '알 수 없는 에러'}`)
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleUploadFile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile || !uploadPath.trim()) return

    let formattedPath = uploadPath.trim()
    if (!formattedPath.startsWith('/')) {
      formattedPath = '/' + formattedPath
    }

    const formData = new FormData()
    formData.append('path', formattedPath)
    formData.append('file', uploadFile)

    try {
      const res = await fetch('/api/vfs/upload', {
        method: 'POST',
        body: formData
      })
      if (res.ok) {
        addConsoleLog(`[VFS] Uploaded file successfully: ${formattedPath}`)
        setUploadFile(null)
        setUploadPath('')
        fetchVfsList()
        handleSelectFile(formattedPath)
      } else {
        alert('업로드에 실패했습니다.')
      }
    } catch (err) {
      console.error(err)
    }
  }

  const handleDownloadFile = (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    window.open(`/api/vfs/download?path=${encodeURIComponent(path)}`)
  }

  // File tree grouping render
  const renderTree = () => {
    // Process flat path entries into tree structure or render directly sorted list
    // Since VFS contains full paths like /skills/research_assistant/SKILL.md, we sort them so directories appear first.
    
    // Sort directories before files, then sort alphabetically
    const sorted = [...entries].sort((a, b) => {
      if (a.is_dir && !b.is_dir) return -1
      if (!a.is_dir && b.is_dir) return 1
      return a.path.localeCompare(b.path)
    })

    return (
      <div className="space-y-1">
        {sorted.map(entry => {
          if (!isEntryVisible(entry)) return null

          const depth = (entry.path.match(/\//g) || []).length - (entry.path.endsWith('/') ? 1 : 0)
          const name = entry.path.split('/').filter(Boolean).pop() || entry.path

          if (entry.path === '/') return null

          const paddingLeft = `${depth * 12}px`

          return (
            <div
              key={entry.path}
              onClick={() => {
                if (entry.is_dir) {
                  toggleFolder(entry.path)
                } else {
                  handleSelectFile(entry.path)
                }
              }}
              className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs cursor-pointer group transition-all ${
                selectedFile === entry.path
                  ? 'bg-cyan-400/10 text-cyan-400 font-semibold border-l-2 border-cyan-400'
                  : 'text-zinc-400 hover:bg-white/5 hover:text-white'
              }`}
              style={{ paddingLeft }}
            >
              <div className="flex items-center gap-2 truncate">
                {entry.is_dir ? (
                  <>
                    {expandedFolders[entry.path] ? (
                      <ChevronDown className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
                    )}
                    <Folder className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  </>
                ) : (
                  <>
                    <span className="w-3.5 h-3.5 flex-shrink-0" />
                    <FileText className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                  </>
                )}
                <span className="truncate" title={entry.path}>{name}{entry.is_dir ? '/' : ''}</span>
              </div>
              
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {!entry.is_dir && (
                  <button
                    onClick={(e) => handleDownloadFile(entry.path, e)}
                    className="p-1 hover:text-cyan-400 rounded hover:bg-white/10"
                    title="Download file"
                  >
                    <Download className="w-3 h-3" />
                  </button>
                )}
                <button
                  onClick={(e) => handleDeleteFile(entry.path, e)}
                  className="p-1 hover:text-rose-400 rounded hover:bg-white/10"
                  title="Delete entry"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  const [consoleLogs, setConsoleLogs] = useState<string[]>([
    '[VFS System] Virtual File System online (Postgres Backed).'
  ])
  const addConsoleLog = (msg: string) => {
    setConsoleLogs(prev => [...prev, `${new Date().toLocaleTimeString()} - ${msg}`])
  }

  return (
    <div className="flex h-full bg-[#161a23] border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
      {/* Left Sidebar: File Tree & Tools */}
      <div className="w-[300px] border-r border-white/5 bg-[#0f1118]/60 flex flex-col flex-shrink-0">
        <div className="px-5 py-4 border-b border-white/5 bg-slate-900/40 flex items-center justify-between">
          <div className="flex items-center gap-2.5 text-white">
            <HardDrive className="w-5 h-5 text-cyan-400" />
            <h3 className="font-bold text-sm tracking-wide">VFS Admin</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                setIsNewFolder(false)
                setShowCreateModal(true)
              }}
              className="p-1.5 text-zinc-400 hover:text-cyan-400 hover:bg-white/5 rounded transition-all"
              title="New file"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={fetchVfsList}
              className="p-1.5 text-zinc-400 hover:text-cyan-400 hover:bg-white/5 rounded transition-all"
              title="Refresh VFS tree"
            >
              <ChevronRight className="w-4 h-4 rotate-90" />
            </button>
          </div>
        </div>

        {/* Tree Container */}
        <div className="flex-1 p-4 overflow-y-auto scrollbar-gutter-stable overscroll-contain">
          {entries.length === 0 ? (
            <p className="text-xs text-zinc-500 text-center p-4">Loading VFS database records...</p>
          ) : (
            renderTree()
          )}
        </div>

        {/* Upload form block */}
        <div className="p-4 border-t border-white/5 bg-black/20">
          <h4 className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider mb-2">Upload local files to VFS</h4>
          <form onSubmit={handleUploadFile} className="space-y-2">
            <input
              type="text"
              placeholder="VFS destination path (e.g. /skills/my_skill/SKILL.md)"
              value={uploadPath}
              onChange={(e) => {
                setUploadPath(e.target.value)
                // Auto fill upload path with filename if empty
                if (uploadFile && !e.target.value) {
                  setUploadPath(`/memory/${uploadFile.name}`)
                }
              }}
              className="w-full bg-[#1b202e] border border-white/5 rounded px-2.5 py-1.5 text-xs text-white placeholder-zinc-600 focus:outline-none"
              required
            />
            <div className="flex gap-2">
              <input
                type="file"
                id="vfs-uploader-file"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) {
                    setUploadFile(f)
                    setUploadPath(prev => prev ? prev : `/memory/${f.name}`)
                  }
                }}
              />
              <label
                htmlFor="vfs-uploader-file"
                className="flex-1 text-center bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs px-2.5 py-1.5 rounded cursor-pointer transition-all border border-white/5 truncate"
              >
                {uploadFile ? uploadFile.name : 'Select file'}
              </label>
              <button
                type="submit"
                disabled={!uploadFile}
                className={`px-3 py-1.5 text-xs rounded font-medium flex items-center gap-1.5 transition-all ${
                  uploadFile 
                    ? 'bg-cyan-400 text-slate-950 hover:bg-cyan-300' 
                    : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Upload</span>
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Right side: Editor Panel */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#0f1118]/20">
        {selectedFile ? (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Editor toolbar */}
            <div className="px-5 py-3 border-b border-white/5 bg-slate-900/20 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-mono text-white truncate" title={selectedFile}>
                  {selectedFile}
                </span>
                {fileContent !== originalContent && (
                  <span className="text-[10px] bg-amber-400/10 text-amber-400 px-1.5 py-0.5 rounded uppercase font-semibold tracking-wider font-mono">
                    Modified
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSaveFile}
                  disabled={saving || fileContent === originalContent}
                  className={`px-3.5 py-1.5 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-all ${
                    saving || fileContent === originalContent
                      ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed border border-white/5'
                      : 'bg-cyan-400 text-slate-950 hover:bg-cyan-300 active:scale-95 shadow-lg shadow-cyan-400/15'
                  }`}
                >
                  {saving ? (
                    <ChevronRight className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  <span>Save changes</span>
                </button>
                <button
                  onClick={() => {
                    setSelectedFile(null)
                    setFileContent('')
                  }}
                  className="p-1.5 hover:bg-white/5 text-zinc-400 hover:text-white rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Content Textarea */}
            <div className="flex-1 p-5 min-h-0 flex flex-col">
              {loadingFile ? (
                <div className="flex-1 flex items-center justify-center">
                  <ChevronRight className="w-6 h-6 text-cyan-400 animate-spin" />
                </div>
              ) : (
                <textarea
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                  className="flex-1 w-full bg-[#0a0c10] border border-white/5 rounded-xl p-4 text-xs font-mono text-zinc-300 focus:outline-none focus:ring-1 focus:ring-cyan-400/20 leading-relaxed resize-none select-text"
                  spellCheck="false"
                />
              )}
            </div>
          </div>
        ) : (
          /* Empty Dashboard view */
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#0d1017]">
            <div className="p-4 rounded-full bg-cyan-400/5 text-cyan-400 mb-4">
              <HardDrive className="w-10 h-10" />
            </div>
            <h3 className="font-bold text-white mb-2">VFS Explorer Mode</h3>
            <p className="text-xs text-zinc-400 max-w-sm leading-relaxed mb-6">
              왼쪽의 파일 목록에서 파일을 선택하여 실시간으로 조회하고 편집할 수 있습니다. 
              에이전트가 작업하는 과정에서 생성한 파일들이 여기에 즉시 연동됩니다.
            </p>

            <div className="w-full max-w-md bg-[#161a23] border border-white/5 rounded-xl p-4 text-left font-mono text-[10px] text-zinc-400">
              <div className="text-zinc-500 border-b border-white/5 pb-2 mb-2 uppercase tracking-wide font-bold">VFS Activity Logs</div>
              <div className="space-y-1.5 max-h-[150px] overflow-y-auto">
                {consoleLogs.map((log, i) => (
                  <div key={i} className="text-zinc-400 truncate">{log}</div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Creation Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-sm bg-[#161a23] border border-white/10 rounded-2xl p-5 shadow-2xl animate-fade-in">
            <h3 className="font-bold text-white text-sm mb-4">Create New VFS Item</h3>
            <form onSubmit={handleCreateEntry} className="space-y-4">
              <div>
                <label className="block text-[10px] text-zinc-500 uppercase tracking-wider font-bold mb-1.5">Type</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setIsNewFolder(false)}
                    className={`py-2 text-xs rounded-lg font-medium transition-all ${
                      !isNewFolder 
                        ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30' 
                        : 'bg-zinc-800 text-zinc-400 border border-transparent'
                    }`}
                  >
                    File
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsNewFolder(true)}
                    className={`py-2 text-xs rounded-lg font-medium transition-all ${
                      isNewFolder 
                        ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30' 
                        : 'bg-zinc-800 text-zinc-400 border border-transparent'
                    }`}
                  >
                    Directory
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[10px] text-zinc-500 uppercase tracking-wider font-bold mb-1.5">Path</label>
                <input
                  type="text"
                  placeholder={isNewFolder ? '/skills/new_folder' : '/memory/report.md'}
                  value={newPath}
                  onChange={(e) => setNewPath(e.target.value)}
                  className="w-full bg-[#0a0c10] border border-white/5 rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-700 focus:outline-none"
                  required
                />
              </div>

              <div className="flex gap-2 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false)
                    setNewPath('')
                  }}
                  className="px-3.5 py-2 text-xs text-zinc-400 hover:text-white rounded-lg transition-all"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-cyan-400 text-slate-950 hover:bg-cyan-300 transition-all"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
