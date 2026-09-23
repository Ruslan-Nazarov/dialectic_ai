"""A roadmap is constructed before practice. A planned leap is not a realized leap."""
import copy
import uuid
from dataclasses import asdict, dataclass, field


@dataclass
class Roadmap:
    id: str
    simplest_id: str
    contradiction_ids: list[str]
    resolution_ids: list[str]
    execution_process_ids: list[str]
    snapshot: dict
    revision_observation_ids: list[str] = field(default_factory=list)
    revision_reason: str = ""


PLANNING_MOVES = {
    'PROPOSE_SIMPLEST', 'ASSESS_SIMPLEST', 'DEVELOP_PROCESS', 'CONNECT_DEVELOPMENT',
    'DESIGNATE_OPPOSITE', 'ESTABLISH_CONTRADICTION', 'PROPOSE_LEAP', 'BEGIN_EXECUTION',
    # COMPLETE is also legal directly from planning -- see the "clear" path in validate_world's
    # COMPLETE branch below: a goal can turn out to have no genuine opposite/contradiction at
    # all (analytical/diagnostic tasks especially), and forcing a manufactured contradiction to
    # reach COMPLETE only through BEGIN_EXECUTION was a real, observed failure mode -- the engine
    # had no honest way to say "resolved through development alone, no leap needed."
    'COMPLETE',
}
EXECUTION_MOVES = {'PROPOSE_ACTION', 'ASSESS_PRACTICE', 'ASSESS_LEAP', 'REVISE_WORLD', 'COMPLETE'}


def validate_world(proposal, state):
    from dialectic_ai.core.runtime import DesignationRole

    move = proposal.move_type.value
    p = proposal.payload
    permitted = PLANNING_MOVES if state.phase == 'planning' else EXECUTION_MOVES
    if move not in permitted:
        raise ValueError(f'{move} is forbidden during {state.phase}; construct the roadmap before acting')
    goal = state.get_active_goal()
    if not goal:
        raise ValueError('No active goal')
    if move == 'ESTABLISH_CONTRADICTION':
        if not p.get('simplest_dev_ref_ids') or not p.get('opposite_dev_ref_ids'):
            raise ValueError('A contradiction requires committed development of BOTH processes')
    if move == 'BEGIN_EXECUTION':
        simplest = state.get_designation(p['simplest_id'])
        if not simplest or simplest.role != DesignationRole.SIMPLEST or simplest.goal_id != goal.id:
            raise ValueError('Roadmap requires a committed simplest process for this goal')
        if any(d.role == DesignationRole.CANDIDATE_SIMPLEST for d in state.get_all_designations()):
            raise ValueError('Assess pending simplest candidates before accepting a roadmap')
        resolutions = [state._resolution_relations.get(rid) for rid in p['resolution_ids']]
        if any(r is None for r in resolutions):
            raise ValueError('Roadmap resolution does not exist')
        for cid in p['contradiction_ids']:
            c = state.get_contradiction(cid)
            if not c or c.simplest_id != simplest.id:
                raise ValueError('Roadmap contradiction does not belong to its simplest process')
            if not any(r.contradiction_id == cid for r in resolutions):
                raise ValueError('Every roadmap contradiction requires a planned leap')
        if any(r.contradiction_id not in p['contradiction_ids'] for r in resolutions):
            raise ValueError('Resolution is outside the roadmap')
        reachable = {simplest.process_id}
        for cid in p['contradiction_ids']:
            c = state.get_contradiction(cid)
            reachable.add(state.get_designation(c.opposite_id).process_id)
            for rid in c.simplest_dev_ref_ids + c.opposite_dev_ref_ids:
                rel = state.get_development_relation(rid)
                reachable.update([rel.source_process_id, rel.emergent_process_id])
        reachable.update(r.resolution_process_id for r in resolutions)
        changed = True
        while changed:
            before = len(reachable)
            reachable.update(r.emergent_process_id for r in state.get_all_development_relations()
                             if r.source_process_id in reachable and state.is_committed(r.id))
            changed = before != len(reachable)
        for pid in p['execution_process_ids']:
            process = state.get_process(pid)
            if pid not in reachable or not process or process.status != 'active' or not state.is_committed(pid):
                raise ValueError('Execution route must reference committed processes in this roadmap')
        # A revision must actually change the selected graph, not merely relabel the same roadmap.
        if state.active_roadmap_id:
            old = state._roadmaps[state.active_roadmap_id]
            new_signature = (p['simplest_id'], p['contradiction_ids'], p['resolution_ids'], p['execution_process_ids'])
            old_signature = (old.simplest_id, old.contradiction_ids, old.resolution_ids, old.execution_process_ids)
            if new_signature == old_signature:
                raise ValueError('Revision must change the roadmap, not repeat the old one')
    if move == 'PROPOSE_ACTION':
        roadmap = state._roadmaps.get(state.active_roadmap_id)
        ref = p['origin_ref']
        if not roadmap or ref['type'] != 'Process' or ref['id'] not in roadmap.execution_process_ids:
            raise ValueError('Action must originate in a process on the accepted execution route')
        if any(a.status == 'pending' for a in state.get_all_actions()):
            raise ValueError('A previous action is still pending')
        if unassessed(state):
            raise ValueError('Assess the previous observation before the next action')
        if revision_needed(state):
            raise ValueError('Practice contradicted the roadmap; revise it before acting again')
    if move == 'REVISE_WORLD':
        for oid in p['observation_ids']:
            observation = state.get_observation(oid)
            if not observation or not any(pa.observation_id == oid for pa in state._practice_assessments.values()):
                raise ValueError('Revision requires existing assessed observations')
        if unassessed(state):
            raise ValueError('Assess observations before revising the roadmap')
        contradicted = {pa.observation_id for pa in state._practice_assessments.values()
                        if pa.expected_actual_relation == 'contradicted'
                        and state.get_action(pa.action_id).roadmap_id == state.active_roadmap_id}
        if not contradicted.issubset(set(p['observation_ids'])):
            raise ValueError('Revision must account for all contradicted observations of this roadmap')
    if move == 'ASSESS_LEAP':
        roadmap = state._roadmaps[state.active_roadmap_id]
        if p['resolution_id'] not in roadmap.resolution_ids:
            raise ValueError('Leap is outside the active roadmap')
        resolution = state._resolution_relations[p['resolution_id']]
        if resolution.confirmed_roadmap_id == roadmap.id:
            raise ValueError('Leap has already been assessed for this roadmap')
        if unassessed(state) or revision_needed(state):
            raise ValueError('Assess practice and revise contradicted expectations before confirming a leap')
        for oid in p['observation_ids']:
            observation = state.get_observation(oid)
            if not observation or not observation.success:
                raise ValueError('A realized leap needs successful observations')
            action = state.get_action(observation.action_id)
            assessments = [pa for pa in state._practice_assessments.values() if pa.observation_id == oid]
            if not assessments or assessments[-1].expected_actual_relation not in ('confirmed', 'partially_confirmed'):
                raise ValueError('Inconclusive practice cannot substantiate a realized leap')
            if action.roadmap_id != roadmap.id:
                raise ValueError('Leap evidence must come from the current roadmap execution')
    if move == 'COMPLETE':
        roadmap = state._roadmaps.get(state.active_roadmap_id)
        if roadmap is None:
            # "Clear" completion: reached directly from planning, with no roadmap ever accepted.
            # Legitimate when the goal turned out to need no genuine opposite/contradiction --
            # resolved through the simplest's own development alone. Nothing was executed, so
            # there is no practice to ground and no observations to cite; demanding either would
            # make this path impossible to use for exactly the goals it exists for.
            if p.get('evidence_observation_ids'):
                raise ValueError('No roadmap was ever executed for this goal -- a clear completion '
                                 'cannot cite evidence_observation_ids (there is no practice to ground)')
            return
        if revision_needed(state):
            raise ValueError('Cannot complete a roadmap contradicted by practice')
        if not all(state._resolution_relations[rid].confirmed_roadmap_id == roadmap.id for rid in roadmap.resolution_ids):
            raise ValueError('Every planned leap needs a practice-grounded assessment before completion')
        if not p.get('evidence_observation_ids'):
            raise ValueError('Completion requires observations from actual execution')
        for oid in p['evidence_observation_ids']:
            observation = state.get_observation(oid)
            if not observation or not observation.success:
                raise ValueError('Failed observations cannot support successful completion')
            if state.get_action(observation.action_id).roadmap_id != roadmap.id:
                raise ValueError('Completion needs evidence from the current roadmap')


def unassessed(state):
    assessed = {p.observation_id for p in state._practice_assessments.values()}
    return any(o.id not in assessed for o in state.get_all_observations())


def revision_needed(state):
    roadmap = state._roadmaps.get(state.active_roadmap_id)
    if not roadmap:
        return False
    return any(p.expected_actual_relation == 'contradicted'
               and state.get_action(p.action_id).roadmap_id == roadmap.id
               for p in state._practice_assessments.values())


def commit_world(proposal, state):
    p = proposal.payload
    move = proposal.move_type.value
    if move == 'BEGIN_EXECUTION':
        rid = str(uuid.uuid4())
        snapshot = {name: [asdict(v) for v in getattr(state, '_' + name).values()]
                    for name in ['processes', 'development_relations', 'designations', 'contradictions', 'resolution_relations']}
        state._roadmaps[rid] = Roadmap(rid, p['simplest_id'], list(p['contradiction_ids']),
                                      list(p['resolution_ids']), list(p['execution_process_ids']), copy.deepcopy(snapshot),
                                      list(state._revision_observation_ids), state._revision_reason)
        state.active_roadmap_id = rid
        state.phase = 'executing'
        return rid
    if move == 'REVISE_WORLD':
        state.phase = 'planning'
        state._revision_observation_ids = list(p['observation_ids'])
        state._revision_reason = p['reason']
        return state.active_roadmap_id
    if move == 'ASSESS_LEAP':
        resolution = state._resolution_relations[p['resolution_id']]
        resolution.confirmed_roadmap_id = state.active_roadmap_id
        resolution.evidence_observation_ids = list(p['observation_ids'])
        resolution.practice_explanation = p['explanation']
        return resolution.id
    raise ValueError('Not a world transition')
