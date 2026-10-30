# Performance Patch — release notes

An unofficial performance optimization for **Need for Speed: Most Wanted (2005) on PS Vita**, based on **[germanalvarez15/nfsmw-vita release 1.3.7](https://github.com/germanalvarez15/nfsmw-vita/releases/tag/1.3.7)**. Full credit for the original port belongs to its upstream author(s).

## Observed performance

| | Original port | Optimized patch |
|---|---:|---:|
| Median gameplay FPS | **22.0** | **28.2** |
| Rendering resolution | 640 × 368 | **960 × 544** |
| CPU / GPU clocks | 500 / 222 MHz | 500 / 222 MHz |

The **28.2 FPS** result is a median over the opening ~40% of one recorded knockout race; **22.0 FPS** comes from an earlier original-gameplay recording at a lower resolution and with different scenes. These are observational measurements, **not a controlled same-scene benchmark** or a proven percentage speedup. Demanding areas can still fall below 30 FPS.

## Improvements over the original

- **Three-core lighting scheduling:** lighting groups distributed between CPU 0, CPU 1 and CPU 2, with adaptive work allocation, render-wait assistance and staggered cache maintenance.
- **Graphics hot-path optimizations:** exact integer arithmetic for verified cases, redundant blend/vertex-array state suppression, specialized bindings, and fixed-function vertex-layout reuse. The same draw calls and graphics quality remain.
- **Resource-worker improvements:** flexible CPU 0/CPU 2 affinity for existing I/O and decoder workers; additional read, render, scheduler and core-utilization diagnostics.
- **Stability improvements:** per-worker semaphores, synchronized completion and a narrowly scoped invalid file-handle guard, with the original watchdog retained.

No intentional reductions to resolution, textures, lighting, effects, geometry or LOD. This does **not** introduce geometry batching or asynchronous decoding, and does not guarantee locked 30 FPS.

## Build and installation

The repository includes the patch source, patch-only payload, Python build tool, static validation and host tests; **it does not include the game**.

```bash
python3 build_vpk.py /path/to/original/nfsmw.vpk -o nfsmw_performance.vpk
```

Requires an original executable matching the checksum in README. Install your locally built VPK using VitaShell and retain a backup of your saves/configuration.

**Distribution:** Do not attach copyrighted original or fully patched game VPKs/`eboot.bin` to a public GitHub release without the necessary rights. See [README.md](README.md) for compatibility, license and testing limitations.
