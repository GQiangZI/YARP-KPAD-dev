#!/usr/bin/env python3
"""Exact v1.0 MTK library patch. Refuse every other input build."""
import hashlib,json,struct,sys
from pathlib import Path
BASE='71aee2540c4995920fe520cdb0cd4c3b4d694462686638eaf6a1c6884e3a1939'
def patch(data):
    assert hashlib.sha256(data).hexdigest()==BASE
    out=bytearray(data)
    # Init: do not skip the existing property-gated fastest same-resolution
    # mode selection just because MTK needs the standard legacy KMS path.
    # Init: allow twrp.drm.direct_scanout=false to allocate a cached RAM
    # drawing surface, instead of forcing drawing directly into DRM memory.
    sites={0x1c538:0x37000f48,0x1c7a4:0x54ffe460}
    for off,old in sites.items():
        assert struct.unpack_from('<I',data,off)[0]==old
        struct.pack_into('<I',out,off,0xd503201f)
    assert len(out)==len(data)
    assert all(i in range(0x1c538,0x1c53c) or i in range(0x1c7a4,0x1c7a8)
               for i,(a,b) in enumerate(zip(data,out)) if a!=b)
    return bytes(out)
if __name__=='__main__':
    a,b=map(Path,sys.argv[1:]);out=patch(a.read_bytes());b.write_bytes(out)
    print(json.dumps({'sha256':hashlib.sha256(out).hexdigest(),'size':len(out)}))
