#!/usr/bin/env python3
"""Build the NFS MW Vita performance patch from the exact ORIGINAL VPK.
Python 3.9+, standard library. Input is never overwritten. No compiler required.
All changes are checksum/byte checked and loader relocation records updated.
"""
from pathlib import Path
import argparse, hashlib, io, json, struct, sys, zipfile
import self_format as fmt
ROOT=Path(__file__).resolve().parent
ORIGINAL_SHA='ffae9cef5b2819570ae95ca4fc5c9663879f8de0b0ef14d2f1a22925928ad24b'
PROFILE='combined'
PAYLOAD_ROOT=ROOT/'builds'/PROFILE/'payload'
PAYLOAD_SHA=None
GUARD_SITE=0x812a03f0
GUARD=bytes.fromhex('30b90923c8f800306ff00000bde8f081037905467047')
need=fmt.require
sha=fmt.sha256

def branch(site,target,tail=False):
    data=bytearray(fmt.encode_bl(site,target&~1))
    if tail:struct.pack_into('<H',data,2,struct.unpack_from('<H',data,2)[0]&~0x4000)
    need(fmt.decode_bl(site,data)==(target&~1),'Branch target roundtrip failed')
    return bytes(data)

def patch_executable(original):
    need(sha(original)==ORIGINAL_SHA,'Wrong executable. Use the original nfsmw.vpk, NOT a previously patched version.')
    payload=(PAYLOAD_ROOT/'payload.bin').read_bytes()
    meta=json.loads((PAYLOAD_ROOT/'payload.json').read_text())
    hooks=json.loads((PAYLOAD_ROOT/'hooks.json').read_text())
    need(sha(payload)==PAYLOAD_SHA==meta['text_sha256'],'Payload checksum mismatch')
    header,elf,ph,segs=fmt.parse_self(original)
    original_segs=segs.copy();original_ph=[p.copy() for p in ph]
    po=meta['text_vaddr']-fmt.CODE_BASE
    need(len(segs[0])<=po and po+len(payload)<fmt.DATA_BASE-fmt.CODE_BASE,'Payload overlap')
    need(meta['entry_vaddr']==meta['symbols']['cpu_balance_dispatch']==meta['text_vaddr']+1,'Bad entry')
    need(meta['bss_vaddr']>=fmt.DATA_BASE+ph[1][5],'BSS overlap')
    code=bytearray(segs[0]);code+=bytes(po-len(code));code+=payload
    while len(code)%4:code.append(0)
    reloc=bytearray(segs[2]);records={}
    need(len(reloc)%12==0,'Bad relocation table')
    for off in range(0,len(reloc),12):
        flags,ad,site=struct.unpack_from('<3I',reloc,off)
        need(flags&15==0,'Unexpected relocation form')
        if (flags>>16)&15==0:
            need(site not in records,'Duplicate relocation site')
            records[site]=(off,flags,ad)
    changed=[]
    for h in hooks:
        va=h['site'];site=va-fmt.CODE_BASE;target=meta['symbols'][h['new_symbol']]
        need(meta['text_vaddr']<=target<meta['text_vaddr']+len(payload),'Replacement outside payload')
        need(target&1==1,'Replacement must be Thumb')
        old=bytes.fromhex(h['original_bytes'])
        need(code[site:site+4]==old,'Original opcode mismatch at '+hex(va))
        if 'argument_prefix' in h:
            need(code[site-4:site]==bytes.fromhex(h['argument_prefix']),'Binding target MOVW mismatch')
        if h['original_branch'] in ('cmp','cmp_jump'):
            need(site not in records,'Inner hook unexpectedly relocated')
            reloc+=struct.pack('<3I',0xa00,target-4-fmt.CODE_BASE,site)
        else:
            off,flags,ad=records[site]
            need(flags==h['original_reloc_flags']==0xa00 and ad==h['original_reloc_addend'],'Loader relocation mismatch')
            struct.pack_into('<I',reloc,off+4,target-4-fmt.CODE_BASE)
        new=branch(va,target,h['original_branch'] in ('bw','cmp_jump'))
        code[site:site+4]=new
        changed.append(dict(h,new_bytes=new.hex(),new_target=target))
    # Preserve exactly the v2.1 null file-handle error guard.
    guard_addr=fmt.CODE_BASE+len(code);site=GUARD_SITE-fmt.CODE_BASE
    need(code[site:site+4]==bytes.fromhex('03790546'),'File guard site mismatch')
    need(all(not site<=s<site+4 for s in records),'Guard overlaps relocation')
    need((ROOT/'guard/fd_seek_guard.bin').read_bytes()==GUARD,'File guard changed')
    code[site:site+4]=branch(GUARD_SITE,guard_addr+1);code+=GUARD
    while len(code)%4:code.append(0)
    need(fmt.CODE_BASE+len(code)<=fmt.DATA_BASE,'Code overlaps data')
    ph[0][5]=len(code);ph[1][5]=meta['bss_vaddr']+meta['bss_size']-fmt.DATA_BASE
    for r in meta['absolute_relocations']:
        need(r['type'] in (2,47,48) and r['symbol_segment'] in (0,1),'Bad absolute fixup')
        need(po<=r['instruction_offset']<po+len(payload)-3,'Payload fixup out of bounds')
        need(0<=r['addend']<ph[r['symbol_segment']][5],'Payload target out of bounds')
        flags=r['symbol_segment']<<4 | r['type']<<8
        reloc+=struct.pack('<3I',flags,r['addend'],r['instruction_offset'])
    # Extend ONLY existing SceLibKernel import arrays, retaining all 50 old NIDs
    # and stubs. One new user-mode API enables measured idle-clock telemetry.
    descriptor=0x306ad8
    size,version,attr,count,nv,nt=struct.unpack_from('<6H',code,descriptor)
    lib,_,_,nidptr,funptr=struct.unpack_from('<5I',code,descriptor+16)
    need(size==52 and count==50 and lib==0xcae9ace6 and nv==0 and nt==0,'LibKernel descriptor differs')
    entries=[]
    for i in range(count):
        nid=struct.unpack_from('<I',code,nidptr-fmt.CODE_BASE+i*4)[0]
        fun=struct.unpack_from('<I',code,funptr-fmt.CODE_BASE+i*4)[0]
        entries.append((nid,fun))
    need(all(n!=0xe0241faa for n,f in entries),'System-info import already exists')
    stub=meta['symbols']['nf_system_info']
    need(stub%16==0 and code[stub-fmt.CODE_BASE:stub-fmt.CODE_BASE+16]==bytes.fromhex('0000e0e31eff2fe10000a0e100000000'),'Native stub mismatch')
    entries.append((0xe0241faa,stub));entries.sort()
    new_nids=fmt.CODE_BASE+len(code)
    code+=struct.pack('<%dI'%len(entries),*[n for n,f in entries])
    new_funcs=fmt.CODE_BASE+len(code)
    for n,fun in entries:
        reloc+=struct.pack('<3I',0x200,fun-fmt.CODE_BASE,len(code))
        code+=struct.pack('<I',fun)
    struct.pack_into('<H',code,descriptor+6,len(entries))
    import_changes=[]
    for field,value in [(28,new_nids),(32,new_funcs)]:
        site=descriptor+field
        off,flags,ad=records[site]
        need(flags==0x200,'Unexpected import table pointer relocation')
        import_changes.append(dict(site=site,old_pointer=struct.unpack_from('<I',code,site)[0],new_pointer=value,record_offset=off))
        struct.pack_into('<I',code,site,value)
        struct.pack_into('<I',reloc,off+4,value-fmt.CODE_BASE)
    need(fmt.CODE_BASE+len(code)<=fmt.DATA_BASE,'Extended import table exceeds code space')
    ph[0][5]=len(code)
    segs=[bytes(code),segs[1],bytes(reloc)]
    output,raw_elf=fmt.wrap_self(original,header,elf,ph,segs)
    _,ne,np,back=fmt.parse_self(output)
    need(back==segs and fmt.plain_elf(ne,np,back)==raw_elf,'SELF/ELF roundtrip failure')
    allowed=set(range(GUARD_SITE-fmt.CODE_BASE,GUARD_SITE-fmt.CODE_BASE+4))
    for h in hooks:allowed.update(range(h['site']-fmt.CODE_BASE,h['site']-fmt.CODE_BASE+4))
    allowed.update(range(descriptor+6,descriptor+8))
    for change in import_changes:allowed.update(range(change['site'],change['site']+4))
    differences=[i for i,(x,y) in enumerate(zip(original_segs[0],back[0])) if x!=y]
    need(all(i in allowed for i in differences),'Undeclared original instruction changed')
    need(back[1]==original_segs[1],'Original initialized data changed')
    # Revert the eight integer division calls in a temporary view; the entire
    # original lighting worker must then match, including every FP instruction.
    lighting_start,lighting_end=0x2134ec,0x21513c
    reverted=bytearray(back[0][lighting_start:lighting_end])
    for h in hooks:
        s=h['site']-fmt.CODE_BASE
        if lighting_start<=s<lighting_end:
            need(h['category'] in ('lighting cache division','lighting cleanup phase gate'),'Unexpected lighting modification')
            reverted[s-lighting_start:s-lighting_start+4]=bytes.fromhex(h['original_bytes'])
    need(reverted==original_segs[0][lighting_start:lighting_end],'Lighting equations changed')
    audit=dict(revision='performance-patch '+PROFILE,hardware_tested=False,
        input_eboot_sha256=sha(original),output_eboot_sha256=sha(output),payload_sha256=sha(payload),
        payload_bytes=len(payload),payload_bss_bytes=meta['bss_size'],
        changed_original_byte_count=len(differences),branch_hooks=changed,
        fd_guard_site=hex(GUARD_SITE),fd_guard_entry=hex(guard_addr),fd_guard_bytes=GUARD.hex(),
        original_lighting_equations_preserved=True,
        cleanup_stagger_frames=37 if any(h['category']=='lighting cleanup phase gate' for h in hooks) else 0,cleanup_period_frames=300,
        import_changes=import_changes,new_import_nid=hex(0xe0241faa),new_import_stub=hex(stub),
        old_import_count=count,new_import_count=len(entries),
        original_initialized_data_identical=True,watchdog_unchanged=True,
        settings_clocks_shaders_assets_lod_unchanged=True,
        original_phdrs=original_ph,patched_phdrs=np,
        absolute_fixups_added=len(meta['absolute_relocations']),
        limitations=['No hardware execution/FPS or pixel-output measurements.',
                     'No full floating-point/NEON lighting rewrite.',
                     'No geometry batching or draw-call removal.',
                     'No asynchronous resource-decoding or save-I/O rewrite.',
                     'Core-load API availability and cache usefulness need on-device measurement.',
                     'Resource variant changes existing decoder affinity; no decode algorithm, upload or prefetch rewrite.',
                     'No pixel-output comparison, actual ARM-code emulation or on-device validation.'])
    return output,raw_elf,audit

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_vpk',type=Path)
    parser.add_argument('-o','--output',type=Path,default=None)
    parser.add_argument('--elf-out',type=Path)
    parser.add_argument('--eboot-out',type=Path)
    parser.add_argument('--profile',choices=list(json.loads((ROOT/'profiles.json').read_text())),default='combined')
    a=parser.parse_args()
    global PROFILE,PAYLOAD_ROOT,PAYLOAD_SHA
    PROFILE=a.profile;PAYLOAD_ROOT=ROOT/'builds'/PROFILE/'payload'
    manifest=json.loads((ROOT/'builds'/PROFILE/'manifest.json').read_text())
    PAYLOAD_SHA=manifest['payload_sha256']
    need(sha((PAYLOAD_ROOT/'hooks.json').read_bytes())==manifest['hooks_sha256'],'Hook manifest checksum mismatch')
    source=a.original_vpk.resolve();out=(a.output or Path('nfsmw_performance.vpk')).resolve()
    paths=[out,out.with_suffix('.audit.json')]+[p.resolve() for p in [a.elf_out,a.eboot_out] if p]
    need(source.is_file(),'Input VPK missing')
    need(len(set(paths))==len(paths) and source not in paths,'Input/output path collision')
    for p in paths:need(not p.exists() and p.parent.is_dir(),'Output exists or parent missing: '+str(p))
    with zipfile.ZipFile(source) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        need(len(set(names))==len(names) and names.count('eboot.bin')==1,'Invalid VPK entries')
        eboot,elf,audit=patch_executable(z.read('eboot.bin'))
        stable={};buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as dst:
            dst.comment=z.comment
            for info in infos:
                data=eboot if info.filename=='eboot.bin' else z.read(info)
                if info.filename!='eboot.bin':stable[info.filename]=sha(data)
                dst.writestr(info,data)
    vpk=buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(vpk)) as z:
        need(z.testzip() is None,'Package CRC failure')
        need(z.read('eboot.bin')==eboot,'Packaged executable mismatch')
        for name,h in stable.items():need(sha(z.read(name))==h,'Non-executable content changed')
    audit.update(output_vpk_sha256=sha(vpk),input_vpk_sha256=sha(source.read_bytes()),identical_non_eboot_entries=stable)
    out.write_bytes(vpk);out.with_suffix('.audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    if a.elf_out:a.elf_out.write_bytes(elf)
    if a.eboot_out:a.eboot_out.write_bytes(eboot)
    print('Created:',out,'bytes:',len(vpk),'SHA256:',sha(vpk))
    print('Static construction checks passed. Physical Vita testing still required.')
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,zipfile.BadZipFile,KeyError) as ex:
        print('ERROR:',ex,file=sys.stderr);sys.exit(1)
