# CLARA offline training environment

This image is isolated from `services/api` and `services/ml`. It is not part of
the online Compose stack, contains no application credentials, and must not
connect directly to production OLTP.

The base image is digest-pinned and the selected classical ML packages are
exact-version pinned in `requirements.lock`. Training input must be an audited,
purpose/consent-filtered, pseudonymized snapshot with a precomputed
person/household/site/source/time split. Output is an immutable manifest plus
checksummed artifact; the offline signer adds an Ed25519 signature. The online
loader receives only allowlisted public keys.

PyTorch, notebooks, foundation models and accelerator runtimes are deliberately
absent. Add them only in a new approved use-case/change record with a separate
locked image and license/supply-chain review.

Build:

```bash
podman build -t clara-training:classical-20260729 services/training
```

Do not mount `.env`, cloud credentials, production database sockets, or raw
identity mapping keys into this image.
