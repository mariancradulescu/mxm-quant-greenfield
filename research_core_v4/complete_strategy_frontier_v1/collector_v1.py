"""Bounded bilateral history and strictly necessary M5 warmup; existing native auth."""
from research_core_v4.dynamic_exit_diagnostic_v1.collector_v3 import Collector as Existing
class Collector(Existing):
 def __init__(self):
  super().__init__();self.caps.update(BID_ASK=900,M5=12,H1=0)
