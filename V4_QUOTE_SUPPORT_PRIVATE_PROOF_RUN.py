"""One offline proof run from the existing bound probe folder."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'vendor'))
if __name__=='__main__':
    from V4_QUOTE_SUPPORT_PRIVATE_PROOF_VERIFY import main
    raise SystemExit(main(ROOT))
