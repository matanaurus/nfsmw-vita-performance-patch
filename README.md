# Need for Speed: Most Wanted (PS Vita) — Performance Patch

**An unofficial performance optimization for the PS Vita port of Need for Speed: Most Wanted (2005), based on [germanalvarez15/nfsmw-vita release 1.3.7](https://github.com/germanalvarez15/nfsmw-vita/releases/tag/1.3.7).**

The original Vita port and its features are the work of its upstream author(s). This project is a separate community patch for one **specific, checksum-verified executable**. It is not a standalone game, a replacement for the upstream project, or an official update.

## Performance

| | Original port | Performance patch |
|---|---:|---:|
| **Observed median FPS** | **22.0 FPS** | **28.2 FPS** |
| Resolution | 640 × 368 | **960 × 544 (native Vita)** |
| CPU clock | 500 MHz | 500 MHz |
| GPU clock | 222 MHz | 222 MHz |

These numbers come from gameplay logs recorded on PS Vita hardware. The patched **28.2 FPS is the median of the opening ~40% of a recorded knockout race**, while the original **22.0 FPS is a median from an earlier, different gameplay recording**. The original run also used a lower rendering resolution. **These are not matched-scene, matched-resolution benchmarks, so the difference must not be treated as a verified percentage gain solely attributable to this patch.** Window-average FPS is not instantaneous minimum FPS, and heavier scenes can still run below 30 FPS.

For methodology and limitations, read [Performance measurements](docs/PERFORMANCE.md).

## Improvements over upstream 1.3.7

### Lighting and CPU scheduling

- **Three-core lighting execution:** CPU-side lighting cache groups can run on CPU 0, CPU 1 (renderer), and CPU 2, instead of concentrating the work on the rendering thread.
- **Adaptive group distribution:** eight original cache-owning groups are dynamically claimed and prioritized using previous timing measurements. An advisory CPU 0 work budget responds to measured core load, and the helper can rejoin during a later render handoff wait.
- **Safe worker coordination:** per-worker kernel semaphores, single-owner group claims, failure fallbacks and a completion barrier. Every original lighting group completes before rendering advances.
- **Staggered lighting-cache maintenance:** avoids scheduling all cache-maintenance checks on the same frame.

### CPU-side graphics performance

- **Exact integer quotient/remainder fast paths** at 64 verified call sites, including lighting-cache operations, with original behavior retained for unsupported divisors.
- **Avoidance of redundant blending and vertex-array enable/disable changes** when the graphics state is already correct.
- **Specialized verified buffer and texture bindings** for call sites with a known target.
- **Vertex-layout reuse:** prevents unnecessary fixed-function layout invalidations when the layout is unchanged, while still updating the original buffer pointers and submitting every draw.

### Loading, worker scheduling, and stability

- **More flexible resource-worker placement:** existing file-I/O, texture-decoding and geometry-decoding workers can use CPU 0 or CPU 2, with fallback to their previous affinity if needed. Their queues and decoding algorithms are unchanged.
- **Better diagnostics:** core utilization, lighting distribution, render handoff, graphics hot-path and file-read timing counters aid profiling on actual hardware.
- **Stability fixes:** replacement of the earlier experimental lighting barrier with native semaphores, plus a narrowly scoped invalid-file-handle seek guard; the original watchdog remains enabled.

**Visual fidelity is preserved by design:** no intentional changes to texture detail, geometry, lighting equations, resolution, reflections, effects, draw order, LOD or clock defaults. The patch **does not** combine draw calls, replace shaders, rewrite model/texture decoding, or guarantee 30 FPS in every scene.

For technical implementation details and a list of validated hooks, read [Implementation notes](docs/IMPLEMENTATION.md). A consolidated list of changes is available in [CHANGELOG.md](CHANGELOG.md).

## Build your own patched VPK

Requirements: **Python 3.9+** and your own compatible **original** `nfsmw.vpk` from the [upstream 1.3.7 release](https://github.com/germanalvarez15/nfsmw-vita/releases/tag/1.3.7). The builder uses Python's standard library; no VitaSDK compiler is needed to generate a VPK using the included patch-only payload.

**Windows PowerShell:**

```powershell
py -3 build_vpk.py "C:\path\to\nfsmw.vpk" -o "nfsmw_performance.vpk"
```

**Linux / macOS:**

```bash
python3 build_vpk.py /path/to/nfsmw.vpk -o nfsmw_performance.vpk
```

The builder creates a complete VPK **locally from your own original files**. It does not modify the input or include copyrighted game data in this repository.

### Exact executable compatibility

Only the matching upstream executable is supported. The builder checks the original `eboot.bin` SHA-256 and verified instruction/relocation sites before making changes; it fails safely for other versions or already-patched executables.

| File | SHA-256 |
|---|---|
| Required original `eboot.bin` | `ffae9cef5b2819570ae95ca4fc5c9663879f8de0b0ef14d2f1a22925928ad24b` |
| Original test VPK, reference only | `88075aa6f52a60192e93b6f49706e6b1d751479f061a06792e3d51b43265d4fd` |
| Tested patch output VPK, reference only | `21fa87a9f1664fe6116dea8ed001828cd3dc5316e3a5436ad829449a17f4854a` |

The original VPK hash is informational; repackaging ZIP entries may change it without changing the executable. This project does not automatically support every future upstream release, and the 1.3.7 release label alone is not a substitute for a matching executable checksum.

### Install and test

1. Back up your original installation, saves, and `ux0:data/nfsmw/config.ini`.
2. Close the game completely, then use VitaShell to install the **locally built** VPK over your current installation. Do not delete the game's data directory.
3. The recorded benchmark configuration was **960 × 544, CPU 500 MHz, GPU 222 MHz, `render_thread=1`**, with other graphical effects unchanged.
4. Check gameplay, visuals and `ux0:data/nfsmw/nfsmw.log` (look for `[cpu-balance]` diagnostic lines).
5. If you encounter crashes, visual defects, or worse performance, restore the backed-up working installation.

## Repository contents

```text
build_vpk.py                Local patcher / VPK packaging tool
self_format.py              PS Vita SELF/ELF construction utilities
builds/combined/payload/    Patch-only compiled payload and verified hook map
guard/                      Narrow file-seek guard assembly/source
source/                     Freestanding ARM patch source and rebuild scripts
rebuild_all.py              Optional source compilation (LLVM required)
tests/                      Host test models and static validation
docs/                       Implementation and performance methodology
.github/workflows/          Automated host checks
```

To recompile the freestanding ARM patch-only payload (optional, requires LLVM `clang`, `ld.lld` and Python), run:

```bash
python3 rebuild_all.py
```

To validate your locally built VPK against your original (static checks, not on-device execution):

```bash
python3 tests/validate_package.py /path/to/nfsmw.vpk nfsmw_performance.vpk combined
```

To run host-model tests on Linux with GCC:

```bash
python3 tests/run_tests.py
python3 tests/run_patch_components.py
python3 tests/run_hotpaths.py
python3 tests/run_components.py
```

Host tests and package checks are **not** substitutes for visual and performance testing on actual Vita hardware.

## Upstream credit, licensing and distribution

**Based on [Need for Speed: Most Wanted — PS Vita port, release 1.3.7 by germanalvarez15](https://github.com/germanalvarez15/nfsmw-vita/releases/tag/1.3.7).** Please visit the [upstream project](https://github.com/germanalvarez15/nfsmw-vita) for the port itself, its updates, requirements and original credits.

This repository contains **no original or modified full game VPK, no full game executable, no original game assets, and no saved user data**. Users must obtain their own legal copy and create the patched VPK locally. Do not upload the original or modified game executable/game files as GitHub Release attachments without the necessary rights.

The included [MIT license](LICENSE) covers only newly authored patch code and documentation where applicable, **not** Electronic Arts' game, Sony software, upstream port code or third-party libraries such as [vitaGL](https://github.com/Rinnegatamante/vitaGL) and [VitaSDK](https://vitasdk.org/). This is an independent fan/community project and is not endorsed by Electronic Arts, Sony or the upstream port author.

For contributions and bug reports, see [CONTRIBUTING.md](CONTRIBUTING.md). Please redact personal information from logs before posting them publicly.
