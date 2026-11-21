# Darcy training-file correspondence

On training indices 0–639 inclusive, the 16-grid file is an exact, same-index restriction of both larger training files checked below. Only named training members were extracted. No official test examples or final holdout examples entered the comparison. Source: [Zenodo record 12784353](https://zenodo.org/records/12784353).

| Grid | Training pairs | Training member SHA-256 |
|---|---:|---|
| 16 | 1,000 | 0be662acdb1dab7dfd1a1da0b140e97f75cc94f98a14edcf768abe6968b3b418 |
| 32 | 5,000 | f44a1151802eaf2eac65ddaded1ecf105bac019add0e3d277a3e9939cca1cd8b |
| 64 | 5,000 | f6a5b776b38b8da6d257f9f1bf350d773636fcc14eb83f0afc1357faa08c5039 |

All three compressed archives matched the record's MD5 checksums. For each larger grid of width N, compare each tensor slice [0:640, ::k, ::k] with its 16-grid counterpart, where k = N/16. Each of the four comparisons had zero unequal elements out of 163,840. All 640 restricted fields were distinct within each comparison. Float32 coefficients 0 and 1 map to False and True respectively. Float32 pressures require no scaling, offset, axis exchange or interpolation. The relative pressure discrepancy (L2 norm of difference divided by reference norm) is exactly zero for both restrictions.

The first row and column survive. The last retained coordinate is 30 of 31 or 60 of 63 (zero-based) on each axis. All 38,400 coarse perimeter pressure values were nonzero, ranging from −0.009102881 to 0.92605597. Imposing zero pressure around this stored perimeter would change the reference fields.

## Fine-grid provenance remains open

The 421 archive is a 12,090,734,827-byte gzip stream (published MD5 d6600431a21ebae44b05eac601451b17). Compressed bytes 0–1,048,575 had SHA-256 81bd9dfa0d542f91163138449a39842ccbc0913bd696b862ead824b724ea32c9. The first tar header identifies darcy_train_421.pt, 7,089,640,955 bytes. Its PyTorch metadata describes two float32 views of shape (4000,421,421) with strides (1,2105000,5000). The first backing storage alone has 886,205,000 floats preceding the pressure storage. A compressed byte offset cannot independently decode the pressure without a gzip restart index or sequential inflation. Available disk was 7.6 GiB, below the compressed archive size. The prefix inspection did not verify pressure correspondence, physical permeability polarity, or stride 28. A streaming fine-grid comparison remains possible. The confirmed restriction discrepancy measures data agreement only. The generating PDE operator and its actual relative equation residual remain unresolved.
