# Independent-generator development result

Oriented four-corner pattern ridge achieved the lowest mean missing-node relative L2 across 128 fresh PhysicsNeMo fields. Its gain over the strongest overall control, histogram gradient boosting, was **8.04%** (paired field bootstrap 95% interval 6.82–9.24%, 118/128 wins). The predeclared 10% screen failed. Boosting also had lower exterior error, where the last fine-grid row and column require extrapolation. [Frozen protocol](PROTOCOL.md) · [All paired results](summary.json)

| Arm | All missing | Interior | Exterior | Overall pattern gain |
|---|---:|---:|---:|---:|
| Oriented pattern ridge | 0.015074 | 0.012089 | 0.090481 | — |
| Histogram gradient boosting | 0.016392 | 0.014344 | 0.079373 | 8.04% |
| Population ridge | 0.016842 | 0.013971 | 0.094656 | 10.49% |
| Material CNN | 0.017799 | 0.015193 | 0.093555 | 15.31% |
| Pooled ridge | 0.018323 | 0.015096 | 0.104424 | 17.73% |
| Pressure CNN | 0.023343 | 0.020288 | 0.114332 | 35.42% |

Across 640 distinct binary coefficient fields, the maximum absolute reconstructed interior discrete pressure residual was 0.000619 for unit source (RMS 0.0000620). All methods preserved the 256 observed nodes exactly. Independent-generator synthetic development evidence covers this solver, permeability contrast, grid and sampling scheme. Each arm was refit on this generator; cross-generator weight transfer and final holdout performance remain unmeasured. [Cohort archive](fields.npz) · [Source and replay instructions](REPRODUCE.md) · [Residual audit](audit.json)
