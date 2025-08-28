# Packages

The `ruffsack` Python module needs to ship with all current and past versions of the
`Ruffsack`/`RuffsackProxy`/`RuffsackFactory` contract artifacts in order to work.
If a new release is created, the current highest version (see `pyproject.toml`) should
be locked to final release artifact built by ape via `ape compile`, and then the next
release should be symbolically linked to `../../.build/__local__.json` for development.

This allows the `ruffsack` Python module (and it's dependents e.g. the Ruffsack API service)
to support all deployed versions of the system.
