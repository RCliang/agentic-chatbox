import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import type { Skill, SkillToolItem, SkillRefItem, SkillExampleItem } from '../types';

/* ------------------------------------------------------------------ */
/*  Form types                                                         */
/* ------------------------------------------------------------------ */

interface SkillFormData {
  name: string;
  description: string;
  instructions: string;
  tools: SkillToolItem[];
  references: SkillRefItem[];
  examples: SkillExampleItem[];
}

const EMPTY_FORM: SkillFormData = {
  name: '',
  description: '',
  instructions: '',
  tools: [],
  references: [],
  examples: [],
};

const EMPTY_TOOL: SkillToolItem = { name: '', when: '', required: false };
const EMPTY_REF: SkillRefItem = { type: 'text', source: '', title: '', inject: 'on_demand' };
const EMPTY_EXAMPLE: SkillExampleItem = { user: '', assistant: '' };

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function SkillsPage() {
  const navigate = useNavigate();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<SkillFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  // collapsible sections in cards
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  // hover / focus state for styled buttons/inputs
  const [submitHover, setSubmitHover] = useState(false);

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
      instructions: skill.instructions,
      tools: skill.tools ?? [],
      references: skill.references ?? [],
      examples: skill.examples ?? [],
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
      instructions: form.instructions,
      tools: form.tools.length > 0 ? form.tools.filter((t) => t.name.trim()) : null,
      references: form.references.length > 0 ? form.references.filter((r) => r.source.trim()) : null,
      examples: form.examples.length > 0 ? form.examples.filter((ex) => ex.user.trim()) : null,
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
    if (!confirm('确定要删除该 Skill 吗？')) return;
    setError('');
    try {
      await api.delete(`/api/skills/${id}`);
      await fetchSkills();
    } catch {
      setError('Failed to delete skill.');
    }
  };

  /* ---- form array helpers ---- */

  const updateTool = (idx: number, patch: Partial<SkillToolItem>) => {
    setForm((f) => ({
      ...f,
      tools: f.tools.map((t, i) => (i === idx ? { ...t, ...patch } : t)),
    }));
  };

  const updateRef = (idx: number, patch: Partial<SkillRefItem>) => {
    setForm((f) => ({
      ...f,
      references: f.references.map((r, i) => (i === idx ? { ...r, ...patch } : r)),
    }));
  };

  const updateExample = (idx: number, patch: Partial<SkillExampleItem>) => {
    setForm((f) => ({
      ...f,
      examples: f.examples.map((ex, i) => (i === idx ? { ...ex, ...patch } : ex)),
    }));
  };

  /* ---- shared inline styles ---- */

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-light)',
    color: 'var(--text-primary)',
  };

  const inputFocusStyle: React.CSSProperties = {
    ...inputStyle,
    borderColor: 'var(--accent)',
  };

  /* ---- render ---- */

  const inputCls = 'w-full rounded px-3 py-2 text-sm focus:outline-none';
  const labelCls = 'block text-xs font-medium mb-1';
  const sectionTitleCls = 'text-sm font-semibold mb-2 flex items-center justify-between';

  /** Helper: returns props for an input/textarea/select with focus border handling */
  const inputProps = (extraCls = '') => ({
    className: `${inputCls} ${extraCls}`,
    style: inputStyle,
    onFocus: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      e.currentTarget.style.borderColor = 'var(--accent)';
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      e.currentTarget.style.borderColor = 'var(--border-light)';
    },
  });

  return (
    <div className="min-h-screen p-8" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="cursor-pointer transition-colors"
            style={{ color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
            title="返回聊天"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold">Skill 管理</h1>
        </div>
        <button
          onClick={openCreate}
          className="px-4 py-2 rounded-lg transition-colors font-medium cursor-pointer"
          style={{ background: 'var(--accent)', color: '#fff' }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--accent)')}
        >
          新建 Skill
        </button>
      </div>

      {error && <p className="text-sm mb-4" style={{ color: 'var(--danger)' }}>{error}</p>}

      {/* Skill cards */}
      {loading ? (
        <p style={{ color: 'var(--text-secondary)' }}>Loading...</p>
      ) : skills.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>No skills found.</p>
      ) : (
        <div className="grid gap-4">
          {skills.map((skill) => {
            const isExpanded = expandedCard === skill.id;
            const toolCount = skill.tools?.length ?? 0;
            const refCount = skill.references?.length ?? 0;
            const exCount = skill.examples?.length ?? 0;

            return (
              <div
                key={skill.id}
                className="rounded-lg p-4 border-l-2"
                style={{
                  background: 'var(--bg-card)',
                  borderLeftColor: skill.is_builtin ? 'var(--accent)' : 'var(--success)',
                }}
              >
                {/* Top row */}
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{skill.name}</span>
                  <span
                    className="text-xs px-2 py-0.5 rounded"
                    style={
                      skill.is_builtin
                        ? { background: 'var(--accent-surface)', color: 'var(--accent-light)' }
                        : { background: 'var(--success-muted)', color: 'var(--success)' }
                    }
                  >
                    {skill.is_builtin ? '内置' : '自定义'}
                  </span>
                  {/* Module counts */}
                  <div className="flex gap-2 ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>
                    {toolCount > 0 && <span>{toolCount} tools</span>}
                    {refCount > 0 && <span>{refCount} refs</span>}
                    {exCount > 0 && <span>{exCount} examples</span>}
                  </div>
                </div>

                {skill.description && (
                  <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>{skill.description}</p>
                )}

                {/* Expand toggle */}
                <button
                  onClick={() => setExpandedCard(isExpanded ? null : skill.id)}
                  className="text-xs mb-2 cursor-pointer"
                  style={{ color: 'var(--accent-light)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
                  onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                >
                  {isExpanded ? '收起详情 ▲' : '展开详情 ▼'}
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="mt-2 space-y-3 text-sm">
                    {/* Instructions */}
                    <div>
                      <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Instructions</p>
                      <pre
                        className="rounded p-3 text-xs whitespace-pre-wrap"
                        style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                      >
                        {skill.instructions}
                      </pre>
                    </div>

                    {/* Tools */}
                    {skill.tools && skill.tools.length > 0 && (
                      <div>
                        <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Tools</p>
                        <div className="space-y-1">
                          {skill.tools.map((t, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-2 rounded px-3 py-1.5 text-xs"
                              style={{ background: 'var(--bg-primary)' }}
                            >
                              <span className="font-mono" style={{ color: 'var(--success)' }}>{t.name}</span>
                              <span
                                className="px-1.5 py-0.5 rounded text-[10px]"
                                style={
                                  t.required
                                    ? { background: 'var(--danger-muted)', color: 'var(--danger)' }
                                    : { background: 'var(--bg-surface)', color: 'var(--text-muted)' }
                                }
                              >
                                {t.required ? '必需' : '按需'}
                              </span>
                              <span className="truncate" style={{ color: 'var(--text-muted)' }}>{t.when}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* References */}
                    {skill.references && skill.references.length > 0 && (
                      <div>
                        <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>References</p>
                        <div className="space-y-1">
                          {skill.references.map((r, i) => (
                            <div
                              key={i}
                              className="rounded px-3 py-1.5 text-xs"
                              style={{ background: 'var(--bg-primary)' }}
                            >
                              <div className="flex items-center gap-2 mb-1">
                                <span style={{ color: 'var(--accent-light)' }}>[{r.type}]</span>
                                <span className="font-medium" style={{ color: 'var(--text-primary)' }}>{r.title || '(untitled)'}</span>
                                <span
                                  className="px-1.5 py-0.5 rounded text-[10px]"
                                  style={
                                    r.inject === 'always'
                                      ? { background: 'var(--success-muted)', color: 'var(--success)' }
                                      : { background: 'var(--warning-muted)', color: 'var(--warning)' }
                                  }
                                >
                                  {r.inject === 'always' ? '始终注入' : '按需注入'}
                                </span>
                              </div>
                              <p className="truncate" style={{ color: 'var(--text-muted)' }}>{r.source}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Examples */}
                    {skill.examples && skill.examples.length > 0 && (
                      <div>
                        <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Examples</p>
                        <div className="space-y-2">
                          {skill.examples.map((ex, i) => (
                            <div
                              key={i}
                              className="rounded px-3 py-2 text-xs space-y-1"
                              style={{ background: 'var(--bg-primary)' }}
                            >
                              <p><span style={{ color: 'var(--accent-light)' }}>User:</span> <span style={{ color: 'var(--text-primary)' }}>{ex.user}</span></p>
                              <p><span style={{ color: 'var(--success)' }}>Assistant:</span> <span style={{ color: 'var(--text-secondary)' }}>{ex.assistant}</span></p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => openEdit(skill)}
                    className="text-sm px-3 py-1 rounded cursor-pointer transition-colors"
                    style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => !skill.is_builtin && handleDelete(skill.id)}
                    disabled={skill.is_builtin}
                    className={`text-sm px-3 py-1 rounded transition-colors ${skill.is_builtin ? 'cursor-not-allowed' : 'cursor-pointer'}`}
                    style={{
                      background: 'var(--bg-surface)',
                      color: skill.is_builtin ? 'var(--text-muted)' : 'var(--danger)',
                    }}
                    onMouseEnter={(e) => { if (!skill.is_builtin) e.currentTarget.style.opacity = '0.7'; }}
                    onMouseLeave={(e) => { if (!skill.is_builtin) e.currentTarget.style.opacity = '1'; }}
                  >
                    删除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ---- Modal ---- */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={closeModal} />
          <div
            className="relative rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
            style={{ background: 'var(--bg-card)' }}
          >
            <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
              {editingId ? '编辑 Skill' : '新建 Skill'}
            </h2>

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelCls} style={{ color: 'var(--text-secondary)' }}>名称 *</label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    {...inputProps()}
                    placeholder="Skill 名称"
                  />
                </div>
                <div>
                  <label className={labelCls} style={{ color: 'var(--text-secondary)' }}>描述</label>
                  <input
                    type="text"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    {...inputProps()}
                    placeholder="简短描述"
                  />
                </div>
              </div>

              {/* Instructions */}
              <div>
                <label className={labelCls} style={{ color: 'var(--text-secondary)' }}>Instructions *</label>
                <textarea
                  required
                  value={form.instructions}
                  onChange={(e) => setForm({ ...form, instructions: e.target.value })}
                  rows={5}
                  {...inputProps('resize-y')}
                  placeholder="核心系统指令，始终注入到 Agent..."
                />
              </div>

              {/* ---- Tools Section ---- */}
              <div className="rounded-lg p-3" style={{ border: '1px solid var(--border-light)' }}>
                <div className={sectionTitleCls} style={{ color: 'var(--text-primary)' }}>
                  <span>Tools ({form.tools.length})</span>
                  <button
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, tools: [...f.tools, { ...EMPTY_TOOL }] }))}
                    className="text-xs cursor-pointer"
                    style={{ color: 'var(--accent-light)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >
                    + 添加
                  </button>
                </div>
                {form.tools.map((t, i) => (
                  <div key={i} className="flex items-start gap-2 mb-2">
                    <input
                      value={t.name}
                      onChange={(e) => updateTool(i, { name: e.target.value })}
                      {...inputProps('w-32 shrink-0')}
                      placeholder="工具名"
                    />
                    <input
                      value={t.when}
                      onChange={(e) => updateTool(i, { when: e.target.value })}
                      {...inputProps('flex-1')}
                      placeholder="何时使用"
                    />
                    <label className="flex items-center gap-1 text-xs shrink-0 mt-2 cursor-pointer" style={{ color: 'var(--text-secondary)' }}>
                      <input
                        type="checkbox"
                        checked={t.required}
                        onChange={(e) => updateTool(i, { required: e.target.checked })}
                        style={{ accentColor: 'var(--accent)' }}
                      />
                      必需
                    </label>
                    <button
                      type="button"
                      onClick={() => setForm((f) => ({ ...f, tools: f.tools.filter((_, j) => j !== i) }))}
                      className="text-xs shrink-0 mt-2 cursor-pointer"
                      style={{ color: 'var(--danger)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
                      onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                    >
                      ✕
                    </button>
                  </div>
                ))}
                {form.tools.length === 0 && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>暂无工具配置</p>}
              </div>

              {/* ---- References Section ---- */}
              <div className="rounded-lg p-3" style={{ border: '1px solid var(--border-light)' }}>
                <div className={sectionTitleCls} style={{ color: 'var(--text-primary)' }}>
                  <span>References ({form.references.length})</span>
                  <button
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, references: [...f.references, { ...EMPTY_REF }] }))}
                    className="text-xs cursor-pointer"
                    style={{ color: 'var(--accent-light)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >
                    + 添加
                  </button>
                </div>
                {form.references.map((r, i) => (
                  <div key={i} className="mb-3 rounded p-2 space-y-2" style={{ background: 'var(--bg-primary)' }}>
                    <div className="flex gap-2">
                      <select
                        value={r.type}
                        onChange={(e) => updateRef(i, { type: e.target.value as SkillRefItem['type'] })}
                        {...inputProps('w-36 shrink-0')}
                      >
                        <option value="text">文本</option>
                        <option value="knowledge_base">知识库</option>
                        <option value="url">URL</option>
                      </select>
                      <input
                        value={r.title}
                        onChange={(e) => updateRef(i, { title: e.target.value })}
                        {...inputProps('flex-1')}
                        placeholder="标题"
                      />
                      <select
                        value={r.inject}
                        onChange={(e) => updateRef(i, { inject: e.target.value as SkillRefItem['inject'] })}
                        {...inputProps('w-28 shrink-0')}
                      >
                        <option value="always">始终注入</option>
                        <option value="on_demand">按需注入</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, references: f.references.filter((_, j) => j !== i) }))}
                        className="text-xs shrink-0 cursor-pointer"
                        style={{ color: 'var(--danger)' }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                      >
                        ✕
                      </button>
                    </div>
                    <textarea
                      value={r.source}
                      onChange={(e) => updateRef(i, { source: e.target.value })}
                      rows={2}
                      {...inputProps('resize-y')}
                      placeholder={r.type === 'knowledge_base' ? '知识库 ID' : r.type === 'url' ? 'https://...' : '参考文本内容...'}
                    />
                  </div>
                ))}
                {form.references.length === 0 && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>暂无参考资料</p>}
              </div>

              {/* ---- Examples Section ---- */}
              <div className="rounded-lg p-3" style={{ border: '1px solid var(--border-light)' }}>
                <div className={sectionTitleCls} style={{ color: 'var(--text-primary)' }}>
                  <span>Examples ({form.examples.length})</span>
                  <button
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, examples: [...f.examples, { ...EMPTY_EXAMPLE }] }))}
                    className="text-xs cursor-pointer"
                    style={{ color: 'var(--accent-light)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.8')}
                    onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                  >
                    + 添加
                  </button>
                </div>
                {form.examples.map((ex, i) => (
                  <div key={i} className="mb-3 rounded p-2 space-y-2" style={{ background: 'var(--bg-primary)' }}>
                    <div className="flex items-start gap-2">
                      <div className="flex-1 space-y-2">
                        <div>
                          <label className="text-[10px]" style={{ color: 'var(--accent-light)' }}>User</label>
                          <textarea
                            value={ex.user}
                            onChange={(e) => updateExample(i, { user: e.target.value })}
                            rows={2}
                            {...inputProps('resize-y')}
                            placeholder="用户输入示例"
                          />
                        </div>
                        <div>
                          <label className="text-[10px]" style={{ color: 'var(--success)' }}>Assistant</label>
                          <textarea
                            value={ex.assistant}
                            onChange={(e) => updateExample(i, { assistant: e.target.value })}
                            rows={2}
                            {...inputProps('resize-y')}
                            placeholder="期望的助手回复"
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, examples: f.examples.filter((_, j) => j !== i) }))}
                        className="text-xs shrink-0 mt-4 cursor-pointer"
                        style={{ color: 'var(--danger)' }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
                {form.examples.length === 0 && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>暂无示例对话</p>}
              </div>

              {error && <p className="text-sm" style={{ color: 'var(--danger)' }}>{error}</p>}

              {/* Buttons */}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 rounded cursor-pointer transition-colors"
                  style={{ color: 'var(--text-secondary)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded cursor-pointer disabled:opacity-50 transition-colors"
                  style={{
                    background: submitHover ? 'var(--accent-hover)' : 'var(--accent)',
                    color: '#fff',
                  }}
                  onMouseEnter={() => setSubmitHover(true)}
                  onMouseLeave={() => setSubmitHover(false)}
                >
                  {submitting ? 'Saving...' : editingId ? '更新' : '创建'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
