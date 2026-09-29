from pathlib import Path
import hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]; TARGET=ROOT/"dist"/"MXM_EPOCH46_OUTCOME_BLIND_M5_WAVE_01_CAPTURE_PACKAGE_V1.zip"
FILES=("EPOCH46_OUTCOME_BLIND_M5_CAPTURE_RUN.py","data/EPOCH46_OUTCOME_BLIND_M5_ACQUISITION_WAVE_01_PLAN_V1.json","research_v3/__init__.py","research_v3/epoch46_outcome_blind_m5_capture.py","research_v3/pydroid_epoch46_outcome_blind_m5_launcher.py","research_v3/capture_identity.py","competition/__init__.py","competition/frontier_data_capture.py","m6/__init__.py","m6/_ctrader_capture_base.py","m6/ctrader_capture.py","m6/ctrader_transport.py","m6/pydroid_oauth.py","m6/ctrader_proto/__init__.py","m6/ctrader_proto/OpenApiCommonModelMessages_pb2.py","m6/ctrader_proto/OpenApiCommonMessages_pb2.py","m6/ctrader_proto/OpenApiModelMessages_pb2.py","m6/ctrader_proto/OpenApiMessages_pb2.py","m6/ctrader_proto/LICENSE_SPOTWARE_OPENAPIPY.txt","tools/requirements-m6-capture.txt")
def build():
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(TARGET,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in FILES:
            p=ROOT/rel
            if not p.is_file(): raise FileNotFoundError(rel)
            i=zipfile.ZipInfo(rel,(1980,1,1,0,0,0)); i.compress_type=zipfile.ZIP_DEFLATED; i.external_attr=0o644<<16; z.writestr(i,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    print(TARGET); print(hashlib.sha256(TARGET.read_bytes()).hexdigest())
if __name__=="__main__": build()
