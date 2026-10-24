"""Extract only the checksum-pinned official Spotware CLI release. No execution."""
import hashlib,os,sys,tarfile
from pathlib import Path
from .ctrader_cli_metadata import TARBALL_SHA,need

def extract(archive,destination):
    archive=Path(archive);destination=Path(destination)
    need(archive.stat().st_size==103434349 and hashlib.sha256(archive.read_bytes()).hexdigest()==TARBALL_SHA,'VENDOR_TARBALL_PIN')
    destination.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive,'r:gz') as t:
        members=t.getmembers()
        need(len(members)<10000 and sum(x.size for x in members)<1073741824,'VENDOR_EXTRACTION_BOUNDS')
        t.extractall(destination,filter='data')
    # Mirror the pinned vendor Homebrew formula: Windows tar lacks executable bits.
    for path in destination.rglob('*'):
        if path.is_file() and ('.' not in path.name or path.name=='algohost.netcore'):path.chmod(0o755)
    need((destination/'ctrader-cli').is_file(),'NATIVE_EXECUTABLE_LOCATION')
    print('MXM_PINNED_VENDOR_CLI_EXTRACTED_NO_EXECUTION')
if __name__=='__main__':need(len(sys.argv)==3,'INSTALL_ARGUMENTS');extract(*sys.argv[1:])
