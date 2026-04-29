import { useEffect, useState } from 'react';
import api from '../api/client';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Skill {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  tool_ids: string[] | null;
  knowledge_base_id: string | null;
  is_builtin: boolean;
  created_at: string;
}

interface SkillFormData {
  name: string;
  description: string;
  system_prompt: string;
  tool_ids: string; // comma-separated string in the form
}

const EMPTY_FORM: SkillFormData = {
  name: '',
  description: '',
  system_prompt: '',
  tool_ids: '',
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function parseToolIds(raw: string): string[] | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  return trimmed
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

function toolIdsToForm(ids: string[] | null): string {
  if (!ids || ids.length === 0) return '';
  return ids.join(', ');
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<SkillFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  /* ---- fetch ---- */

  const fetchSkills = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get<Skill[]>('/api/skills');
      setSkills(res.data);
    } catch {
      setError('Failed to load skills.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSkills();
  }, []);

  /* ---- modal helpers ---- */

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (skill: Skill) => {
    setEditingId(skill.id);
    setForm({
      name: skill.name,
      description: skill.description ?? '',
      system_prompt: skill.system_prompt,
      tool_ids: toolIdsToForm(skill.tool_ids),
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
  };

  /* ---- CRUD ---- */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    const payload = {
      name: form.name,
      description: form.description || null,
      system_prompt: form.system_prompt,
      tool_ids: parseToolIds(form.tool_ids),
    };

    try {
      if (editingId) {
        await api.put(`/api/skills/${editingId}`, payload);
      } else {
        await api.post('/api/skills', payload);
      }
      closeModal();
      await fetchSkills();
    } catch {
      setError(editingId ? 'Failed to update skill.' : 'Failed to create skill.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this skill?')) return;
    setError('');
    try {
      await api.delete(`/api/skills/${id}`);
      await fetchSkills();
    } catch {
      setError('Failed to delete skill.');
    }
  };

  /* ---- render ---- */

  return (
    <div className="min-h-screen bg-[#0d0d1a] text-gray-200 p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Skill 管理</h1>
        <button
          onClick={openCreate}
          className="px-4 py-2 bg-[#0f3460] text-blue-400 rounded-lg hover:bg-[#0f3460]/80 transition-colors font-medium"
        >
          新建 Skill
        </button>
      </div>

      {/* Error */}
      {error && (
        <p className="text-red-400 text-sm mb-4">{error}</p>
      )}

      {/* Loading */}
      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : skills.length === 0 ? (
        <p className="text-gray-500">No skills found.</p>
      ) : (
        <div className="grid gap-4">
          {skills.map((skill) => (
            <div
              key={skill.id}
              className={`bg-[#16213e] rounded-lg p-4 border-l-2 ${
                skill.is_builtin
                  ? 'border-red-500'
                  : 'border-green-500'
              }`}
            >
              {/* Top row: name + badge */}
              <div className="flex items-center gap-3 mb-2">
                <span className="font-bold text-gray-200">{skill.name}</span>
                {skill.is_builtin ? (
                  <span className="text-xs px-2 py-0.5 rounded bg-[#0f3460] text-blue-400">
                    内置
                  </span>
                ) : (
                  <span className="text-xs px-2 py-0.5 rounded bg-[#2d4a22] text-green-400">
                    自定义
                  </span>
                )}
              </div>

              {/* Description */}
              {skill.description && (
                <p className="text-gray-400 text-sm mb-2">{skill.description}</p>
              )}

              {/* Tool tags */}
              {skill.tool_ids && skill.tool_ids.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {skill.tool_ids.map((tool) => (
                    <span
                      key={tool}
                      className="text-xs px-2 py-0.5 rounded bg-[#1a1a2a] text-green-400"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-2">
                <button
                  onClick={() => openEdit(skill)}
                  className="text-sm px-3 py-1 rounded bg-[#1a1a2e] text-gray-300 hover:bg-[#1a1a2e]/70 transition-colors"
                >
                  编辑
                </button>
                {skill.is_builtin ? (
                  <button
                    disabled
                    className="text-sm px-3 py-1 rounded bg-[#1a1a2e] text-gray-600 cursor-not-allowed"
                    title="Cannot delete builtin skill"
                  >
                    删除
                  </button>
                ) : (
                  <button
                    onClick={() => handleDelete(skill.id)}
                    className="text-sm px-3 py-1 rounded bg-[#1a1a2e] text-red-400 hover:bg-[#1a1a2e]/70 transition-colors"
                  >
                    删除
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---- Modal ---- */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Overlay */}
          <div
            className="absolute inset-0 bg-black/60"
            onClick={closeModal}
          />
          {/* Panel */}
          <div className="relative bg-[#16213e] rounded-xl p-6 w-full max-w-lg mx-4">
            <h2 className="text-lg font-bold text-gray-200 mb-4">
              {editingId ? '编辑 Skill' : '新建 Skill'}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* name */}
              <div>
                <label className="block text-gray-400 text-sm mb-1">名称</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
                  placeholder="Skill name"
                />
              </div>

              {/* description */}
              <div>
                <label className="block text-gray-400 text-sm mb-1">描述</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={2}
                  className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 focus:outline-none focus:border-blue-500 resize-none"
                  placeholder="Brief description"
                />
              </div>

              {/* system_prompt */}
              <div>
                <label className="block text-gray-400 text-sm mb-1">System Prompt</label>
                <textarea
                  required
                  value={form.system_prompt}
                  onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                  rows={6}
                  style={{ minHeight: '150px' }}
                  className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 focus:outline-none focus:border-blue-500 resize-y"
                  placeholder="System prompt for the skill..."
                />
              </div>

              {/* tool_ids */}
              <div>
                <label className="block text-gray-400 text-sm mb-1">Tool IDs</label>
                <input
                  type="text"
                  value={form.tool_ids}
                  onChange={(e) => setForm({ ...form, tool_ids: e.target.value })}
                  className="w-full bg-[#1a1a2e] border border-[#333] text-gray-200 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
                  placeholder="tool_a, tool_b, tool_c"
                />
              </div>

              {/* Error inside modal */}
              {error && (
                <p className="text-red-400 text-sm">{error}</p>
              )}

              {/* Buttons */}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 rounded text-gray-400 hover:text-gray-200 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {submitting
                    ? 'Saving...'
                    : editingId
                      ? '更新'
                      : '创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
