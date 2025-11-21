# Contributing

To contribute new features to this codebase, first install [`ape`](https://apeworx.io/framework).

## Versioning Guidelines

Since this monorepo produces multiple artifacts for it's tagged versions, it's important to understand how they fit together.

### Smart Contract Code

only major version changes (e.g. `v1`, `v2`, etc.) are allowing to make upgrades to the smart contract code used by all other components (frontend, indexing server, Python SDK, etc.).
If there is a breaking change that would make updates to the smart contract code that would require re-deploying it, those updates will only get "published" on a major version.
Therefore, we keep track of the latest build of the smart contracts as the "next" package manifest bundled with the other components, e.g. `v1.json` maps to what the "published" manifest will be **on the next major version release**.
"Publishing" the package manifest simply corresponds to undoing the symbolic link to the built version of the package, and then adding a new symbolic link targeting the next major version that will come along.
Just prior to that major release, there will be "pre-audit" tags (e.g. `vX.0.0-preaudit.Y`) that match to the expected release of that code, where signnificant changes should not be anticipated, but minor updates to resolve security defects can still be done.
Once patched and released as a major version, those artifacts will have to get published on any supporting chain.

### Python SDK

The Python SDK (e.g. `ruffsack` library) is published to PyPI on every patch tag of this repo.
This is the primary artifact for the indexing service component, and is also intended as the primary way to [add support for Ruffsack](#deploying-to-a-new-chain) on your preferred chain (via the built-in `ruffsack` CLI).

### Indexing Service

When a new version of the Python SDK is released, this will cause a release of an update to the `ghcr.io/apeworx/ruffsack-service:stable` container image tag.
Version tags will also be published alongside `stable`, but `stable` will be the only recommended and supported version of the image available.
There will also be a `latest` tag that matches the current version available on `main` for use by those who require an un-released version of the service, but it's use is not recommended to use that one.

### Javascript SDK

The Javascript module for working with Ruffsack will be published for each release, alongside the Python SDK.
The corresponding version of these modules are used in the published frontend.

### Frontend

The frontend code will be published on every commit to `main` on IPFS, and that content will become pinned.
The pin that will be "published" as the "official" version of the UI that will only be updated on every official release (if the content has changed since the last release)
No intermediate versions of the frontend will be maintained by this monorepo.

## Deploying to a New Chain

You can create a deployment of Ruffsack on any chain supported by Ape easily using the built-in `ruffsack` CLI.

However, there are some pre-requisites that are needed first before deploying Ruffsack to a new chain:

1. The [`CREATE2` opcode](https://eips.ethereum.org/EIPS/eip-1014) must be supported on that chain
2. [CreateX](https://createx.rocks) must be deployed on that chain
3. You should have an account imported to [`ape`](https://docs.apeworx.io/ape/stable/userguides/accounts#live-network-accounts) that is funded with sufficient gas and can deploy the required system components on that chain

Once you have met the pre-requisites, it is easy to perform this procedure by using the following commands:

```sh
# Deploy the proxy factory/registry contract
$ ruffsack sudo deploy factory --network ... --account ...

# Deploy a supported version of the Ruffsack contract
# NOTE: do this for each version you want to support...
$ ruffsack sudo deploy singleton [--version <supported version>] --network ... --account ...
```
