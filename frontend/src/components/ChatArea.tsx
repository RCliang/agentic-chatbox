import { useState, useRef, useEffect, type FormEvent, type ChangeEvent } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useThemeStore } from '../stores/themeStore';
import MessageBubble from './MessageBubble';
import AgentStep from './AgentStep';
import NodeTracker from './NodeTracker';
import PlanView from './PlanView';
import InterruptDialog from './InterruptDialog';

interface AttachedFile {
  file: File;
  preview?: string;
}

export default function ChatArea() {
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [kbDropdownOpen, setKbDropdownOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const messages = useChatStore((s) => s.messages);
  const agentEvents = useChatStore((s) => s.agentEvents);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const conversations = useChatStore((s) => s.conversations);
  const currentConversationId = useChatStore((s) => s.currentConversationId);
  const sendMessage = useChatStore((s) => s.sendMessage);

  const updateConversationMode = useChatStore((s) => s.updateConversationMode);
  const updateConversationSkill = useChatStore((s) => s.updateConversationSkill);
  const updateConversationKB = useChatStore((s) => s.updateConversationKB);
  const updateConversationTools = useChatStore((s) => s.updateConversationTools);
  const skills = useChatStore((s) => s.skills);

  const interruptData = useChatStore((s) => s.interruptData);
  const planSteps = useChatStore((s) => s.planSteps);
  const activeNodes = useChatStore((s) => s.activeNodes);
  const resumeInterrupt = useChatStore((s) => s.resumeInterrupt);
  const knowledgeBases = useChatStore((s) => s.knowledgeBases);

  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);

  const currentConversation = conversations.find((c) => c.id === currentConversationId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentEvents]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if ((!trimmed && attachedFiles.length === 0) || isStreaming) return;
    setInput('');
    setAttachedFiles([]);
    sendMessage(trimmed);
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newFiles: AttachedFile[] = Array.from(files).map((file) => {
      const af: AttachedFile = { file };
      if (file.type.startsWith('image/')) {
        af.preview = URL.createObjectURL(file);
      }
      return af;
    });
    setAttachedFiles((prev) => [...prev, ...newFiles]);
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => {
      const removed = prev[index];
      if (removed.preview) URL.revokeObjectURL(removed.preview);
      return prev.filter((_, i) => i !== index);
    });
  };

  const isAgentic = currentConversation?.mode === 'agentic';

  const handleSkillToggle = (skillId: string) => {
    if (!currentConversation || !isAgentic || isStreaming) return;
    const newSkillId = currentConversation.skill_id === skillId ? null : skillId;
    updateConversationSkill(currentConversation.id, newSkillId);
  };

  const handleKBSelect = (kbId: string | null) => {
    if (!currentConversation || isStreaming) return;
    updateConversationKB(currentConversation.id, kbId);
    setKbDropdownOpen(false);
  };

  const enabledTools = currentConversation?.enabled_tools || [];

  const handleToolToggle = (toolName: string) => {
    if (!currentConversation || isStreaming) return;
    const newTools = enabledTools.includes(toolName)
      ? enabledTools.filter((t) => t !== toolName)
      : [...enabledTools, toolName];
    updateConversationTools(currentConversation.id, newTools);
  };

  const selectedKB = knowledgeBases.find((kb) => kb.id === currentConversation?.knowledge_base_id);

  return (
    <div className="flex-1 flex flex-col h-full" style={{ background: 'var(--bg-primary)' }}>
      {/* Top bar */}
      <div className="shrink-0 px-6 py-3 flex items-center justify-center relative" style={{ borderBottom: '1px solid var(--border-color)' }}>
        {currentConversation ? (
          <>
            <span className="absolute left-6 text-sm truncate max-w-[180px]" style={{ color: 'var(--text-secondary)' }}>
              {currentConversation.title}
            </span>
            <div className="flex rounded-lg overflow-hidden" style={{ border: '1px solid var(--border-light)' }}>
              <button
                onClick={() => updateConversationMode(currentConversation.id, 'normal')}
                disabled={isStreaming || currentConversation.mode === 'normal'}
                className="px-4 py-1.5 text-xs font-medium transition-colors disabled:cursor-default cursor-pointer hover-lift hover-press"
                style={{
                  background: currentConversation.mode === 'normal' ? 'var(--bg-surface)' : undefined,
                  color: currentConversation.mode === 'normal' ? 'var(--text-primary)' : 'var(--text-muted)',
                }}
              >
                Normal
              </button>
              <button
                onClick={() => updateConversationMode(currentConversation.id, 'agentic')}
                disabled={isStreaming || currentConversation.mode === 'agentic'}
                className="px-4 py-1.5 text-xs font-medium transition-colors disabled:cursor-default cursor-pointer hover-lift hover-press"
                style={{
                  background: currentConversation.mode === 'agentic' ? 'var(--accent-surface)' : undefined,
                  color: currentConversation.mode === 'agentic' ? 'var(--accent-light)' : 'var(--text-muted)',
                }}
              >
                Agentic
              </button>
            </div>
          </>
        ) : (
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Select or create a conversation</span>
        )}

        <button
          onClick={toggleTheme}
          className="absolute right-6 w-8 h-8 flex items-center justify-center rounded-lg transition-colors cursor-pointer hover-scale hover-press"
          style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-light)' }}
          title={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
        >
          {theme === 'dark' ? (
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
            </svg>
          )}
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && agentEvents.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Send a message to start the conversation</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {agentEvents.map((evt, idx) => (
          <AgentStep key={`agent-${idx}`} event={evt} />
        ))}

          {/* Node execution tracker */}
          {activeNodes.length > 0 && <NodeTracker nodes={activeNodes} />}

          {/* Plan view */}
          {planSteps.length > 0 && <PlanView steps={planSteps} />}

          {/* Interrupt dialog */}
          {interruptData && (
            <InterruptDialog
              data={interruptData}
              onAction={(action, payload) => resumeInterrupt(action, payload)}
            />
          )}

        {isStreaming && (
          <div className="flex justify-start mb-4">
            <div className="rounded-lg px-4 py-3" style={{ background: 'var(--bg-card)' }}>
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--accent-light)', animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--accent-light)', animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full animate-bounce" style={{ background: 'var(--accent-light)', animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Skill bubbles */}
      {skills.length > 0 && (
        <div className="shrink-0 px-6 py-2 flex items-center gap-2 flex-wrap" style={{ borderTop: '1px solid var(--border-color)' }}>
          <span className="text-xs mr-1" style={{ color: 'var(--text-muted)' }}>Skills:</span>
          {skills.map((skill) => {
            const isSelected = currentConversation?.skill_id === skill.id;
            const disabled = !isAgentic || isStreaming;
            return (
              <button
                key={skill.id}
                onClick={() => handleSkillToggle(skill.id)}
                disabled={disabled}
                title={disabled
                  ? '仅在 Agentic 模式下可选择 Skill'
                  : `${skill.description || skill.name}${skill.tools?.length ? ` | 工具: ${skill.tools.length}` : ''}${skill.references?.length ? ` | 参考: ${skill.references.length}` : ''}${skill.examples?.length ? ` | 示例: ${skill.examples.length}` : ''}`
                }
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all hover-glow hover-press ${
                  disabled && !isSelected ? 'cursor-not-allowed' : 'cursor-pointer'
                }`}
                style={
                  isSelected
                    ? { background: 'var(--accent-surface)', color: 'var(--accent-light)', border: '1px solid var(--accent)', boxShadow: '0 0 8px var(--accent-muted)' }
                    : { background: 'var(--bg-card)', color: disabled ? 'var(--text-muted)' : 'var(--text-secondary)', border: '1px solid var(--border-light)' }
                }
              >
                {isSelected && <span className="mr-1">&#10003;</span>}
                {skill.name}
              </button>
            );
          })}
        </div>
      )}

      {/* Tools toolbar */}
      {currentConversation && (
        <div className="shrink-0 px-6 py-2 flex items-center gap-3 flex-wrap" style={{ borderTop: '1px solid var(--border-color)' }}>
          {/* Knowledge base selector */}
          <div className="relative">
            <button
              onClick={() => setKbDropdownOpen(!kbDropdownOpen)}
              disabled={isStreaming}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover-glow-success hover-press"
              style={
                selectedKB
                  ? { background: 'var(--success-muted)', color: 'var(--success)', borderColor: 'var(--success)' }
                  : { background: 'var(--bg-card)', color: 'var(--text-secondary)', borderColor: 'var(--border-light)' }
              }
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
              </svg>
              {selectedKB ? selectedKB.name : '知识库问答'}
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
            {kbDropdownOpen && (
              <div className="absolute bottom-full mb-1 left-0 w-48 rounded-lg shadow-lg z-10 py-1 max-h-48 overflow-y-auto" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)' }}>
                <button
                  onClick={() => handleKBSelect(null)}
                  className="w-full px-3 py-2 text-xs text-left transition-colors cursor-pointer"
                  style={{ color: !selectedKB ? 'var(--accent-light)' : 'var(--text-secondary)' }}
                >
                  不使用知识库
                </button>
                {knowledgeBases.map((kb) => (
                  <button
                    key={kb.id}
                    onClick={() => handleKBSelect(kb.id)}
                    className="w-full px-3 py-2 text-xs text-left transition-colors cursor-pointer"
                    style={{ color: currentConversation.knowledge_base_id === kb.id ? 'var(--accent-light)' : 'var(--text-secondary)' }}
                  >
                    {kb.name}
                  </button>
                ))}
                {knowledgeBases.length === 0 && (
                  <div className="px-3 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>暂无知识库</div>
                )}
              </div>
            )}
          </div>

          <div className="w-px h-5" style={{ background: 'var(--border-light)' }} />

          {/* Web search toggle */}
          <button
            onClick={() => handleToolToggle('web_search')}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover-glow hover-press"
            style={
              enabledTools.includes('web_search')
                ? { background: 'var(--accent-surface)', color: 'var(--accent-light)', borderColor: 'var(--accent)' }
                : { background: 'var(--bg-card)', color: 'var(--text-secondary)', borderColor: 'var(--border-light)' }
            }
            title="开启后将使用联网搜索获取最新信息"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.083 9h1.946c.089-1.546.383-2.97.837-4.118A6.004 6.004 0 004.083 9zM10 2a8 8 0 100 16 8 8 0 000-16zm0 2c-.076 0-.232.032-.465.262-.238.234-.497.623-.737 1.182-.389.907-.673 2.142-.766 3.556h3.936c-.093-1.414-.377-2.649-.766-3.556-.24-.56-.5-.948-.737-1.182C10.232 4.032 10.076 4 10 4zm3.971 5c-.089-1.546-.383-2.97-.837-4.118A6.004 6.004 0 0115.917 9h-1.946zm-2.003 2H8.032c.093 1.414.377 2.649.766 3.556.24.56.5.948.737 1.182.233.23.389.262.465.262.076 0 .232-.032.465-.262.238-.234.497-.623.737-1.182.389-.907.673-2.142.766-3.556zm1.166 4.118c.454-1.147.748-2.572.837-4.118h1.946a6.004 6.004 0 01-2.783 4.118zm-6.268 0C6.412 13.97 6.118 12.546 6.029 11H4.083a6.004 6.004 0 002.783 4.118z" clipRule="evenodd" />
            </svg>
            联网搜索
          </button>

          {/* Knowledge graph toggle */}
          <button
            onClick={() => handleToolToggle('knowledge_graph')}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover-glow hover-press"
            style={
              enabledTools.includes('knowledge_graph')
                ? { background: 'var(--accent-surface)', color: 'var(--accent-light)', borderColor: 'var(--accent)' }
                : { background: 'var(--bg-card)', color: 'var(--text-secondary)', borderColor: 'var(--border-light)' }
            }
            title="开启后将使用知识图谱进行深度语义搜索"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M13 7H7v6h6V7z" />
              <path fillRule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clipRule="evenodd" />
            </svg>
            知识图谱
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="shrink-0 px-6 py-4" style={{ borderTop: '1px solid var(--border-color)' }}>
        {attachedFiles.length > 0 && (
          <div className="flex gap-2 mb-2 flex-wrap">
            {attachedFiles.map((af, idx) => (
              <div key={idx} className="relative group rounded-lg p-1.5 flex items-center gap-2 max-w-[200px]" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)' }}>
                {af.preview ? (
                  <img src={af.preview} alt="" className="w-10 h-10 object-cover rounded" />
                ) : (
                  <div className="w-10 h-10 flex items-center justify-center rounded" style={{ background: 'var(--bg-surface)', color: 'var(--accent-light)' }}>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                    </svg>
                  </div>
                )}
                <span className="text-xs truncate" style={{ color: 'var(--text-secondary)' }}>{af.file.name}</span>
                <button
                  onClick={() => removeFile(idx)}
                  className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full text-white text-[10px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                  style={{ background: 'var(--danger)' }}
                >
                  x
                </button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.pdf,.doc,.docx,.txt,.md,.csv"
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isStreaming}
            className="shrink-0 w-10 h-10 flex items-center justify-center rounded-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer hover-scale hover-press"
            style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-light)' }}
            title="上传文件"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            disabled={isStreaming}
            className="flex-1 rounded-xl px-4 py-3 text-sm focus:outline-none disabled:opacity-50 transition-colors"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border-light)', color: 'var(--text-primary)' }}
            onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--border-light)'}
          />
          <button
            type="submit"
            disabled={isStreaming || (!input.trim() && attachedFiles.length === 0)}
            className="px-6 py-3 text-white rounded-xl text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer hover-lift hover-press"
            style={{ background: 'var(--accent)' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-hover)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--accent)')}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
