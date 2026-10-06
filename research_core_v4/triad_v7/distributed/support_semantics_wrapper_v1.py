"""Distributed execution compatibility layer for the frozen V7 worker.
It converts only prospectively enumerated NumericalUnavailable support-loss
reasons into atomic unsupported configuration rows. The frozen worker, DGP,
projection kernel, RNG, inference geometry, seeds and trial counts are unchanged.
"""
import numpy as np
import stochastic_worker_v1 as w

EXPECTED_SUPPORT_UNAVAILABLE = frozenset({
    "CANDIDATE_FAIL_CLOSED",
    "DIMENSION_OR_FINITE_REJECTION",
    "SCALE_REJECTION",
    "NONFINITE_SINGULAR_VALUES",
    "NUMERICAL_SUPPORT_AMBIGUOUS_UNTESTED_NOT_NULL",
    "INDEPENDENT_ORTHOGONALITY_REJECTION",
    "RESIDUAL_RELIABILITY_REJECTION",
    "FIXED_TIMESTAMP_OR_SYNTHETIC_FULL_FAMILY_SUPPORT_FAILURE",
    "DEGENERATE_STUDENTIZATION",
    "NEGATIVE_BOOTSTRAP_VARIANCE",
})

def _dummy_inference():
    z=np.zeros(12,dtype=bool)
    return {"reject":z.copy(),"lead":z.copy(),"support":False}

def _configs(manifest,mode):
    return manifest["partial_nulls"] if mode=="null" else manifest["power_cells"]

def _reason(exc):
    reason=str(exc)
    if reason not in EXPECTED_SUPPORT_UNAVAILABLE:
        raise exc
    return reason

def trial(manifest,g,project,mode,case_id,index,verify_supported_path=False):
    """Call the frozen worker trial; convert only frozen support loss atomically."""
    base_scores=w.scores
    base_infer=w.infer
    reasons=[]
    def scores_proxy(*args,**kwargs):
        reasons.append(None)
        try:
            return base_scores(*args,**kwargs)
        except w.NumericalUnavailable as exc:
            reason=_reason(exc)
            reasons[-1]=reason
            return {"__mxm_support_unavailable__":reason}
    def infer_proxy(*args,**kwargs):
        o=args[1] if len(args)>1 else kwargs["o"]
        if isinstance(o,dict) and "__mxm_support_unavailable__" in o:
            return _dummy_inference()
        try:
            return base_infer(*args,**kwargs)
        except w.NumericalUnavailable as exc:
            reason=_reason(exc)
            assert reasons and reasons[-1] is None
            reasons[-1]=reason
            return _dummy_inference()
    w.scores=scores_proxy
    w.infer=infer_proxy
    try:
        rows=w.trial(manifest,g,project,mode,case_id,index)
    finally:
        w.scores=base_scores
        w.infer=base_infer
    configs=_configs(manifest,mode)
    assert len(rows)==len(configs)==len(reasons)
    converted=[]
    by_reason={}
    supported=0
    for row,config,reason in zip(rows,configs,reasons):
        assert row["cell_id"]==config["id"]
        row=dict(row)
        if reason is None:
            supported+=1
        else:
            assert row["false_significance"] is False
            assert row["false_lead"] is False
            assert row["any_nonnull_lead"] is False
            assert row["all_nonnull_leads"] is False
            assert all(int(v)==0 for v in row["per_leaf_lead"])
            row["support"]=False
            by_reason[reason]=by_reason.get(reason,0)+1
        converted.append(row)
    meta={
        "supported_configurations":supported,
        "unsupported_configurations":len(configs)-supported,
        "support_unavailable_by_reason":dict(sorted(by_reason.items())),
        "support_unavailable_reasons_by_configuration":reasons,
        "hard_failures":0,
        "atomic_no_partial_salvage":True,
    }
    if verify_supported_path:
        meta["supported_path_parity"]=_supported_path_parity(
            manifest,g,project,mode,case_id,index
        )
    return converted,meta

def _supported_path_parity(manifest,g,project,mode,case_id,index):
    """Engineering-only isolated-config proof; never used by certification."""
    configs=_configs(manifest,mode)
    key="partial_nulls" if mode=="null" else "power_cells"
    bit_identical=0
    expected_unsupported=0
    details=[]
    for config in configs:
        one=dict(manifest)
        one[key]=[config]
        try:
            original=w.trial(one,g,project,mode,case_id,index)
        except w.NumericalUnavailable as exc:
            reason=_reason(exc)
            corrected,meta=trial(one,g,project,mode,case_id,index,False)
            assert len(corrected)==1 and corrected[0]["support"] is False
            assert meta["unsupported_configurations"]==1
            expected_unsupported+=1
            details.append({"cell_id":config["id"],"original":"EXPECTED_SUPPORT_UNAVAILABLE","reason":reason})
        else:
            corrected,meta=trial(one,g,project,mode,case_id,index,False)
            assert meta["unsupported_configurations"]==0
            assert w.canonical(original)==w.canonical(corrected)
            bit_identical+=1
            details.append({"cell_id":config["id"],"original":"SUPPORTED","bit_identical":True})
    assert bit_identical+expected_unsupported==len(configs)
    return {
        "tested_configurations":len(configs),
        "supported_bit_identical":bit_identical,
        "expected_unsupported_preserved":expected_unsupported,
        "all_accounted":True,
        "details":details,
    }
