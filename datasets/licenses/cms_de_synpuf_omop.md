# CMS DE-SynPUF OMOP local source record

- Registry IDs: `cms_de_synpuf_omop`, `cms_de_synpuf_omop_100k`
- Local source inspected: 2026-08-12
- Access classification: open public-use agreement
- Data type: synthetic claims converted to OMOP CDM

The operator supplied separate 1K, 100K, and approximately 2.3M directories.
They are not interchangeable cohorts. The exact conversion release,
provider-published file inventory, and canonical checksums are unresolved.

The 100K directory contains 17 gzip-compressed OMOP tables and passed a local
`gzip -t` stream check. This is a development source only until it is hashed,
frozen, and normalized through a reviewed adapter.

The approximately 2.3M directory contains 50 canonical-looking LZO objects and
one extra temporary-suffix object,
`condition_era.csv.3.lzo.f9049F32`. The extra object fails `lzop -t` with a
compressed-data violation; the corresponding canonical
`condition_era.csv.3.lzo` passes. Repository verification therefore fails
closed on the extra object. Nothing in this record authorizes deleting or
repairing operator data, and no full-distribution integrity or completeness
claim is made.
