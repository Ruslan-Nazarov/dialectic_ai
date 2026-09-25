import React, { useState, useEffect } from 'react';
import { Activity, AlertCircle, RefreshCw, GitCommit, Target, CheckCircle2, ArrowRight } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8123/api';

const RUN_STATUS_LABELS = {
  pending: 'В очереди — агент ещё не начал работу',
  running: 'Выполняется',
  completed: 'Завершён',
  error: 'Завершён с ошибкой',
};

export default function V2Observability({ runId }) {
  const [snapshot, setSnapshot] = useState(null);
  const [runStatus, setRunStatus] = useState(null);
  const [runError, setRunError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchV2State = async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const url = `${API_BASE}/state?run_id=${runId}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Network error');
      const data = await res.json();
      setSnapshot(data.snapshot || null);
      setRunStatus(data.status || null);
      setRunError(data.error || null);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить Runtime V2 State.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSnapshot(null);
    setRunStatus(null);
    setRunError(null);
    fetchV2State();
    const interval = setInterval(fetchV2State, 2000);
    return () => clearInterval(interval);
  }, [runId]);

  const statusBanner = (runStatus && runStatus !== 'running') ? (
    <div className={`v2-run-status v2-run-status-${runStatus}`}>
      <strong>{RUN_STATUS_LABELS[runStatus] || runStatus}</strong>
      {runError && <div style={{marginTop: 4}}>{runError}</div>}
    </div>
  ) : null;

  if (!snapshot) {
    return (
      <div className="v2-observability-container">
        <div className="v2-header">
           <h3 style={{display: 'flex', alignItems: 'center', gap: '8px', margin: 0}}>
             <Activity size={18} /> Runtime V2 Explorer
           </h3>
        </div>
        {statusBanner}
        {loading && !runStatus ? <div className="log-empty-hint">Загрузка...</div> : null}
        {!loading && !runStatus && <div className="log-empty-hint">Нет данных о запуске.</div>}
        {runStatus === 'pending' && <div className="log-empty-hint">Агент запускается, состояние ещё не создано...</div>}
      </div>
    );
  }

  const {
    goal, direction, allowed_moves, processes, development, designations,
    actions, observations, practice, contradictions, resolutions, completion, timeline
  } = snapshot;

  const renderGoal = () => (
    <div className="v2-section">
      <h4 className="v2-section-title"><Target size={16} /> Goal</h4>
      {goal ? (
        <div className="v2-card">
          <strong>{goal.content}</strong> (Active: {goal.active ? 'Yes' : 'No'})
        </div>
      ) : <div className="v2-empty">No active goal</div>}
    </div>
  );

  const renderSimplest = () => {
    const s_des = designations.filter(d => d.role === "simplest" || d.role === "candidate_simplest");
    return (
      <div className="v2-section">
        <h4 className="v2-section-title">Simplest Candidates & Committed</h4>
        <div className="v2-card-grid">
          {s_des.map(d => {
            const p = processes.find(proc => proc.id === d.process_id);
            return (
              <div key={d.id} className="v2-card">
                <span className="v2-badge">{d.role}</span>
                {p ? p.content : "Unknown Process"}
                <div style={{fontSize: 10, marginTop: 4}}>{d.committed ? "Committed" : "Provisional"}</div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderDevelopment = () => {
    return (
      <div className="v2-section">
        <h4 className="v2-section-title">Development View</h4>
        <div className="v2-tree-list">
          {development.map(rel => {
            const sp = processes.find(p => p.id === rel.source_process_id);
            const ep = processes.find(p => p.id === rel.emergent_process_id);
            return (
              <div key={rel.id} className="v2-card">
                <div style={{display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap'}}>
                  <span className="v2-node">{sp ? sp.content : rel.source_process_id}</span>
                  <ArrowRight size={14} />
                  <span className="v2-node">{ep ? ep.content : rel.emergent_process_id}</span>
                </div>
                <div style={{fontSize: 11, marginTop: 8, color: '#aaa'}}>
                  <div><strong>Containment:</strong> {rel.potential_containment}</div>
                  <div><strong>Emergence:</strong> {rel.emergence}</div>
                  <div><strong>Concretization:</strong> {rel.concretization}</div>
                  <div><strong>New Content:</strong> {rel.new_content}</div>
                </div>
                <div style={{fontSize: 10, marginTop: 4}}>{rel.committed ? "Committed" : "Provisional"}</div>
              </div>
            );
          })}
          {development.length === 0 && <div className="v2-empty">No development relations.</div>}
        </div>
      </div>
    );
  };

  const renderOppositeAndContradiction = () => {
    return (
      <div className="v2-section">
        <h4 className="v2-section-title">Opposites & Contradictions</h4>
        {designations.filter(d => d.role === "opposite").map(d => {
          const p = processes.find(proc => proc.id === d.process_id);
          return (
            <div key={d.id} className="v2-card" style={{marginBottom: 8}}>
              <span className="v2-badge op">Opposite</span>
              {p ? p.content : d.process_id}
              <div style={{fontSize: 11, marginTop: 4, color: '#aaa'}}>{d.justification}</div>
            </div>
          );
        })}
        {contradictions.map(c => (
          <div key={c.id} className="v2-card" style={{borderLeft: '3px solid #f87171'}}>
            <strong>Contradiction Unity</strong> [{c.status}]
            <div style={{fontSize: 11, color: '#aaa'}}>{c.unity_justification}</div>
            <div style={{fontSize: 11, color: '#aaa'}}>{c.developing_unity_description}</div>
            {resolutions.filter(r => r.contradiction_id === c.id).map(r => (
              <div key={r.id} style={{marginTop: 8, padding: 4, background: 'rgba(34, 197, 94, 0.1)', borderRadius: 4}}>
                <strong>{r.confirmed_roadmap_id ? "Оценён по практике:" : "Запланированный скачок:"}</strong> {r.outcome} (Process: {processes.find(p => p.id === r.resolution_process_id)?.content})
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  };

  const renderActionReality = () => {
    return (
      <div className="v2-section">
        <h4 className="v2-section-title">Action &rarr; Reality View</h4>
        {actions.map(act => {
          const obs = observations.find(o => o.action_id === act.id);
          const pa = practice.find(p => p.action_id === act.id);
          return (
            <div key={act.id} className="v2-card">
              <div><strong>Action:</strong> {act.tool_name} (Status: {act.status})</div>
              <div style={{fontSize: 11, color: '#aaa'}}>Why now: {act.why_now}</div>
              <div style={{fontSize: 11, color: '#aaa'}}>Expectation: {act.expectation}</div>
              
              {obs && (
                <div style={{marginTop: 8, padding: 6, background: 'rgba(59, 130, 246, 0.1)', borderRadius: 4}}>
                  <strong>Observation:</strong> {JSON.stringify(obs.raw_result)}
                </div>
              )}
              {pa && (
                <div style={{marginTop: 8, padding: 6, background: 'rgba(168, 85, 247, 0.1)', borderRadius: 4}}>
                  <strong>Practice Assessment:</strong> {pa.expected_actual_relation}
                  <div style={{fontSize: 11}}>{pa.explanation}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const renderDirectionAndMoves = () => (
    <div style={{display: 'flex', gap: 16}}>
      <div className="v2-section" style={{flex: 1}}>
        <h4 className="v2-section-title">Direction</h4>
        <div className="v2-card">
          {direction ? (
            <pre style={{margin: 0, fontSize: 11}}>{JSON.stringify(direction, null, 2)}</pre>
          ) : "None"}
        </div>
      </div>
      <div className="v2-section" style={{flex: 1}}>
        <h4 className="v2-section-title">Allowed Moves</h4>
        <div className="v2-card">
          <ul style={{margin: 0, paddingLeft: 16, fontSize: 11}}>
            {allowed_moves.map(m => <li key={m}>{m}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );

  const renderCompletion = () => {
    if (completion.length === 0) return null;
    const comp = completion[0];
    return (
      <div className="v2-section">
        <h4 className="v2-section-title"><CheckCircle2 size={16} /> Completion</h4>
        <div className="v2-card" style={{border: '1px solid #4ade80'}}>
          <strong>Response:</strong> {comp.final_response}
          <div style={{fontSize: 11, color: '#aaa', marginTop: 4}}>Coverage: {comp.goal_coverage}</div>
          <div style={{fontSize: 11, color: '#aaa'}}>Why further not needed: {comp.why_further_development_not_needed}</div>
        </div>
      </div>
    );
  };

  const renderTimeline = () => {
    return (
      <div className="v2-section" style={{gridColumn: '1 / -1'}}>
        <h4 className="v2-section-title">Execution Timeline</h4>
        <div className="v2-timeline-list">
          {timeline.map((event, i) => (
            <div key={i} className="v2-timeline-event">
              <span className={`v2-badge ${event.event_type === 'proposal_rejected' ? 'op' : ''}`}>
                {event.event_type}
              </span>
              {event.proposal && (
                <div style={{fontSize: 11, marginLeft: 8, flex: 1}}>
                  <strong>{event.proposal.move_type}</strong>
                  {event.validation_error && <div style={{color: '#f87171'}}>Error: {event.validation_error}</div>}
                  {event.proposal.why_this_move_now && <div style={{color: '#aaa'}}>Why: {event.proposal.why_this_move_now}</div>}
                </div>
              )}
            </div>
          ))}
          {timeline.length === 0 && <div className="v2-empty">No events recorded.</div>}
        </div>
      </div>
    );
  };

  return (
    <div className="v2-observability-container">
      <div className="v2-header">
        <h3 style={{display: 'flex', alignItems: 'center', gap: '8px', margin: 0}}>
          <Activity size={18} /> Runtime V2 Explorer
        </h3>
        <div style={{display: 'flex', gap: 8}}>
          <button onClick={fetchV2State} disabled={loading} className="v2-refresh-btn">
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Обновить
          </button>
        </div>
      </div>
      
      {error && <div className="v2-error"><AlertCircle size={14}/> {error}</div>}
      {statusBanner}
      <p>Версий дороги: {snapshot.roadmaps?.length || 0}. Активная: {snapshot.active_roadmap_id || "ещё не принята"}</p>
      <p>Фаза: {snapshot?.phase === "planning" ? "Построение картины мира — инструменты запрещены" : "Исполнение принятой дороги"}</p>

      <div className="v2-grid-layout">
        {renderGoal()}
        {renderDirectionAndMoves()}
        {renderSimplest()}
        {renderDevelopment()}
        {renderOppositeAndContradiction()}
        {renderActionReality()}
        {renderCompletion()}
        {renderTimeline()}
      </div>
    </div>
  );
}
