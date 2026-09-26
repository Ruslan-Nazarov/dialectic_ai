import { useState, useEffect, useRef } from 'react'
import { Terminal, Send, Activity, Cpu, Zap, RefreshCw, BarChart3, ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'
import './index.css'
import V2Observability from './components/V2Observability'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8123/api';

const STATUS_LABELS = {
  pending: 'В очереди',
  running: 'Выполняется',
  completed: 'Завершён',
  error: 'Ошибка',
};

function App() {
  const [agentGoal, setAgentGoal] = useState(() => localStorage.getItem('dialectic-agent-goal') || '');
  const [task, setTask] = useState('');
  const [conversationReply, setConversationReply] = useState('');
  const [provider, setProvider] = useState('mock');
  const [providers, setProviders] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [loading, setLoading] = useState(false);

  // Resizing state for vertical split
  const [logsHeight, setLogsHeight] = useState(500);
  const [isDragging, setIsDragging] = useState(false);
  const startDragYRef = useRef(0);
  const startHeightRef = useRef(500);

  useEffect(() => {
    fetchRuns();
    fetchProviders();
    const interval = setInterval(() => {
      fetchRuns();
      fetchProviders();
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    localStorage.setItem('dialectic-agent-goal', agentGoal);
  }, [agentGoal]);

  const fetchProviders = async () => {
    try {
      const res = await fetch(`${API_BASE}/providers`);
      const data = await res.json();
      if (data.providers) {
        setProviders(data.providers);
        setMetrics(data.metrics || null);
        const available = data.providers.find(p => p.id !== 'mock' && p.available);
        setProvider(current => data.providers.some(p => p.id === current && p.available)
          ? current
          : (data.current_provider && data.providers.some(p => p.id === data.current_provider)
            ? data.current_provider
            : (available ? available.id : 'mock')));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const formatNumber = (value) => new Intl.NumberFormat('ru-RU').format(value || 0);
  const selectedProvider = providers.find(p => p.id === provider);
  const providerMetrics = metrics?.by_provider?.[provider];
  const measurementLabel = metrics?.exact_calls > 0 && metrics?.estimated_calls > 0
    ? 'API + оценка'
    : metrics?.exact_calls > 0 ? 'точный учёт' : metrics?.estimated_calls > 0 ? 'оценка' : 'нет вызовов';

  // Handle dragging the vertical resizer divider
  const handleResizerMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
    startDragYRef.current = e.clientY;
    startHeightRef.current = logsHeight;
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e) => {
      const deltaY = startDragYRef.current - e.clientY;
      const newHeight = Math.min(Math.max(startHeightRef.current + deltaY, 200), window.innerHeight - 100);
      setLogsHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const fetchRuns = async () => {
    try {
      const res = await fetch(`${API_BASE}/runs`);
      const data = await res.json();
      if (data.runs) {
        setRuns(data.runs);
        if (!selectedRunId && data.runs.length > 0) {
          setSelectedRunId(data.runs[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleStartRun = async (e) => {
    e.preventDefault();
    if (!agentGoal.trim() || !task.trim() || loading) return;

    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_goal: agentGoal, task: task, provider: provider })
      });
      
      const data = await res.json();
      if (data.run_id) {
        setSelectedRunId(data.run_id);
        setTask('');
        setConversationReply('');
      } else if (data.kind === 'conversation') {
        setTask('');
        setConversationReply(data.message || 'Готов к предметной задаче.');
      }
      setTimeout(fetchRuns, 1000);
    } catch (e) {
      console.error(e);
      alert('Ошибка соединения с API');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-root">
      {/* Top Header Bar */}
      <header className="top-header-bar glass-panel">
        <div className="top-brand">
          <Cpu size={20} className="brand-icon" />
          <div className="brand-text">
            <span className="brand-name">DIALECTIC AI</span>
            <span className="brand-sub">RUNTIME V2</span>
          </div>
        </div>

        <div className="top-metrics-ctrl">
          <div className="metric-chip" title="Фактически учтённые токены ответов моделей">
            <Zap size={13} className="metric-chip-icon zap-icon" />
            <span className="metric-chip-val">{formatNumber(metrics?.total_tokens)}</span>
            <span className="metric-chip-lbl">токенов</span>
          </div>
          <div className="metric-chip">
            <Activity size={13} className="metric-chip-icon act-icon" />
            <span className="metric-chip-val">{formatNumber(metrics?.total_calls)}</span>
            <span className="metric-chip-lbl">LLM-вызовов</span>
          </div>
          <span className={`measurement-badge ${metrics?.exact_calls ? 'exact' : ''}`}>{measurementLabel}</span>
          <button 
            className="refresh-btn" 
            onClick={fetchRuns} 
            title="Обновить список Runs"
          >
            <RefreshCw size={13} /> Обновить
          </button>
        </div>
      </header>

      {/* Main Two-Column Layout */}
      <div className="app-container">
        
        {/* Sidebar: Runs */}
        <div className="sidebar">
          <div className="glass-panel section sidebar-panel" style={{ flex: 1 }}>
            <h2 className="section-title"><Activity size={18} /> Active Runs</h2>
            
            <div className={`agent-list ${selectedRunId ? 'compact-list' : ''}`}>
              {runs.length === 0 && <div className="agent-meta">Нет активных запусков</div>}
              {runs.slice().reverse().map(run => (
                <div
                  key={run.id}
                  className={`agent-card ${selectedRunId === run.id ? 'active' : ''}`}
                  onClick={() => setSelectedRunId(run.id)}
                  title={run.error || run.goal}
                >
                  <div className="agent-name">{run.goal || `Run: ${run.id}`}</div>
                  <div className="agent-meta">
                    <span>{run.provider || 'mock'}</span>
                    <span className={`status-badge status-${run.status || 'pending'}`}>
                      {STATUS_LABELS[run.status] || run.status || 'В очереди'}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Start New Run */}
            <div className="test-sandbox fadeIn" style={{marginTop: 'auto'}}>
              <div className="sandbox-top-bar">
                <div className="sandbox-agent-label">
                  <Terminal size={15} className="sandbox-agent-icon" />
                  <div className="sandbox-agent-name">Запустить новый Goal</div>
                </div>
              </div>
              <form onSubmit={handleStartRun} className="run-launch-form">
                <div className="form-label">Модель</div>
                <div className="provider-grid" role="radiogroup" aria-label="LLM-провайдер">
                  {providers.map(p => (
                    <button key={p.id} type="button" role="radio"
                      aria-checked={provider === p.id}
                      className={`provider-card ${provider === p.id ? 'selected' : ''}`}
                      onClick={() => p.available && setProvider(p.id)}
                      disabled={loading || !p.available}>
                      <span className="provider-card-name">{p.name}</span>
                      <span className="provider-card-model">{p.available ? p.model : 'нет ключа'}</span>
                    </button>
                  ))}
                </div>
                <label className="form-label" htmlFor="agent-goal-input">Цель агента <span>постоянная</span></label>
                <textarea id="agent-goal-input" className="goal-input agent-purpose-input" rows="3"
                  placeholder="Например: анализировать архитектуру ПО и находить противоречия"
                  value={agentGoal}
                  onChange={e => setAgentGoal(e.target.value)}
                  disabled={loading}
                />
                <label className="form-label" htmlFor="task-input">Текущая задача <span>для диалектического пути</span></label>
                <textarea id="task-input" className="goal-input" rows="4"
                  placeholder="Конкретная предметная задача агенту"
                  value={task}
                  onChange={e => setTask(e.target.value)}
                  disabled={loading}
                />
                {conversationReply && <div className="conversation-reply">{conversationReply}</div>}
                <button type="submit" className="launch-btn" disabled={loading || !agentGoal.trim() || !task.trim()}>
                  {loading ? <Activity size={15} className="spin-icon" /> : <Send size={15} />}
                  {loading ? 'Запускаем…' : 'Построить и выполнить путь'}
                </button>
                <div className="selected-provider-note">
                  <span>{selectedProvider?.description || 'Локальная симуляция протокола'}</span>
                  <strong>{formatNumber(providerMetrics?.total_tokens)} токенов · {formatNumber(providerMetrics?.calls)} вызовов</strong>
                </div>
              </form>
            </div>

            <div className="usage-panel">
              <div className="usage-panel-title"><BarChart3 size={15} /> Расход токенов</div>
              <div className="usage-values">
                <div><ArrowDownToLine size={13} /><span>Вход</span><strong>{formatNumber(metrics?.prompt_tokens)}</strong></div>
                <div><ArrowUpFromLine size={13} /><span>Выход</span><strong>{formatNumber(metrics?.completion_tokens)}</strong></div>
              </div>
              <div className="usage-footnote">
                Обновляется раз в 2 секунды. Квота аккаунта провайдером не передаётся.
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="main-content">
          <div 
            className="glass-panel section logs-area"
            style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
          >
            <div className="log-container" style={{ flex: 1, padding: 0 }}>
              {selectedRunId ? (
                <V2Observability runId={selectedRunId} />
              ) : (
                <div className="log-empty-hint" style={{margin: '2rem'}}>
                  Выберите Run слева или запустите новую задачу.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
