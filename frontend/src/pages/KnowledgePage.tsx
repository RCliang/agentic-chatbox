import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import api from '../api/client';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  scope: 'personal' | 'department';
  owner_id: string;
  department_name?: string;
  document_count: number;
  created_at: string;
}

interface Document {
  id: string;
  title: string;
  source_type: 'upload' | 'feishu';
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  chunk_count: number;
  created_at: string;
}

interface KnowledgeShare {
  id: string;
  knowledge_base_id: string;
  shared_with_user_id: string;
  shared_with_username: string;
  created_at: string;
}

interface UserSearchResult {
  id: string;
  username: string;
  display_name: string;
}

type ScopeFilter = 'all' | 'personal' | 'department';

/* ------------------------------------------------------------------ */
/*  Status / source badge helpers                                      */
/* ------------------------------------------------------------------ */

const STATUS_STYLES: Record<string, React.CSSProperties> = {
  pending: { background: 'var(--warning-muted)', color: 'var(--warning)' },
  indexing: { background: 'var(--accent-surface)', color: 'var(--accent-light)' },
  ready: { background: 'var(--success-muted)', color: 'var(--success)' },
  failed: { background: 'var(--danger-muted)', color: 'var(--danger)' },
};

const STATUS_LABEL: Record<string, string> = {
  pending: '处理中',
  indexing: '索引中',
  ready: '就绪',
  failed: '失败',
};

const SOURCE_LABEL: Record<string, string> = {
  upload: '上传',
  feishu: '飞书',
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function KnowledgePage() {
  const navigate = useNavigate();

  /* ---- state ---- */
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [filter, setFilter] = useState<ScopeFilter>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // create KB modal
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ name: '', description: '', scope: 'personal' as 'personal' | 'department' });
  const [creating, setCreating] = useState(false);

  // manage-docs modal
  const [activeKb, setActiveKb] = useState<KnowledgeBase | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // share modal
  const [shareKb, setShareKb] = useState<KnowledgeBase | null>(null);
  const [shares, setShares] = useState<KnowledgeShare[]>([]);
  const [sharesLoading, setSharesLoading] = useState(false);
  const [shareUsername, setShareUsername] = useState('');
  const [shareSearchResults, setShareSearchResults] = useState<UserSearchResult[]>([]);
  const [shareError, setShareError] = useState<string | null>(null);

  /* ---- hover helpers ---- */
  const hoverAccent = {
    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.background = 'var(--accent-hover)'; },
    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.background = 'var(--accent)'; },
  };
  const hoverSurface = {
    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.background = 'var(--bg-surface)'; },
    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.background = 'transparent'; },
  };
  const hoverTextPrimary = {
    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.color = 'var(--text-primary)'; },
    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.color = 'var(--text-muted)'; },
  };
  const hoverDanger = {
    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
      e.currentTarget.style.background = 'var(--danger-muted)';
      e.currentTarget.style.color = 'var(--danger)';
    },
    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
      e.currentTarget.style.background = 'transparent';
      e.currentTarget.style.color = 'var(--text-muted)';
    },
  };
  const focusAccent = {
    onFocus: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => { e.currentTarget.style.borderColor = 'var(--accent)'; },
    onBlur: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => { e.currentTarget.style.borderColor = 'var(--border-light)'; },
  };

  /* ---- fetch KB list ---- */
  const fetchBases = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<KnowledgeBase[]>('/api/knowledge/bases');
      setBases(res.data ?? []);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : 'Failed to load knowledge bases';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBases();
  }, []);

  /* ---- filtered list ---- */
  const filtered = filter === 'all' ? bases : bases.filter((b) => b.scope === filter);

  /* ---- create KB ---- */
  const handleCreate = async () => {
    if (!createForm.name.trim()) return;
    setCreating(true);
    try {
      await api.post('/api/knowledge/bases', createForm);
      setShowCreate(false);
      setCreateForm({ name: '', description: '', scope: 'personal' });
      fetchBases();
    } catch {
      // handled silently for now
    } finally {
      setCreating(false);
    }
  };

  /* ---- delete KB ---- */
  const handleDeleteKb = async (id: string) => {
    if (!window.confirm('确认删除此知识库？')) return;
    try {
      await api.delete(`/api/knowledge/bases/${id}`);
      fetchBases();
    } catch {
      // silent
    }
  };

  /* ---- manage docs modal ---- */
  const openDocs = async (kb: KnowledgeBase) => {
    setActiveKb(kb);
    setDocsLoading(true);
    try {
      const res = await api.get<Document[]>(`/api/knowledge/bases/${kb.id}/documents`);
      setDocs(res.data ?? []);
    } catch {
      setDocs([]);
    } finally {
      setDocsLoading(false);
    }
  };

  const closeDocs = () => {
    setActiveKb(null);
    setDocs([]);
  };

  /* ---- upload document ---- */
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeKb) return;
    const token = localStorage.getItem('token');
    try {
      const formData = new FormData();
      formData.append('file', file);
      await axios.post(`/api/knowledge/bases/${activeKb.id}/documents`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' },
        baseURL: 'http://localhost:8000',
      });
      // refresh doc list
      const res = await api.get<Document[]>(`/api/knowledge/bases/${activeKb.id}/documents`);
      setDocs(res.data ?? []);
    } catch {
      // silent
    }
    // reset file input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  /* ---- delete document ---- */
  const handleDeleteDoc = async (docId: string) => {
    if (!activeKb) return;
    try {
      await api.delete(`/api/knowledge/bases/${activeKb.id}/documents/${docId}`);
      setDocs((prev) => prev.filter((d) => d.id !== docId));
    } catch {
      // silent
    }
  };

  /* ---- feishu sync (placeholder action) ---- */
  const handleFeishuSync = async (kb: KnowledgeBase) => {
    try {
      await api.post(`/api/knowledge/bases/${kb.id}/feishu-sync`);
      fetchBases();
    } catch {
      // silent
    }
  };

  /* ---- share modal ---- */
  const openShares = async (kb: KnowledgeBase) => {
    setShareKb(kb);
    setSharesLoading(true);
    setShareError(null);
    setShareUsername('');
    setShareSearchResults([]);
    try {
      const res = await api.get<KnowledgeShare[]>(`/api/knowledge/bases/${kb.id}/shares`);
      setShares(res.data ?? []);
    } catch {
      setShares([]);
    } finally {
      setSharesLoading(false);
    }
  };

  const closeShares = () => {
    setShareKb(null);
    setShares([]);
    setShareError(null);
    setShareUsername('');
    setShareSearchResults([]);
  };

  const handleSearchUsers = async () => {
    const q = shareUsername.trim();
    if (!q) return;
    try {
      const res = await api.get<UserSearchResult[]>('/api/auth/users/search', { params: { q } });
      setShareSearchResults(res.data ?? []);
    } catch {
      setShareSearchResults([]);
    }
  };

  const handleAddShare = async (userId: string) => {
    if (!shareKb) return;
    setShareError(null);
    try {
      const res = await api.post<KnowledgeShare>(`/api/knowledge/bases/${shareKb.id}/shares`, { user_id: userId });
      setShares((prev) => [...prev, res.data]);
      setShareSearchResults([]);
      setShareUsername('');
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) ? err.response?.data?.detail ?? err.message : 'Failed to share';
      setShareError(msg);
    }
  };

  const handleRemoveShare = async (shareId: string) => {
    if (!shareKb) return;
    try {
      await api.delete(`/api/knowledge/bases/${shareKb.id}/shares/${shareId}`);
      setShares((prev) => prev.filter((s) => s.id !== shareId));
    } catch {
      // silent
    }
  };

  /* ================================================================ */
  /*  Render                                                           */
  /* ================================================================ */

  return (
    <div className="min-h-screen p-8" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="cursor-pointer transition-colors"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; }}
            title="返回聊天"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold">知识库管理</h1>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="cursor-pointer rounded px-4 py-2 transition-colors"
          style={{ background: 'var(--accent)', color: '#fff' }}
          {...hoverAccent}
        >
          新建知识库
        </button>
      </div>

      {/* ---- Filter tabs ---- */}
      <div className="flex gap-2 mb-6">
        {(['all', 'personal', 'department'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className="cursor-pointer px-4 py-1.5 rounded text-sm transition-colors"
            style={
              filter === tab
                ? { background: 'var(--accent)', color: '#fff' }
                : { background: 'var(--bg-card)', color: 'var(--text-secondary)' }
            }
            onMouseEnter={(e) => {
              if (filter !== tab) e.currentTarget.style.color = 'var(--text-primary)';
            }}
            onMouseLeave={(e) => {
              if (filter !== tab) e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            {tab === 'all' ? '全部' : tab === 'personal' ? '个人' : '部门'}
          </button>
        ))}
      </div>

      {/* ---- Error ---- */}
      {error && (
        <div className="rounded p-3 mb-4 text-sm" style={{ background: 'var(--danger-muted)', color: 'var(--danger)' }}>{error}</div>
      )}

      {/* ---- Loading ---- */}
      {loading && <p style={{ color: 'var(--text-muted)' }}>加载中...</p>}

      {/* ---- KB Cards ---- */}
      {!loading && filtered.length === 0 && (
        <p style={{ color: 'var(--text-muted)' }}>暂无知识库</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((kb) => (
          <div key={kb.id} className="rounded-lg p-4 flex flex-col gap-3" style={{ background: 'var(--bg-card)' }}>
            {/* name */}
            <div className="flex items-start justify-between">
              <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{kb.name}</span>
              <span
                className="text-xs px-2 py-0.5 rounded"
                style={
                  kb.scope === 'personal'
                    ? { background: 'var(--accent-surface)', color: 'var(--accent-light)' }
                    : { background: 'var(--success-muted)', color: 'var(--success)' }
                }
              >
                {kb.scope === 'personal' ? '个人' : '部门'}
              </span>
            </div>

            {/* description */}
            {kb.description && <p className="text-sm line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{kb.description}</p>}

            {/* meta */}
            <div className="text-xs flex flex-wrap gap-x-4 gap-y-1" style={{ color: 'var(--text-muted)' }}>
              {kb.department_name && <span>部门: {kb.department_name}</span>}
              <span>文档: {kb.document_count}</span>
              <span>{new Date(kb.created_at).toLocaleDateString('zh-CN')}</span>
            </div>

            {/* actions */}
            <div className="flex gap-2 mt-auto pt-1 flex-wrap">
              <button
                onClick={() => openDocs(kb)}
                className="cursor-pointer rounded px-3 py-1 text-sm transition-colors"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverSurface}
              >
                管理文档
              </button>
              <button
                onClick={() => openShares(kb)}
                className="cursor-pointer rounded px-3 py-1 text-sm transition-colors"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverSurface}
              >
                共享
              </button>
              <button
                onClick={() => handleFeishuSync(kb)}
                className="cursor-pointer rounded px-3 py-1 text-sm transition-colors"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverSurface}
              >
                飞书同步
              </button>
              <button
                onClick={() => handleDeleteKb(kb.id)}
                className="cursor-pointer rounded px-3 py-1 text-sm transition-colors ml-auto"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverDanger}
              >
                删除
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* ================================================================ */}
      {/*  Create KB Modal                                                  */}
      {/* ================================================================ */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="rounded-xl p-6 w-full max-w-md" style={{ background: 'var(--bg-card)' }}>
            <h2 className="text-lg font-bold mb-4">新建知识库</h2>

            <label className="block mb-1 text-sm" style={{ color: 'var(--text-secondary)' }}>名称</label>
            <input
              value={createForm.name}
              onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full rounded px-3 py-2 mb-3 focus:outline-none"
              style={{ background: 'var(--bg-surface)', borderWidth: '1px', borderStyle: 'solid', borderColor: 'var(--border-light)', color: 'var(--text-primary)' }}
              placeholder="知识库名称"
              {...focusAccent}
            />

            <label className="block mb-1 text-sm" style={{ color: 'var(--text-secondary)' }}>描述</label>
            <textarea
              value={createForm.description}
              onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full rounded px-3 py-2 mb-3 focus:outline-none resize-none"
              style={{ background: 'var(--bg-surface)', borderWidth: '1px', borderStyle: 'solid', borderColor: 'var(--border-light)', color: 'var(--text-primary)' }}
              rows={3}
              placeholder="可选描述"
              {...focusAccent}
            />

            <label className="block mb-1 text-sm" style={{ color: 'var(--text-secondary)' }}>范围</label>
            <select
              value={createForm.scope}
              onChange={(e) => setCreateForm((f) => ({ ...f, scope: e.target.value as 'personal' | 'department' }))}
              className="w-full rounded px-3 py-2 mb-5 focus:outline-none"
              style={{ background: 'var(--bg-surface)', borderWidth: '1px', borderStyle: 'solid', borderColor: 'var(--border-light)', color: 'var(--text-primary)' }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border-light)'; }}
            >
              <option value="personal">个人</option>
              <option value="department">部门</option>
            </select>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowCreate(false)}
                className="cursor-pointer rounded px-4 py-2 transition-colors"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverSurface}
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !createForm.name.trim()}
                className="cursor-pointer rounded px-4 py-2 transition-colors disabled:opacity-50"
                style={{ background: 'var(--accent)', color: '#fff' }}
                {...hoverAccent}
              >
                {creating ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/*  Manage Documents Modal                                           */}
      {/* ================================================================ */}
      {activeKb && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="rounded-xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col" style={{ background: 'var(--bg-card)' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">文档管理 — {activeKb.name}</h2>
              <button
                onClick={closeDocs}
                className="cursor-pointer text-xl leading-none transition-colors"
                style={{ color: 'var(--text-muted)' }}
                {...hoverTextPrimary}
              >
                &times;
              </button>
            </div>

            {/* upload */}
            <div className="mb-4">
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="cursor-pointer rounded px-4 py-2 text-sm transition-colors"
                style={{ background: 'var(--accent)', color: '#fff' }}
                {...hoverAccent}
              >
                上传文档
              </button>
            </div>

            {/* doc list */}
            {docsLoading && <p className="text-sm" style={{ color: 'var(--text-muted)' }}>加载中...</p>}

            {!docsLoading && docs.length === 0 && (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>暂无文档</p>
            )}

            <div className="overflow-y-auto flex-1 space-y-2">
              {docs.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded p-3 flex items-center gap-3"
                  style={{ background: 'var(--bg-surface)' }}
                >
                  {/* title */}
                  <span className="flex-1 text-sm truncate" style={{ color: 'var(--text-primary)' }}>{doc.title}</span>

                  {/* source badge */}
                  <span className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>
                    {SOURCE_LABEL[doc.source_type] ?? doc.source_type}
                  </span>

                  {/* status badge */}
                  <span className="text-xs px-2 py-0.5 rounded" style={STATUS_STYLES[doc.status] ?? {}}>
                    {STATUS_LABEL[doc.status] ?? doc.status}
                  </span>

                  {/* chunk count */}
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{doc.chunk_count} chunks</span>

                  {/* delete */}
                  <button
                    onClick={() => handleDeleteDoc(doc.id)}
                    className="cursor-pointer transition-colors text-sm"
                    style={{ color: 'var(--text-muted)' }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>

            {/* close */}
            <div className="flex justify-end mt-4">
              <button
                onClick={closeDocs}
                className="cursor-pointer rounded px-4 py-2 text-sm transition-colors"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverSurface}
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ================================================================ */}
      {/*  Share Modal                                                      */}
      {/* ================================================================ */}
      {shareKb && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
          <div className="rounded-xl p-6 w-full max-w-lg max-h-[80vh] flex flex-col" style={{ background: 'var(--bg-card)' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">共享 — {shareKb.name}</h2>
              <button
                onClick={closeShares}
                className="cursor-pointer text-xl leading-none transition-colors"
                style={{ color: 'var(--text-muted)' }}
                {...hoverTextPrimary}
              >
                &times;
              </button>
            </div>

            {/* search user */}
            <div className="flex gap-2 mb-3">
              <input
                value={shareUsername}
                onChange={(e) => setShareUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearchUsers()}
                className="flex-1 rounded px-3 py-2 text-sm focus:outline-none"
                style={{ background: 'var(--bg-surface)', borderWidth: '1px', borderStyle: 'solid', borderColor: 'var(--border-light)', color: 'var(--text-primary)' }}
                placeholder="输入用户名搜索"
                {...focusAccent}
              />
              <button
                onClick={handleSearchUsers}
                className="cursor-pointer rounded px-4 py-2 text-sm transition-colors"
                style={{ background: 'var(--accent)', color: '#fff' }}
                {...hoverAccent}
              >
                搜索
              </button>
            </div>

            {shareError && (
              <div className="rounded p-2 mb-3 text-xs" style={{ background: 'var(--danger-muted)', color: 'var(--danger)' }}>{shareError}</div>
            )}

            {/* search results */}
            {shareSearchResults.length > 0 && (
              <div className="mb-4 space-y-1">
                {shareSearchResults.map((u) => (
                  <div key={u.id} className="rounded p-2 flex items-center justify-between" style={{ background: 'var(--bg-surface)' }}>
                    <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{u.display_name} ({u.username})</span>
                    <button
                      onClick={() => handleAddShare(u.id)}
                      className="cursor-pointer text-sm transition-colors"
                      style={{ color: 'var(--accent-light)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.8'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}
                    >
                      添加
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* shared users list */}
            <div className="pt-3 mt-1" style={{ borderTop: '1px solid var(--border-light)' }}>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>已共享用户</p>
              {sharesLoading && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>加载中...</p>}
              {!sharesLoading && shares.length === 0 && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>未共享给任何用户</p>
              )}
              <div className="space-y-1 overflow-y-auto max-h-48">
                {shares.map((s) => (
                  <div key={s.id} className="rounded p-2 flex items-center justify-between" style={{ background: 'var(--bg-surface)' }}>
                    <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{s.shared_with_username}</span>
                    <button
                      onClick={() => handleRemoveShare(s.id)}
                      className="cursor-pointer transition-colors text-xs"
                      style={{ color: 'var(--text-muted)' }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--danger)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
                    >
                      移除
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* close */}
            <div className="flex justify-end mt-4">
              <button
                onClick={closeShares}
                className="cursor-pointer rounded px-4 py-2 text-sm transition-colors"
                style={{ border: '1px solid var(--border-light)', color: 'var(--text-muted)', background: 'transparent' }}
                {...hoverSurface}
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
