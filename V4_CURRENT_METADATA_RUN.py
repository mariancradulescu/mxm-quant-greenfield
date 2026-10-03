"""Open this file in Pydroid and press RUN once. No edits or pip installs."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'vendor'))

if __name__=='__main__':
    try:
        if sys.version_info<(3,9):raise RuntimeError('Python3.9+ required')
        # Vendored IANA database gives Android the same timezone capability used
        # by the unchanged classifier, without requiring package installation.
        import zoneinfo
        zoneinfo.reset_tzpath([])
        from research_core_v4.pydroid_quote_metadata_launcher_v1 import main
        raise SystemExit(main(ROOT))
    except Exception:
        print('[BLOCAT ÎN SIGURANȚĂ] Pachetul nu a trecut verificarea locală. Nu modifica fișierele și nu trimite credențiale.')
        raise SystemExit(1) from None
