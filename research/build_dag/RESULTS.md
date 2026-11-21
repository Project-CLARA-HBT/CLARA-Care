# Reordering build tasks using durations from an earlier build

**Retire this candidate.** At four slots, searching for a single priority swap reduced zlib's replay makespan to 17.502 seconds. Its strongest competitor, longest historical task first, took 17.818 seconds. On libdeflate the same search tied three baselines at 20.950 seconds. It also lost to historical critical path on libdeflate at two and eight slots. The prespecified requirement for a strict four-slot gain on both projects failed.

| Project | Slots | Lexical | Longest task | Critical path | History-selected list | Single swap | Historical CP-SAT |
|---|---:|---:|---:|---:|---:|---:|---:|
| zlib | 2 | 35.239 | 34.673 | 35.007 | 34.673 | 34.659 | 35.007 |
| zlib | 4 | 20.431 | 17.818 | 17.895 | 17.895 | 17.502 | 19.822 |
| zlib | 8 | 13.020 | 9.792 | 9.792 | 9.792 | 9.792 | 9.792 |
| libdeflate | 2 | 40.088 | 39.765 | 39.726 | 39.765 | 39.797 | 40.745 |
| libdeflate | 4 | 26.422 | 20.950 | 20.950 | 20.950 | 20.950 | 23.056 |
| libdeflate | 8 | 16.858 | 15.945 | 15.945 | 16.858 | 16.858 | 15.945 |

All cells give seconds on the second capture. The observed native Ninja four-worker executions finished in 18.924 seconds for zlib and 21.926 seconds for libdeflate. Native wall time includes launcher and dispatch costs that the replay omits. Replaying the measured durations under a different order assumes that contention leaves those durations unchanged.

We retained all 41 zlib commands and all 30 libdeflate commands in the default targets, counting multiple outputs of one command once. The graphs have 43 and 29 distinct direct command precedences after collapsing phony targets. The two previous serial builds supplied all historical estimates. The reviewer can inspect each command's original start and finish, parents, multiple outputs and second-build schedule in the included JSON files. The replay enforces both processor capacity and precedence. Scheduling priorities are computed before simulation of the second run.

HEFT ranks tasks using their upward rank and assigns resources by earliest finish. Historical critical path uses the corresponding weighted path priority on identical workers with zero communication cost. Our work-conserving dynamic dispatch when duration predictions err is a specific adaptation of that priority. CP-SAT optimizes nonpreemptive intervals with precedence and cumulative demand on historical durations. At eight workers it certified the historical optimum on both projects. With the same deterministic limit at two and four workers it found feasible schedules with open bounds. A historical optimum is not an oracle for a future build. Single-swap search evaluated 820 swaps per zlib cell and 435 per libdeflate cell, plus three starting lists. Priority search, critical paths and interval optimization are established techniques. These results supply no new scheduling theorem or significant speedup across projects. [HEFT, Topcuoglu et al.](https://doi.org/10.1109/71.993206) · [OR-Tools scheduling reference](https://developers.google.com/optimization/scheduling/job_shop)

## Source and reproduction

The measurements come from unmodified release build rules for [zlib](https://github.com/madler/zlib/tree/51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf) and [libdeflate](https://github.com/ebiggers/libdeflate/tree/78051988f96dc8d8916310d8b24021f01bd9e102). Each project was configured with CMake 3.31.6, Ninja 1.11.1.git.kitware.jobserver-1 and Ubuntu GCC 13.3.0. The zlib CMake configuration renames its distributed zconf.h. Separate build directories retain the capture logs. Timing reproduction on another host will differ. To collect fresh captures run the following commands on each pinned source checkout with fresh output directories.

```sh
cmake -S "$source_dir" -B "$history_dir" -G Ninja -DCMAKE_BUILD_TYPE=Release
ninja -C "$history_dir" -j1 all
cmake -S "$source_dir" -B "$next_dir" -G Ninja -DCMAKE_BUILD_TYPE=Release
ninja -C "$next_dir" -j4 all
python capture.py "$history_dir" > history.json
python capture.py "$next_dir" > next.json
```

From this study directory, replay the committed timings with Node 24. The independent checker recomputes the completion time, slot capacity and every precedence constraint at each recorded start. The optional solver run uses OR-Tools 9.14.6206 and saves the optimized priorities alongside historical bounds. Solver wall time is observational.

```sh
node --check replay.mjs
for project in libdeflate zlib; do
  node replay.mjs "$project" | diff - "$project/results.json"
done
python verify.py zlib libdeflate
python optimize.py zlib/history.json > /tmp/zlib-cp-replay.json
```

These six cells reuse two pairs of builds, without independent samples of build-to-build variability. The [protocol](PROTOCOL.md) treats them as a development elimination experiment.
