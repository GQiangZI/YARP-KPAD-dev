#!/usr/bin/env python3
"""Repack only a verified v1.0 recovery fragment; never accesses a device."""
import argparse, hashlib, json, stat, struct
from pathlib import Path
import lz4.block

BASE_SHA = 'e9ede605818609f9cbb7725feef7bbfc0490b15200f2d88d85ee87051af3714a'
AWK_SHA = '2550bd68e2ca01c4938023e096b2d96686e4d03fad2e97a1566a41eda2ac02fb'
def sha(b): return hashlib.sha256(b).hexdigest()
def align(n, size=4096): return (n + size-1) // size * size
def decompress(b):
    assert b[:4] == bytes.fromhex('02214c18')
    out=bytearray(); p=4
    while p < len(b):
        n=struct.unpack_from('<I',b,p)[0]; p+=4
        if not n: break
        assert p+n <= len(b)
        out += lz4.block.decompress(b[p:p+n], uncompressed_size=8*1024*1024); p+=n
    assert not any(b[p:])
    return bytes(out)
def compress(b):
    out=bytearray.fromhex('02214c18')
    for p in range(0,len(b),8*1024*1024):
        c=lz4.block.compress(b[p:p+8*1024*1024],mode='high_compression',compression=12,store_size=False)
        out+=struct.pack('<I',len(c))+c
    return bytes(out)
def read_cpio(data):
    p=0; rows=[]
    while True:
        assert data[p:p+6] == b'070701'
        f=[int(data[p+6+i*8:p+14+i*8],16) for i in range(13)]
        q=p+110; name=data[q:q+f[11]-1].decode(); q=align(q+f[11],4)
        body=data[q:q+f[6]];p=align(q+f[6],4)
        assert len(body)==f[6] and not f[12]
        if name=='TRAILER!!!': break
        rows.append((name,f,body))
    assert not any(data[p:])
    return rows
def write_cpio(rows):
    out=bytearray()
    for name,fields,body in rows+[('TRAILER!!!',[0]*13,b'')]:
        f=list(fields);f[6]=len(body);f[11]=len(name.encode())+1;f[12]=0
        out += b'070701'+''.join('%08x'%v for v in f).encode()+name.encode()+b'\0'
        out += b'\0'*(align(len(out),4)-len(out));out+=body
        out += b'\0'*(align(len(out),4)-len(out))
    return bytes(out)
def layout(data):
    assert data[:8]==b'VNDRBOOT' and struct.unpack_from('<I',data,8)[0]==4
    page=struct.unpack_from('<I',data,12)[0]; assert page==4096
    size=struct.unpack_from('<I',data,24)[0]
    hs,ds=struct.unpack_from('<II',data,2096)
    ts,count,es,bs=struct.unpack_from('<IIII',data,2112)
    assert hs==2128 and count==2 and es==108 and ts==count*es and bs==0
    do=page+align(size);to=do+align(ds)
    table=data[to:to+ts]
    frag=[]
    for i in range(count):
        n,off,kind=struct.unpack_from('<III',table,i*es)
        assert kind==i+1
        frag.append(data[page+off:page+off+n])
    return frag,data[do:do+align(ds)],bytearray(table)

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--runtime',type=Path,required=True);p.add_argument('--awk',type=Path,required=True)
    args=p.parse_args();base=args.base.read_bytes();assert sha(base)==BASE_SHA
    frag,dtb,table=layout(base);rows=read_cpio(decompress(frag[1]));original={n:(f,b) for n,f,b in rows}
    changes={};here=Path(__file__).resolve().parent
    runtime=args.runtime.read_bytes()
    assert runtime[:6]==b'\x7fELF\x02\x01' and struct.unpack_from('<H',runtime,18)[0]==183
    phoff=struct.unpack_from('<Q',runtime,32)[0]
    phentsize,phnum=struct.unpack_from('<HH',runtime,54)
    assert phentsize==56 and all(struct.unpack_from('<I',runtime,phoff+i*phentsize)[0]!=3 for i in range(phnum)), 'runtime must be static (no PT_INTERP)'
    awk=args.awk.read_bytes();assert sha(awk)==AWK_SHA, 'unverified awk build'
    changes['system/bin/turner-runtime']=(0o100755,runtime)
    changes['system/bin/turner-runtime-stage.sh']=(0o100755,(here/'turner-runtime-stage.sh').read_bytes())
    changes['system/bin/awk']=(0o100755,awk)
    rcname='system/etc/init/hybrid-services.rc';rc=original[rcname][1].decode()
    targets=['/vendor/bin/tee-supplicant','/system/bin/turner-tee-sup.sh keymint','/system/bin/turner-tee-sup.sh gatekeeper','/system/bin/turner-touch-sup.sh','/system/bin/turner-ks2-sup.sh','/system/bin/turner-vibrator-sup.sh']
    for command in targets:
        old=' '+command+'\n';assert rc.count(old)==1,command
        rc=rc.replace(old,' /system/bin/turner-runtime enter '+command+'\n')
    assert rc.count('capabilities DAC_OVERRIDE SYS_RAWIO')==1
    rc=rc.replace('capabilities DAC_OVERRIDE SYS_RAWIO','capabilities DAC_OVERRIDE SYS_RAWIO SYS_ADMIN SYS_CHROOT SYS_PTRACE')
    rc+='\n# RAM-backed namespace keeper. Must start after staging, before HALs.\nservice turner-runtime-keeper /system/bin/turner-runtime hold\n    class hal\n    user root\n    group root system\n    seclabel u:r:recovery:s0\n    disabled\n'
    changes[rcname]=(original[rcname][0][1],rc.encode())
    name='system/bin/turner-setup.sh';body=original[name][1].decode()
    marker='log_msg "step:persist+metadata ready"\n';assert body.count(marker)==1
    inject='''
# Snapshot the exact installed ROM before launching any dependent HAL.
if ! /system/bin/turner-runtime-stage.sh; then
    setprop vendor.turner.setup.failed runtime-snapshot
    log_msg "runtime snapshot failed; refusing dependent HAL starts"
    exit 1
fi
setprop ctl.start turner-runtime-keeper
_ri=0
while [ "$(getprop vendor.turner.runtime.namespace)" != ready ] && [ $_ri -lt 50 ]; do
    sleep 0.1; _ri=$((_ri + 1))
done
if [ "$(getprop vendor.turner.runtime.namespace)" != ready ]; then
    setprop vendor.turner.setup.failed runtime-namespace
    exit 1
fi
'''
    body=body.replace(marker,marker+inject)
    changes[name]=(original[name][0][1],body.encode())
    patched=[]
    for name,f,b in rows:
        if name in changes:
            mode,b=changes[name];f=list(f);f[1]=mode
        patched.append((name,f,b))
    for name,(mode,b) in changes.items():
        if name not in original:
            f=[0]*13;f[0]=max(r[1][0] for r in patched)+1;f[1]=mode;f[4]=1;patched.append((name,f,b))
    packed=compress(write_cpio(patched));assert read_cpio(decompress(packed))==read_cpio(write_cpio(patched))
    header=bytearray(base[:4096]);struct.pack_into('<I',header,24,len(frag[0])+len(packed))
    for i,c in enumerate([frag[0],packed]):struct.pack_into('<II',table,i*108,len(c),0 if i==0 else len(frag[0]))
    raw=bytes(header)+frag[0]+packed;raw+=b'\0'*(align(len(raw))-len(raw));raw+=dtb+table
    original_size,vo,vs=struct.unpack_from('>QQQ',base,len(base)-52)
    vm=bytearray(base[vo:vo+vs]);assert vs==512 and vm[:4]==b'AVB0' and struct.unpack_from('>I',vm,28)[0]==0
    do,ds=struct.unpack_from('>QQ',vm,96);assert (do,ds)==(0,208)
    at=256; salt=bytes(vm[at+143:at+175]);struct.pack_into('>Q',vm,at+16,len(raw));vm[at+175:at+207]=hashlib.sha256(salt+raw).digest()
    vo2=align(len(raw));assert vo2+512+64 <= len(base)
    result=bytearray(len(base));result[:len(raw)]=raw;result[vo2:vo2+512]=vm
    result[-64:]=b'AVBf'+struct.pack('>IIQQQ',1,0,len(raw),vo2,512)+b'\0'*28
    ff,dd,tt=layout(result);assert ff[0]==frag[0] and dd==dtb
    check={n:(f,b) for n,f,b in read_cpio(decompress(ff[1]))}
    for n,(f,b) in original.items():
        if n not in changes:assert check[n]==(f,b),n
    assert set(check)==set(original)|set(changes)
    args.out.write_bytes(result)
    manifest={'base_sha256':sha(base),'sha256':sha(result),'size':len(result),'runtime_sha256':sha(runtime),'awk_sha256':sha(awk),'f0_unchanged':True,'dtb_unchanged':True,'changed_or_added':sorted(changes),'free_bytes':len(base)-vo2-512-64}
    args.out.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
