# Changes from the upstream PS Vita port

**Base:** [germanalvarez15/nfsmw-vita, release 1.3.7](https://github.com/germanalvarez15/nfsmw-vita/releases/tag/1.3.7). This repository publishes **one combined performance patch built directly from the checksum-matched original executable**; development prototypes are not separate releases or required installation steps.

## CPU-side lighting

- Distributes the eight original cache-owning lighting groups among CPU 0, the CPU 1 renderer and CPU 2 helpers instead of concentrating work on the renderer.
- Uses per-worker native semaphores, atomic single-owner job claims, start/error fallbacks and a strict completion barrier. Every group still executes, with its original floating-point lighting calculations.
- Orders work using previous cost measurements and gives CPU 0 an advisory work budget based on sampled core utilization.
- Supports an additional CPU 0 wake when the main thread enters a later rendering handoff wait.
- Spreads cache maintenance checks across a 300-frame period to avoid synchronized cleanup spikes.

## Draw preparation and graphics state

- Adds exact integer quotient/remainder fast paths at 64 individually verified call sites, forwarding unsupported cases to the original routine.
- Avoids redundant blend state and client-array enable/disable operations when the current state already matches.
- Specializes known-target buffer/texture binding operations at verified call sites.
- Reuses fixed-function vertex, color and texture-coordinate layouts when unchanged, without clearing existing dirty flags or skipping any draw.
- Preserves the original geometry, draw-call ordering, rendering parameters, textures, shaders, effects and lighting fidelity.

## Resource handling, stability and profiling

- Extends CPU affinity of existing I/O, texture-decoding and geometry-decoding workers to CPU 0 / CPU 2, with fallback on errors. Existing queues, codecs, file operations and save behavior remain unchanged.
- Adds direct file-read statistics and timing, core-load sampling, lighting-worker distribution, rendering wait, draw-state and layout-reuse counters.
- Retains the watchdog and a narrowly scoped invalid-file-handle seek guard that prevents one observed null lookup dereference (it does not identify or cure all possible file-handle faults).
- Leaves clock defaults, user configuration, game assets and original non-executable VPK members unchanged.

## Intentional limitations

- **No draw-call batching or draw elimination.** Repeated state/layout preparation is reduced, but every original draw is submitted.
- **No subdivision of cache-owning lighting groups, floating-point lighting rewrite, texture/model decoder rewrite, upload scheduler or speculative prefetching.**
- Previous experimental small-read caching was discarded after negligible observed gameplay hits; the published patch uses the original direct file-read path with profiling.
- Hardware measurements indicate improvements but do not guarantee 30 FPS or prove exact per-frame output identity.

See [Performance measurements](docs/PERFORMANCE.md) and [Implementation notes](docs/IMPLEMENTATION.md).
