import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import api from '../api/client';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface KnowledgeBase {
  id: number;
  name: string;
  description: string;
  scope: 'personal' | 'department';
  department_name?: string;
  document_count: number;
  created_at: string;
}

interface Document {
  id: number;
  title: string;
  source: 'upload' | 'feishu';
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  chunk_count: number;
  created_at: string;
}

type ScopeFilter = 'all' | 'personal' | 'department';

/* ------------------------------------------------------------------ */
/*  Status / source badge helpers                                      */
/* ------------------------------------------------------------------ */

const STATUS_STYLE: Record<string, string> = {
  pending: 'bg-yellow-900/60 text-yellow-400',
  indexing: 'bg-blue-900/60 text-blue-400',
  ready: 'bg-green-900/60 text-green-400',
  failed: 'bg-red-900/60 text-red-400',
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

  /* ---- fetch KB list ---- */
  const fetchBases = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<{ data: KnowledgeBase[] }>('/api/knowledge/bases');
      setBases(res.data.data ?? []);
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
  const handleDeleteKb = async (id: number) => {
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
      const res = await api.get<{ data: Document[] }>(`/api/knowledge/bases/${kb.id}/documents`);
      setDocs(res.data.data ?? []);
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
      const res = await api.get<{ data: Document[] }>(`/api/knowledge/bases/${activeKb.id}/documents`);
      setDocs(res.data.data ?? []);
    } catch {
      // silent
    }
    // reset file input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  /* ---- delete document ---- */
  const handleDeleteDoc = async (docId: number) => {
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
      await api.post(`/api/knowledge/bases/${kb.id}/sync`);
      fetchBases();
    } catch {
      // silent
    }
  };

  /* ================================================================ */
  /*  Render                                                           */
  /* ================================================================ */

  return (
    <div className="min-h-screen bg-[#0d0d1a] text-gray-200 p-8">
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">知识库管理</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-[#0f3460] text-blue-400 hover:bg-[#1a4a70] rounded px-4 py-2 transition-colors"
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
            className={`px-4 py-1.5 rounded text-sm transition-colors ${
              filter === tab
                ? 'bg-[#0f3460] text-blue-400'
                : 'bg-[#16213e] text-gray-400 hover:text-gray-200'
            }`}
          >
            {tab === 'all' ? '全部' : tab === 'personal' ? '个人' : '部门'}
          </button>
        ))}
      </div>

      {/* ---- Error ---- */}
      {error && (
        <div className="bg-red-900/40 text-red-400 rounded p-3 mb-4 text-sm">{error}</div>
      )}

      {/* ---- Loading ---- */}
      {loading && <p className="text-gray-500">加载中...</p>}

      {/* ---- KB Cards ---- */}
      {!loading && filtered.length === 0 && (
        <p className="text-gray-500">暂无知识库</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((kb) => (
          <div key={kb.id} className="bg-[#16213e] rounded-lg p-4 flex flex-col gap-3">
            {/* name */}
            <div className="flex items-start justify-between">
              <span className="font-bold text-gray-200">{kb.name}</span>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  kb.scope === 'personal'
                    ? 'bg-[#0f3460] text-blue-400'
                    : 'bg-[#2d4a22] text-green-400'
                }`}
              >
                {kb.scope === 'personal' ? '个人' : '部门'}
              </span>
            </div>

            {/* description */}
            {kb.description && <p className="text-gray-400 text-sm line-clamp-2">{kb.description}</p>}

            {/* meta */}
            <div className="text-gray-500 text-xs flex flex-wrap gap-x-4 gap-y-1">
              {kb.department_name && <span>部门: {kb.department_name}</span>}
              <span>文档: {kb.document_count}</span>
              <span>{new Date(kb.created_at).toLocaleDateString('zh-CN')}</span>
            </div>

            {/* actions */}
            <div className="flex gap-2 mt-auto pt-1">
              <button
                onClick={() => openDocs(kb)}
                className="border border-[#333] text-gray-500 hover:bg-[#1a1a2e] rounded px-3 py-1 text-sm transition-colors"
              >
                管理文档
              </button>
              <button
                onClick={() => handleFeishuSync(kb)}
                className="border border-[#333] text-gray-500 hover:bg-[#1a1a2e] rounded px-3 py-1 text-sm transition-colors"
              >
                飞书同步
              </button>
              <button
                onClick={() => handleDeleteKb(kb.id)}
                className="border border-[#333] text-gray-500 hover:bg-red-900/40 hover:text-red-400 rounded px-3 py-1 text-sm transition-colors ml-auto"
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
          <div className="bg-[#16213e] rounded-xl p-6 w-full max-w-md">
            <h2 className="text-lg font-bold mb-4">新建知识库</h2>

            <label className="block mb-1 text-sm text-gray-400">名称</label>
            <input
              value={createForm.name}
              onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 mb-3 focus:outline-none focus:border-blue-500"
              placeholder="知识库名称"
            />

            <label className="block mb-1 text-sm text-gray-400">描述</label>
            <textarea
              value={createForm.description}
              onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 mb-3 focus:outline-none focus:border-blue-500 resize-none"
              rows={3}
              placeholder="可选描述"
            />

            <label className="block mb-1 text-sm text-gray-400">范围</label>
            <select
              value={createForm.scope}
              onChange={(e) => setCreateForm((f) => ({ ...f, scope: e.target.value as 'personal' | 'department' }))}
              className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 mb-5 focus:outline-none focus:border-blue-500"
            >
              <option value="personal">个人</option>
              <option value="department">部门</option>
            </select>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowCreate(false)}
                className="border border-[#333] text-gray-500 hover:bg-[#1a1a2e] rounded px-4 py-2 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !createForm.name.trim()}
                className="bg-[#0f3460] text-blue-400 hover:bg-[#1a4a70] rounded px-4 py-2 transition-colors disabled:opacity-50"
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
          <div className="bg-[#16213e] rounded-xl p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">文档管理 — {activeKb.name}</h2>
              <button
                onClick={closeDocs}
                className="text-gray-500 hover:text-gray-200 text-xl leading-none transition-colors"
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
                className="bg-[#0f3460] text-blue-400 hover:bg-[#1a4a70] rounded px-4 py-2 text-sm transition-colors"
              >
                上传文档
              </button>
            </div>

            {/* doc list */}
            {docsLoading && <p className="text-gray-500 text-sm">加载中...</p>}

            {!docsLoading && docs.length === 0 && (
              <p className="text-gray-500 text-sm">暂无文档</p>
            )}

            <div className="overflow-y-auto flex-1 space-y-2">
              {docs.map((doc) => (
                <div
                  key={doc.id}
                  className="bg-[#1a1a2e] rounded p-3 flex items-center gap-3"
                >
                  {/* title */}
                  <span className="flex-1 text-gray-200 text-sm truncate">{doc.title}</span>

                  {/* source badge */}
                  <span className="text-xs px-2 py-0.5 rounded bg-[#0d0d1a] text-gray-400">
                    {SOURCE_LABEL[doc.source] ?? doc.source}
                  </span>

                  {/* status badge */}
                  <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[doc.status] ?? ''}`}>
                    {STATUS_LABEL[doc.status] ?? doc.status}
                  </span>

                  {/* chunk count */}
                  <span className="text-xs text-gray-500">{doc.chunk_count} chunks</span>

                  {/* delete */}
                  <button
                    onClick={() => handleDeleteDoc(doc.id)}
                    className="text-gray-600 hover:text-red-400 transition-colors text-sm"
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
                className="border border-[#333] text-gray-500 hover:bg-[#1a1a2e] rounded px-4 py-2 text-sm transition-colors"
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
