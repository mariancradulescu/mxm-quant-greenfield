"""Candidate-independent stage 1. No research modules or candidate definitions imported."""
import builtins
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path

S = 'research_core_v4/state/'
BASE = '0b76201cc959494487f6f824d4848d1179273aa6'
CERT = S+'STRICT_PREOUTCOME_V2_SHARED_OWN_INFORMATION_BASELINE_CERTIFICATE_V1.json'
INPUT = S+'STRICT_PREOUTCOME_RESELECTION_V2_INPUTS_V1.json'
PROTOCOL = S+'STRICT_PREOUTCOME_V2_SHARED_BASELINE_SPECIFICATION_PROTOCOL_V1.json'
SPEC = S+'STRICT_PREOUTCOME_V2_SHARED_OWN_INFORMATION_BASELINE_EXACT_SPECIFICATION_V1.json'
AUTH = S+'STRICT_PREOUTCOME_V2_SHARED_BASELINE_SPECIFICATION_AUTHORITY_V1.json'
ALLOWED = {CERT, INPUT}
HASHES = {CERT:'3a605e7ae34658c2c2010de8e6ed3ccee0b2478f8f68116fd819ae5d1736fe31', INPUT:'fa01029ed0ac8bee799594a4d08cc053ce55aaedce3b3c2a4375435a3048234b'}
NEXT = 'STRICT_PREOUTCOME_V2_SHARED_BASELINE_INFORMATION_GRANULARITY_UNRESOLVED_PENDING_INDEPENDENT_GOVERNANCE_BEFORE_CANDIDATE_REBUILD'
TEXT = 'Own last completed M5 and hourly price location, range and broker activity, with causal clock controls; incremental predictor excluded from baseline'
COMPONENTS = ['LAST_COMPLETED_M5_PROJECTION','HOURLY_PRICE_LOCATION','RANGE_PROJECTION','BROKER_ACTIVITY_PROJECTION','CAUSAL_CLOCK_CONTROLS','AGGREGATION_CLOCK_DOMAIN']

def require(condition, code):
    if not condition: raise ValueError(code)

def canonical(obj): return (json.dumps(obj, indent=2, sort_keys=True)+'\n').encode()
def digest(data): return hashlib.sha256(data).hexdigest()

@contextmanager
def read_compartment(root, seen):
    root = Path(root).resolve()
    old_b, old_i, old_o = builtins.open, io.open, os.open
    def check(file, writing=False):
        require(not isinstance(file, int), 'FILE_DESCRIPTOR_NOT_ALLOWED')
        resolved = Path(file).resolve()
        try: rel = resolved.relative_to(root).as_posix()
        except ValueError: raise ValueError('READ_OUTSIDE_COMPARTMENT')
        require(not writing and rel in ALLOWED, 'READ_NOT_ALLOWED:'+rel)
        seen.append(rel)
    def guarded_b(file, mode='r', *args, **kwargs):
        check(file, any(x in mode for x in 'wax+')); return old_b(file, mode, *args, **kwargs)
    def guarded_i(file, mode='r', *args, **kwargs):
        check(file, any(x in mode for x in 'wax+')); return old_i(file, mode, *args, **kwargs)
    def guarded_o(file, flags, *args, **kwargs):
        check(file, bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))); return old_o(file, flags, *args, **kwargs)
    builtins.open, io.open, os.open = guarded_b, guarded_i, guarded_o
    try: yield
    finally: builtins.open, io.open, os.open = old_b, old_i, old_o

def project(certificate, neutral):
    # Never dereference source_definitions, identities, comparative or execution fields.
    m = neutral['modalities']['canonical_m5']
    return {'baseline_text':certificate['frozen_baseline_text'],
            'available_fields':m['fields'], 'resolution_minutes':m['resolution_minutes'],
            'availability':m['availability'],
            'activity_units':certificate['UNITS']['broker_activity'],
            'activity_projection':certificate['component_formalization']['broker_activity_projection']['map']}

def protocol():
    return {'schema':'mxm.v4.strict-preoutcome-v2.shared-baseline-specification-protocol.v1',
        'status':'FROZEN_BEFORE_STAGE_1_OUTPUT', 'source_head':BASE,
        'builder_read_allowlist':sorted(ALLOWED), 'candidate_visibility':False,
        'baseline_text':TEXT,
        'invariants':['fidelity','causal preentry completed observations','deterministic map',
                      'explicit domain and units','no imputation','no response','candidate invariance'],
        'resolution_test':'An exact map requires a unique information sigma-algebra; invertible coordinate encodings may be equivalent. Information-losing projections are not equivalent.',
        'ambiguity_test':'Construct two legal symbolic causal inputs and two prose-compatible activity projections differing in retained information. This is a countermodel of uniqueness, not a choice of baseline.',
        'countermodel_domain':'An abstract fully observed completed hour containing 12 M5 count observations; common nonactivity coordinates Z held fixed; all availability timestamps strictly before entry.',
        'stop_rule':'If competing information-content projections satisfy all fixed constraints and no permitted premise orders them, stop at the stage 1 nondefensible free design choice. Do not rebuild certificates or reapply the functional.',
        'forbidden_resolution':['use candidates','use outcomes','choose minimum dimensionality without authorization','assume maximal raw-path retention'],
        'stage_order':['freeze this protocol','derive candidate-blind nonuniqueness result','freeze specification result','bind authority','stop if unresolved'],
        'market_rows_required':0, 'empirical_measurement_authorized':False}

def total_projection(v):
    require(len(v)==12 and all(type(x) is int and x>=0 for x in v), 'COUNT_DOMAIN')
    return (v[-1], sum(v))

def vector_projection(v):
    total_projection(v)
    return (v[-1], tuple(v))

def derive(p):
    require(p['baseline_text']==TEXT, 'SEMANTICS_DRIFT')
    require(p['resolution_minutes']==5 and 'tick_volume' in p['available_fields'], 'SCHEMA_DRIFT')
    require(p['activity_projection'] is None, 'PRIOR_MAP_NOT_UNRESOLVED')
    left=[1,3]+[2]*10; right=[3,1]+[2]*10
    require(total_projection(left)==total_projection(right), 'WITNESS_COARSE')
    require(vector_projection(left)!=vector_projection(right), 'WITNESS_FINE')
    return {'schema':'mxm.v4.strict-preoutcome-v2.shared-baseline-exact-specification.v1',
        'status':'BLOCKED_INFORMATION_CONTENT_GOVERNANCE_CHOICE_PROVED',
        'source_head':BASE, 'frozen_baseline_text':TEXT, 'exact_baseline_map_B_t':None,
        'first_blocking_component':'BROKER_ACTIVITY_PROJECTION',
        'components':{k:{'exact_map':None,'status':'UNRESOLVED_NOT_ASSIGNED'} for k in COMPONENTS},
        'proof':{'domain':'v in nonnegative integer counts^12, completed and authentic availability before entry; common nonactivity coordinates Z fixed. Abstract legal states, not market observations.',
            'coarse_map':'B_total=(Z,v_12,sum(v_j,j=1..12))',
            'fine_map':'B_vector=(Z,v_12,(v_1,...,v_12))',
            'left_counts':left,'right_counts':right,
            'same_total_projection':list(total_projection(left)),
            'different_fine_projection':True,
            'sigma_relation':'sigma(B_total) is a strict subset of sigma(B_vector) on this domain',
            'containment_proof':'Sum and last count are deterministic functions of the vector.',
            'strictness_proof':'The two states have identical total and last count but distinct first coordinate; {v_1=1} is observable under B_vector and not under B_total.',
            'fidelity':'Both are own completed M5/hour broker activity summaries in reported count units. Frozen certificate explicitly leaves last count, hourly aggregate and within-hour vector unchosen.',
            'availability_map':'Every abstract component available at or before completed-hour close, strictly before entry; no forming bars or future response.',
            'degenerate_cases':'Zero counts allowed. Missing counts invalidate the window; neither map imputes. This witness is fully observed.',
            'not_a_baseline_assignment':True},
        'minimum_unstated_freedom_analysis':'The rule minimizes unsupported choices, but supplies neither a minimum-dimension sufficiency criterion nor a maximal-retention criterion. It cannot order distinct information contents. Unit rescaling cannot remove strict sigma containment.',
        'exact_governance_choice_required':'Prospectively specify which temporal activity information belongs in the shared own-information baseline, with a candidate-independent sufficiency justification; total versus vector is a material information-set decision.',
        'why_data_cannot_resolve_semantics':'More rows can estimate properties of either map but cannot establish which information set the frozen prose intended. Choosing by empirical fit would violate the firewall.',
        'boundary_kind':'NONDEFENSIBLE_FREE_DESIGN_CHOICE_STAGE_1_STOP',
        'empirical_or_external_blocker_reached':False,
        'stage_2_executed':False,'stage_3_executed':False,'complete_design_selected':False,
        'remaining_possible_contenders':11,'candidate_definitions_read':False,
        'additional_information_scope':'A shared prospective governance specification only; no candidate comparisons, market rows, broker or external data.',
        'market_rows_used':0,'power_trials':0,'duration_selected':False,'response_opened':False,
        'next_action':NEXT}

def build_root(root, seen):
    with read_compartment(root, seen):
        docs={}
        for path in [CERT,INPUT]:
            data=(Path(root)/path).read_bytes(); require(digest(data)==HASHES[path], 'INPUT_HASH_DRIFT:'+path); docs[path]=json.loads(data)
        projected=project(docs[CERT],docs[INPUT]); del docs
        return derive(projected)
