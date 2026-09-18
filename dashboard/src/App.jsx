import { useState, useEffect, useRef } from 'react'
import { Bot, MessageSquare, Terminal, Lightbulb, Send, Activity, X, Trash2, Cpu, Zap, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react'
import './index.css'

const API_BASE = 'http://127.0.0.1:8123/api';

function App() {
  const [agents, setAgents] = useState([]);
  const [messages, setMessages] = useState([
    { role: 'system', content: 'Привет! Я фреймворк Dialectic AI. Готов помочь вам создать идеального агента.' }
  ]);
  const [input, setInput] = useState('');
  const [frameworkLogs, setFrameworkLogs] = useState([]);
  const [agentThoughts, setAgentThoughts] = useState([]);
  const [activeLogTab, setActiveLogTab] = useState('agent'); // 'agent' | 'framework' | 'all'
  const [proposal, setProposal] = useState('Ожидаю контекст для предложения...');
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [testInput, setTestInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [showProposalModal, setShowProposalModal] = useState(false);

  // Providers & Token Metrics State
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('gigachat');
  const [tokenMetrics, setTokenMetrics] = useState({
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    total_calls: 0,
    by_provider: {}
  });

  // Multi-turn conversational chat storage per agent: { [agentId]: Array<{ role: 'user'|'assistant', content: string, thoughts?: string[] }> }
  const [agentChats, setAgentChats] = useState({});
  
  // Resizing state for vertical split between Chat and Logs
  const [logsHeight, setLogsHeight] = useState(270);
  const [isDragging, setIsDragging] = useState(false);
  const startDragYRef = useRef(0);
  const startHeightRef = useRef(270);

  const messagesEndRef = useRef(null);
  const logsEndRef = useRef(null);
  const sandboxEndRef = useRef(null);

  useEffect(() => {
    fetchAgents();
    fetchProposal();
    fetchProviders();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [frameworkLogs, agentThoughts, activeLogTab]);

  useEffect(() => {
    sandboxEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [agentChats, selectedAgent, testLoading]);

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
      const newHeight = Math.min(Math.max(startHeightRef.current + deltaY, 110), window.innerHeight - 200);
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

  const fetchAgents = async () => {
    try {
      const res = await fetch(`${API_BASE}/agents`);
      const data = await res.json();
      setAgents(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchProposal = async () => {
    try {
      const res = await fetch(`${API_BASE}/proposal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: 'current state' })
      });
      const data = await res.json();
      setProposal(data.proposal);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchProviders = async () => {
    try {
      const res = await fetch(`${API_BASE}/providers`);
      const data = await res.json();
      if (data.providers) {
        setProviders(data.providers);
      }
      if (data.metrics) {
        setTokenMetrics(data.metrics);
      }
      if (data.current_provider && (!selectedProvider || selectedProvider === 'gigachat')) {
        setSelectedProvider(data.current_provider);
      }
    } catch (e) {
      console.error("Failed to load providers:", e);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      
      if (!res.ok) throw new Error("API response not OK");

      const data = await res.json();
      
      setMessages(prev => [...prev, { role: 'system', content: data.reply }]);
      
      if (data.logs) {
        data.logs.forEach((log, i) => {
          setTimeout(() => {
            setFrameworkLogs(prev => [...prev, log]);
          }, i * 300);
        });
        setActiveLogTab('framework');
      }

      if (data.action === 'agent_created') {
        setTimeout(fetchAgents, 2000);
        setTimeout(fetchProposal, 3000);
      }
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'system', content: 'Ошибка соединения с API. Проверьте, работает ли backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleTestAgent = async (e) => {
    e.preventDefault();
    if (!testInput.trim() || !selectedAgent || testLoading) return;
    
    const query = testInput.trim();
    setTestInput('');

    const agentId = selectedAgent.id;
    const previousHistory = agentChats[agentId] || [];
    const updatedHistoryWithUser = [...previousHistory, { role: 'user', content: query }];

    // Optimistically update conversation with user message
    setAgentChats(prev => ({
      ...prev,
      [agentId]: updatedHistoryWithUser
    }));

    setTestLoading(true);
    
    try {
      const res = await fetch(`${API_BASE}/agents/${agentId}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          prompt: query,
          provider: selectedProvider,
          history: previousHistory
        })
      });
      const data = await res.json();
      
      // Append agent reply to persistent chat history
      setAgentChats(prev => ({
        ...prev,
        [agentId]: [
          ...(prev[agentId] || []),
          { role: 'assistant', content: data.result, thoughts: data.agent_thoughts }
        ]
      }));

      // Update tokens
      if (data.tokens) {
        setTokenMetrics(data.tokens);
      } else {
        fetchProviders();
      }

      // Stream thoughts to Under-The-Hood panel
      if (data.agent_thoughts && data.agent_thoughts.length > 0) {
        const runHeader = `[Run] Сессия тестирования "${selectedAgent.name}" [${selectedProvider.toUpperCase()}] -> Запрос: "${query}"`;
        const newThoughts = [runHeader, ...data.agent_thoughts];
        newThoughts.forEach((thought, i) => {
          setTimeout(() => {
            setAgentThoughts(prev => [...prev, thought]);
          }, i * 120);
        });
        setActiveLogTab('agent');
      }
    } catch(e) {
      setAgentChats(prev => ({
        ...prev,
        [agentId]: [
          ...(prev[agentId] || []),
          { role: 'assistant', content: 'Ошибка выполнения теста: ' + e.message }
        ]
      }));
    } finally {
      setTestLoading(false);
    }
  };

  const handleClearAgentChat = (agentId) => {
    if (!agentId) return;
    setAgentChats(prev => ({
      ...prev,
      [agentId]: []
    }));
  };

  const displayedLogs = 
    activeLogTab === 'agent' 
      ? agentThoughts 
      : activeLogTab === 'framework' 
        ? frameworkLogs 
        : [...frameworkLogs, ...agentThoughts];

  const GLUED_WORDS = [
    'простротиворечие', 'противоречие', 'пользователем', 'пользователя', 'пользователь',
    'приветствие', 'сообщениями', 'возвращении', 'игнорировать', 'поздороваться',
    'приздороваться', 'продолжая', 'сообщение', 'получено', 'ответить', 'общения',
    'интернете', 'источники', 'различные', 'диалог', 'привет', 'фактов', 'поиск',
    'обмен', 'про', 'для', 'от', 'на', 'в', 'с'
  ];
  GLUED_WORDS.sort((a, b) => b.length - a.length);

  function formatSpacedText(text) {
    if (!text || typeof text !== 'string') return '';
    let spaced = text.replace(/[а-яёА-ЯЁ]{11,}/g, (token) => {
      let rem = token.toLowerCase();
      let parts = [];
      let i = 0;
      while (i < rem.length) {
        let matched = false;
        for (const w of GLUED_WORDS) {
          if (rem.startsWith(w, i)) {
            parts.push(token.slice(i, i + w.length));
            i += w.length;
            matched = true;
            break;
          }
        }
        if (!matched) {
          let nextI = i + 1;
          while (nextI < rem.length) {
            let found = false;
            for (const w of GLUED_WORDS) {
              if (rem.startsWith(w, nextI)) {
                found = true;
                break;
              }
            }
            if (found) break;
            nextI++;
          }
          parts.push(token.slice(i, nextI));
          i = nextI;
        }
      }
      return parts.join(' ');
    });
    return spaced;
  }

  const renderLogLine = (log, index) => {
    let tag = '';
    let text = log;
    let tagClass = 'tag-default';

    const match = log.match(/^(\[[^\]]+\])\s*(.*)/);
    if (match) {
      tag = match[1];
      text = match[2];
      const lowerTag = tag.toLowerCase();

      if (lowerTag.includes('run')) tagClass = 'tag-run';
      else if (lowerTag.includes('iteration')) tagClass = 'tag-iteration';
      else if (lowerTag.includes('hypothesis')) tagClass = 'tag-hypothesis';
      else if (lowerTag.includes('plan')) tagClass = 'tag-plan';
      else if (lowerTag.includes('decision')) tagClass = 'tag-decision';
      else if (lowerTag.includes('collision')) tagClass = 'tag-collision';
      else if (lowerTag.includes('observation')) tagClass = 'tag-observation';
      else if (lowerTag.includes('contradiction')) tagClass = 'tag-contradiction';
      else if (lowerTag.includes('leap')) tagClass = 'tag-leap';
      else if (lowerTag.includes('synthesis')) tagClass = 'tag-synthesis';
      else if (lowerTag.includes('validation')) tagClass = 'tag-validation';
      else if (lowerTag.includes('architect')) tagClass = 'tag-architect';
      else if (lowerTag.includes('repair')) tagClass = 'tag-repair';
      else if (lowerTag.includes('error')) tagClass = 'tag-error';
      else if (lowerTag.includes('system') || lowerTag.includes('agentbuilder')) tagClass = 'tag-system';
    }

    const cleanFormattedText = formatSpacedText(text);

    return (
      <div key={index} className="log-line">
        {tag && <span className={`log-tag ${tagClass}`}>{tag}</span>}
        <span className="log-text">{cleanFormattedText}</span>
      </div>
    );
  };

  const activeProviderObj = providers.find(p => p.id === selectedProvider) || {
    id: selectedProvider,
    name: selectedProvider,
    available: true,
    model: selectedProvider
  };

  const currentAgentChat = selectedAgent ? (agentChats[selectedAgent.id] || []) : [];

  return (
    <div className="dashboard-root">
      {/* Top Header Bar with Provider Switcher and Metrics */}
      <header className="top-header-bar glass-panel">
        <div className="top-brand">
          <Cpu size={20} className="brand-icon" />
          <div className="brand-text">
            <span className="brand-name">DIALECTIC AI</span>
            <span className="brand-sub">AGENT ENGINE</span>
          </div>
        </div>

        {/* Provider Switcher Controls */}
        <div className="top-provider-ctrl">
          <span className="provider-lbl">Активный LLM:</span>
          <div className="provider-select-wrapper">
            <select
              className="provider-dropdown"
              value={selectedProvider}
              onChange={e => setSelectedProvider(e.target.value)}
              title="Переключить используемый LLM провайдер на лету"
            >
              {providers.map(p => (
                <option key={p.id} value={p.id} disabled={!p.available}>
                  {p.available ? '● ' : '○ '} {p.name} {p.available ? `(${p.model})` : '— нет ключа'}
                </option>
              ))}
            </select>
          </div>
          <div className={`provider-status-badge ${activeProviderObj.available ? 'badge-online' : 'badge-offline'}`}>
            <span className="status-indicator-dot" />
            <span>{activeProviderObj.available ? 'Онлайн' : 'Недоступен'}</span>
          </div>
        </div>

        {/* Real-time Token and Performance Metrics */}
        <div className="top-metrics-ctrl">
          <div className="metric-chip" title="Общее количество обработанных токенов (Prompt + Completion)">
            <Zap size={14} className="metric-chip-icon zap-icon" />
            <span className="metric-chip-val">{tokenMetrics.total_tokens.toLocaleString()}</span>
            <span className="metric-chip-lbl">токенов</span>
          </div>

          <div className="metric-chip" title="Всего запусков и обращений к LLM">
            <Activity size={14} className="metric-chip-icon act-icon" />
            <span className="metric-chip-val">{tokenMetrics.total_calls.toLocaleString()}</span>
            <span className="metric-chip-lbl">вызовов</span>
          </div>

          <button 
            className="refresh-btn" 
            onClick={fetchProviders} 
            title="Обновить статус провайдеров и счетчики токенов"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </header>

      {/* Main Two-Column Layout */}
      <div className="app-container">
        
        {/* Sidebar: Agents Gallery & Sandbox Chat */}
        <div className="sidebar">
          <div className="glass-panel section sidebar-panel" style={{ flex: 1 }}>
            <h2 className="section-title"><Bot size={18} /> Галерея агентов</h2>
            
            <div className={`agent-list ${selectedAgent ? 'compact-list' : ''}`}>
              {agents.length === 0 && <div className="agent-meta">Нет созданных агентов</div>}
              {agents.map(agent => (
                <div 
                  key={agent.id} 
                  className={`agent-card ${selectedAgent?.id === agent.id ? 'active' : ''}`}
                  onClick={() => setSelectedAgent(agent)}
                >
                  <div className="agent-name">{agent.name}</div>
                  <div className="agent-meta">
                    <span>{agent.type}</span>
                    <span className="status-badge">{agent.status}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Interactive Chat Sandbox for Selected Agent */}
            {selectedAgent && (
              <div className="test-sandbox fadeIn">
                <div className="sandbox-top-bar">
                  <div className="sandbox-agent-label">
                    <Bot size={15} className="sandbox-agent-icon" />
                    <div>
                      <div className="sandbox-agent-name">{selectedAgent.name}</div>
                      <div className="sandbox-provider-pill">{selectedProvider.toUpperCase()}</div>
                    </div>
                  </div>
                  <button 
                    className="sandbox-clear-btn"
                    onClick={() => handleClearAgentChat(selectedAgent.id)}
                    title="Очистить историю диалога"
                  >
                    <Trash2 size={12} />
                    <span>Очистить</span>
                  </button>
                </div>

                {/* Chat History List */}
                <div className="sandbox-chat-flow">
                  {currentAgentChat.length === 0 ? (
                    <div className="sandbox-empty-prompt">
                      <MessageSquare size={22} style={{ opacity: 0.35, marginBottom: '6px' }} />
                      <div style={{ fontWeight: 500 }}>Диалог с {selectedAgent.name}</div>
                      <div className="empty-sub">История сохраняется в памяти агента. Отправьте сообщение для начала диалога.</div>
                    </div>
                  ) : (
                    currentAgentChat.map((turn, i) => (
                      <div key={i} className={`sandbox-chat-row ${turn.role}`}>
                        {turn.role === 'assistant' && (
                          <div className="sandbox-bot-avatar">
                            <Bot size={12} />
                          </div>
                        )}
                        <div className={`sandbox-bubble ${turn.role}`}>
                          {turn.role === 'assistant' ? formatSpacedText(turn.content) : turn.content}
                        </div>
                      </div>
                    ))
                  )}

                  {testLoading && (
                    <div className="sandbox-thinking-row">
                      <Activity size={12} className="spin-icon" />
                      <span>Агент размышляет (шаги в "Под капотом")...</span>
                    </div>
                  )}
                  <div ref={sandboxEndRef} />
                </div>

                {/* Chat Input Form */}
                <form onSubmit={handleTestAgent} className="sandbox-input-row">
                  <input 
                    type="text" 
                    className="sandbox-input" 
                    placeholder={`Сообщение для ${selectedAgent.name}...`}
                    value={testInput}
                    onChange={e => setTestInput(e.target.value)}
                    disabled={testLoading}
                  />
                  <button 
                    type="submit" 
                    className="sandbox-send-btn" 
                    disabled={testLoading || !testInput.trim()}
                    title="Отправить сообщение"
                  >
                    {testLoading ? <Activity size={13} className="spin-icon" /> : <Send size={13} />}
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="main-content">
          
          {/* Chat Interface with Dialectic Architect */}
          <div className="glass-panel section chat-area" style={{ flex: 1, position: 'relative' }}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px'}}>
              <h2 className="section-title" style={{marginBottom: 0}}><MessageSquare size={18} /> Chat with Dialectic</h2>
              
              {/* Proposal Trigger Button */}
              <button 
                className="proposal-trigger" 
                onClick={() => setShowProposalModal(true)}
                title="Идеи для новых агентов"
              >
                <Lightbulb size={18} /> Советник
              </button>
            </div>
            
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  {msg.content}
                </div>
              ))}
              {loading && (
                <div className="message system" style={{opacity: 0.7}}>Печатает...</div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-input-container" onSubmit={handleSendMessage}>
              <input 
                type="text" 
                className="chat-input" 
                placeholder="Опишите какого агента вы хотите создать..."
                value={input}
                onChange={e => setInput(e.target.value)}
                disabled={loading}
              />
              <button type="submit" className="send-btn" disabled={loading || !input.trim()}>
                <Send size={20} />
              </button>
            </form>

            {/* Proposal Modal */}
            {showProposalModal && (
              <div className="proposal-modal-overlay" onClick={() => setShowProposalModal(false)}>
                <div className="proposal-modal-content" onClick={e => e.stopPropagation()}>
                  <button className="close-btn" onClick={() => setShowProposalModal(false)}><X size={20} /></button>
                  <h3 style={{color: 'var(--accent-orange)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px'}}>
                    <Lightbulb size={20} /> Next Agent Proposal
                  </h3>
                  <p className="proposal-text" style={{marginBottom: '24px'}}>
                    {proposal}
                  </p>
                  <button 
                    className="proposal-action"
                    onClick={() => {
                      setInput(proposal);
                      setShowProposalModal(false);
                    }}
                  >
                    Использовать как промпт
                  </button>
                </div>
              </div>
            )}

          </div>

          {/* Draggable Vertical Split Resizer */}
          <div 
            className={`split-resizer ${isDragging ? 'dragging' : ''}`}
            onMouseDown={handleResizerMouseDown}
            title="Потяните вверх/вниз для изменения размера рамок"
          >
            <div className="resizer-line" />
            <div className="resizer-pill">
              <span>⋮⋮ ПОТЯНИТЕ ВВЕРХ / ВНИЗ ⋮⋮</span>
            </div>
          </div>

          {/* Logs / Under the hood */}
          <div 
            className="glass-panel section logs-area"
            style={{ height: `${logsHeight}px` }}
          >
            <div className="logs-header">
              <h2 className="section-title" style={{ margin: 0 }}>
                <Terminal size={18} /> Под капотом
              </h2>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <div className="log-tabs">
                  <button 
                    className={`log-tab-btn ${activeLogTab === 'agent' ? 'active' : ''}`}
                    onClick={() => setActiveLogTab('agent')}
                  >
                    🧠 Мышление агента {agentThoughts.length > 0 && <span className="tab-pill">{agentThoughts.length}</span>}
                  </button>
                  <button 
                    className={`log-tab-btn ${activeLogTab === 'framework' ? 'active' : ''}`}
                    onClick={() => setActiveLogTab('framework')}
                  >
                    🛠️ Создание (Фреймворк) {frameworkLogs.length > 0 && <span className="tab-pill">{frameworkLogs.length}</span>}
                  </button>
                  <button 
                    className={`log-tab-btn ${activeLogTab === 'all' ? 'active' : ''}`}
                    onClick={() => setActiveLogTab('all')}
                  >
                    Все ({agentThoughts.length + frameworkLogs.length})
                  </button>
                </div>

                {/* Quick toggle height */}
                <button 
                  className="resize-quick-btn"
                  onClick={() => setLogsHeight(prev => prev > 350 ? 150 : 450)}
                  title={logsHeight > 350 ? "Свернуть панель" : "Развернуть панель на максимум"}
                >
                  {logsHeight > 350 ? "⬇️ Свернуть" : "⬆️ Развернуть"}
                </button>
              </div>
            </div>

            <div className="log-container">
              {displayedLogs.length === 0 && (
                <div className="log-empty-hint">
                  {activeLogTab === 'agent' 
                    ? 'Здесь будут отображаться размышления агента при тестировании: итерации, гипотезы, план, решения и проверки реальностью.'
                    : 'Здесь будут отображаться шаги DialecticalArchitect и логи создания агентов фреймворком.'}
                </div>
              )}
              {displayedLogs.map((log, i) => renderLogLine(log, i))}
              <div ref={logsEndRef} />
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App
