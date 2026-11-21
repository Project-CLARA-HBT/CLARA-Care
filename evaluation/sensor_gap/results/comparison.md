# Held-out development comparison

29 paired weeks per record. Each cell reports mean absolute error.

| Record | Hours | Linear | Seasonal | Direct forest | Residual forest |
| --- | ---: | ---: | ---: | ---: | ---: |
| ETTh1 | 6 | 0.5268 | 1.4610 | 1.1210 | 1.1327 |
| ETTh1 | 24 | 0.9536 | 1.2241 | 1.9484 | 1.4385 |
| ETTh1 | 72 | 1.3546 | 2.0900 | 2.6617 | 2.1058 |
| ETTh2 | 6 | 1.2073 | 2.8392 | 2.3180 | 1.3997 |
| ETTh2 | 24 | 3.9218 | 2.3370 | 2.9172 | 2.5874 |
| ETTh2 | 72 | 4.6465 | 4.1614 | 3.8573 | 3.3462 |
| **Macro MAE** | | 2.1018 | 2.3521 | 2.4706 | 2.0017 |

| Baseline | MAE reduction | Relative reduction | Paired 95% interval (MAE units) |
| --- | ---: | ---: | ---: |
| linear | 0.1001 | 4.76% | [-0.4626, 0.5833] |
| seasonal | 0.3504 | 14.90% | [-0.0279, 0.7211] |
| direct | 0.4689 | 18.98% | [0.2219, 0.7173] |

The residual forest missed the frozen superiority criterion.
