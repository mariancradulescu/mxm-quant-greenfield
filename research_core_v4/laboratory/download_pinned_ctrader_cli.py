"""Bounded parallel ranges of the SAME official, checksum-pinned vendor archive.

No retries, alternate provider, extraction or execution. Each response must prove
its exact byte range; only the complete pre-existing length/hash may be published.
"""
import concurrent.futures
import hashlib
import os
import sys
import time
import urllib.request
from pathlib import Path
from .ctrader_cli_metadata import TARBALL_SHA, need
URL='https://getctrader.spotware.com/cli/homebrew/ctrader-cli-5.9.0-linux-x64.tar.gz'
SIZE=103434349
PARTS=32
SECONDS=420

def read_part(response,start,end,deadline):
    length=end-start+1
    need(response.status==206 and response.headers.get('Content-Range')==f'bytes {start}-{end}/{SIZE}',
         'VENDOR_EXACT_RANGE_RESPONSE')
    need(response.headers.get('Content-Encoding','identity')=='identity' and
         response.headers.get('Content-Length')==str(length),'VENDOR_RANGE_LENGTH_ENCODING')
    chunks=[];received=0
    while received<length:
        need(time.monotonic()<deadline,'VENDOR_RANGE_DEADLINE')
        chunk=response.read(min(65536,length-received))
        need(chunk and len(chunk)<=length-received,'VENDOR_RANGE_TRUNCATED_OR_OVERSIZED')
        chunks.append(chunk);received+=len(chunk)
    need(time.monotonic()<deadline and not response.read(1),'VENDOR_RANGE_TRAILING_BYTES')
    return b''.join(chunks)

def fetch_part(start,end,deadline):
    need(time.monotonic()<deadline,'VENDOR_RANGE_DEADLINE')
    request=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
    with urllib.request.urlopen(request,timeout=min(20,max(.01,deadline-time.monotonic()))) as response:
        need(response.url==URL,'VENDOR_OFFICIAL_RESOURCE_ONLY')
        return read_part(response,start,end,deadline)

def publish(destination,parts,expected_size=SIZE,expected_sha=TARBALL_SHA):
    destination=Path(destination);temporary=destination.with_name(destination.name+'.partial')
    need(not destination.exists() and not destination.is_symlink() and not temporary.exists() and
         not temporary.is_symlink(),'VENDOR_NO_OUTPUT_OVERWRITE')
    digest=hashlib.sha256();count=0
    try:
        with temporary.open('xb') as out:
            for raw in parts:
                count+=len(raw);need(count<=expected_size,'VENDOR_ARCHIVE_SIZE_BOUND')
                digest.update(raw);out.write(raw)
            need(count==expected_size and digest.hexdigest()==expected_sha,'VENDOR_TARBALL_PIN')
            out.flush();os.fsync(out.fileno())
        os.replace(temporary,destination)
    finally:
        if temporary.exists():temporary.unlink()

def download(destination):
    deadline=time.monotonic()+SECONDS
    ranges=[(SIZE*i//PARTS,SIZE*(i+1)//PARTS-1) for i in range(PARTS)]
    # Finite32 requests, total exactly103434349 payload bytes on success.
    # A server ignoring Range is rejected BEFORE any body read.
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARTS) as pool:
        futures=[pool.submit(fetch_part,a,b,deadline) for a,b in ranges]
        publish(destination,(f.result(timeout=max(.01,deadline-time.monotonic())) for f in futures))
    print('MXM_SAME_OFFICIAL_VENDOR_ARCHIVE_EXACT_LENGTH_AND_SHA256_VERIFIED')
if __name__=='__main__':
    need(len(sys.argv)==2,'VENDOR_DOWNLOAD_ARGUMENTS');download(sys.argv[1])
