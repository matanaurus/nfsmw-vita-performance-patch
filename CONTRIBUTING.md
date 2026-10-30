# Contributing

Thanks for helping with the performance patch. This repository currently targets **one exact original executable hash** (see README). Code aimed at other builds should be kept separate unless it has an independently verified address, instruction and relocation map.

- **Never commit** original or modified VPKs, original game executables/assets, firmware files, personal save files, or unredacted logs/crash dumps.
- Keep graphics quality and draw order intact. Avoid changes that silently remove lighting work, draw calls, transparency or geometry.
- Document exact-build hook sites and whether old instructions/relocations are checked.
- Run the host-model tests and, when possible, the static VPK validator against your *own* original VPK. Do not describe mock/static tests as hardware proof.
- Include real Vita testing details: 960 × 544, CPU/GPU clocks, camera/route, number of performance windows, and notable hitches.
- Separate **measurements**, **inference** and **hypotheses** in issue reports.

See [Implementation details](docs/IMPLEMENTATION.md) for patch boundaries and [Performance notes](docs/PERFORMANCE.md) for valid comparisons.
