#!/usr/bin/env python3
"""Recompile the freestanding ARM payload for the combined patch.
Needs clang, ld.lld, Python 3.9+. Not needed to use the ready VPKs/builder.
"""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
r=Path(__file__).resolve().parent
(r/'payload').mkdir(parents=True, exist_ok=True)
for name,flags in json.loads((r/'profiles.json').read_text()).items():
 env=dict(os.environ)
 # Shell variable expansion does not re-evaluate escapes. Literal quote chars
 # must reach the C preprocessor as part of the -D argument.
 env['V5_CFLAGS']=' '.join('-D%s=%s'%(k,v) for k,v in flags.items())+' -DV5_PROFILE="'+name+'"'
 subprocess.run(['sh',str(r/'source/rebuild_payload.sh')],check=True,env=env)
 dest=r/'builds'/name/'payload'
 for file in ['payload.bin','payload.json']:shutil.copyfile(r/'payload'/file,dest/file)
 shutil.copyfile(r/'source/payload.elf',dest/'payload.elf')
 manifest={f+'_sha256':hashlib.sha256((dest/(f+'.bin' if f=='payload' else f+'.json')).read_bytes()).hexdigest() for f in ['payload','hooks']}
 manifest.update(profile=name,compile_defines=flags,hardware_tested=False)
 (dest.parent/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('BUILT',name,flush=True)
