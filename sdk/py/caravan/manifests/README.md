# Packages

The `caravan` Python module needs to ship with all current and past versions of the
`Caravan`/`CaravanProxy`/`CaravanFactory` contract artifacts in order to work.
When a new major release is created, the current highest version (see `pyproject.toml`) should
be "locked" to final release artifact built by ape via `ape compile`, and then the next
major release should be symbolically linked to `.build/__local__.json` for continued development.

This allows the `caravan` Python module (and it's dependents e.g. the Caravan API service)
to support all deployed versions of the system.
