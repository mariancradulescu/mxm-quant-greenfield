"""One production entrypoint: signature -> gate -> reader -> V1 score -> report."""
import argparse
import os
import resource
import time
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from . import gate

def execute(envelope_path):
    permit=gate.authorize(envelope_path)
    from .reader import read_production
    from research_core_v4.exploratory_dev_v1.worker import evaluate
    caches,ids=read_production(permit);permit.check();report=evaluate(caches,ids);permit.check()
    report.update({'authorization_payload_sha256':permit.arm_digest,'execution_head':permit.payload['execution_head'],
      'CPU_seconds':time.process_time()-permit.started,'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      'parsed_corpus_passes':1,'broker_requests':0,'protected_forward_rows':0,'orders':0,'operational_version':2})
    gate.durable_json(permit.payload['output_file'],report)
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--independent-signed-arm',required=True)
    execute(parser.parse_args().independent_signed_arm)

if __name__=='__main__':main()
