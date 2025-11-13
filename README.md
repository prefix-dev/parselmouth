<h1>
  <a href="https://github.com/prefix-dev/parselmouth/">
  </a>
</h1>

<h1 align="center">

![License][license-badge]
[![Build Status][build-badge]][build]
[![Project Chat][chat-badge]][chat-url]

[license-badge]: https://img.shields.io/badge/license-BSD--3--Clause-blue?style=flat-square
[build-badge]: https://img.shields.io/github/actions/workflow/status/prefix-dev/parselmouth/updater.yml?style=flat-square&branch=main
[build]: https://github.com/prefix-dev/parselmouth/actions
[chat-badge]: https://img.shields.io/discord/1082332781146800168.svg?label=&logo=discord&logoColor=ffffff&color=7389D8&labelColor=6A7EC2&style=flat-square
[chat-url]: https://discord.gg/kKV8ZxyzY4

</h1>

# parselmouth: Conda mapping runner

## Overview

`parselmouth` is a utility designed to facilitate the mapping of Conda package names to their corresponding PyPI names and the inverse. This tool automates the process of generating and updating mappings on an hourly basis, ensuring that users have access to the most accurate and up-to-date information.

## Conda to PyPI

Example of mapping for `numpy-1.26.4-py311h64a7726_0.conda` with sha256 `3f4365e11b28e244c95ba8579942b0802761ba7bb31c026f50d1a9ea9c728149`

```json
{
  "pypi_normalized_names": ["numpy"],
  "versions": {
    "numpy": "1.26.4"
  },
  "conda_name": "numpy",
  "package_name": "numpy-1.26.4-py311h64a7726_0.conda",
  "direct_url": [
    "https://github.com/numpy/numpy/releases/download/v1.26.4/numpy-1.26.4.tar.gz"
  ]
}
```

A more simplified version of our mapping is stored here: `files/mapping_as_grayskull.json`

## PyPI to conda

Example of mapping `requests` to the corresponding conda versions is, this shows you the known conda names per PyPI version, if a version is missing it is not available on that conda channel:

```
{"2.10.0": ["requests"], "2.11.0": ["requests"], "2.11.1": ["requests"], "2.12.0": ["requests"], "2.12.1": ["requests"], "2.12.4": ["requests"], "2.12.5": ["requests"], "2.13.0": ["requests"], "2.17.3": ["requests"], "2.18.1": ["requests"], "2.18.2": ["requests"], "2.18.3": ["requests"], "2.18.4": ["requests"], "2.19.0": ["requests"], "2.19.1": ["requests"], "2.20.0": ["requests"], "2.20.1": ["requests"], "2.21.0": ["requests"], "2.22.0": ["requests"], "2.23.0": ["requests"], "2.9.2": ["requests"], "2.27.1": ["requests", "arm_pyart"], "2.24.0": ["requests", "google-cloud-bigquery-storage-core"], "2.26.0": ["requests"], "2.25.1": ["requests"], "2.25.0": ["requests"], "2.27.0": ["requests"], "2.28.0": ["requests"], "2.28.1": ["requests"], "2.31.0": ["requests", "jupyter-sphinx"], "2.28.2": ["requests"], "2.29.0": ["requests"], "2.32.1": ["requests"], "2.32.2": ["requests"], "2.32.3": ["requests"]}
```

## Online availability

There are currently two mappings that are online, one of which is work in progress (#2) and are available behind the following URL:
`https://conda-mapping.prefix.dev/`:

1. The **Conda - PyPI** name mapping that maps a conda package version and name to it's known PyPI counterpart.

   This is available at `https://conda-mapping.prefix.dev/conda-forge/hash-v0/{sha256}` where the
   `{sha256}` is the sha256 of the conda package, taken from a package record from the channels `repodata.json` file.

   So, for example, to find the PyPI name of `numpy-1.26.4-py310h4bfa8fc_0.conda` you can use the following URI:
   `https://conda-mapping.prefix.dev/hash-v0/914476e2d3273fdf9c0419a7bdcb7b31a5ec25949e4afbc847297ff3a50c62c8`

2. **(WIP)** The **PyPI - Conda** name mapping that maps a PyPI package to it's known Conda counterpart. This only works for packages that are available on the conda channels that it references. This is available at `https://conda-mapping.prefix.dev/pypi-to-conda-v0/{channel}/{pypi-normalized-name}.json` where the channel is the name of the channel and the `{pypi-normalized-name}` is the normalized name of the package on PyPI.
   E.g for `requests` we can use `https://conda-mapping.prefix.dev/pypi-to-conda-v0/conda-forge/requests.json`, which will give you the corresponding json.
   There is

## Infrastructure and Storage Architecture

### Storage Locations

Parselmouth uses two primary storage locations:

#### 1. R2 Bucket (Cloud Storage)
The main package mapping data is stored in Cloudflare R2 (S3-compatible storage), configured via the `R2_PREFIX_BUCKET` environment variable. The bucket contains:

**Hash-based Mappings (v0):**
- `hash-v0/{channel}/index.json` - Channel-specific index containing all package hashes
- `hash-v0/{package_sha256}` - Individual mapping entries keyed by conda package SHA256 hash

**Relations Tables (v1):**
- `relations-v1/{channel}/relations.jsonl.gz` - Master relations table (JSONL format, gzipped)
- `relations-v1/{channel}/metadata.json` - Metadata about the relations table
- `pypi-to-conda-v1/{channel}/{pypi_name}.json` - Fast PyPI lookup files derived from relations table

#### 2. Git Repository Files
The `files/` directory in the repository stores compressed mappings that are committed to version control:

- `files/mapping_as_grayskull.json` - Legacy mapping format for Grayskull compatibility
- `files/compressed_mapping.json` - Compressed mapping (legacy format)
- `files/v0/{channel}/compressed_mapping.json` - Channel-specific compressed mappings (conda-forge, pytorch, bioconda)

### Version System

Parselmouth uses a versioned approach to support multiple data formats:

**v0 (Current Hash-based System):**
- Uses conda package SHA256 hashes as keys
- Direct lookup: `hash-v0/{sha256}` returns a single mapping entry
- Optimized for conda → PyPI lookups
- Both old and new workflows write to this path

**v1 (Relations System - New):**
- Stores package relationships in a normalized table format
- Enables PyPI → conda lookups and dependency analysis
- Three-tier structure:
  1. Master relations table (source of truth)
  2. Metadata (statistics, generation timestamp)
  3. Derived lookup files (cached for performance)
- Only new workflows with `update_relations_table` job write to this path

### Workflow Pipeline Architecture

The GitHub Actions workflows are organized into stages:

1. **Producer Stage** (`generate_hash_letters`):
   - Identifies missing packages by comparing upstream channel repodata with existing index
   - Outputs a matrix of `subdir@letter` combinations to process in parallel

2. **Updater Stage** (`updater_of_records`):
   - Runs in parallel for each `subdir@letter` combination
   - Downloads artifact metadata and extracts PyPI mappings
   - Uploads individual package mappings to `hash-v0/{sha256}`

3. **Merger Stage** (`updater_of_index`):
   - Combines all partial indices into a master index
   - Uploads consolidated index to `hash-v0/{channel}/index.json`

4. **Relations Generation Stage** (`update_relations_table`) - **NEW**:
   - Runs after the merger stage completes
   - Reads the updated index and generates relations table
   - Uploads to `relations-v1/{channel}/` paths
   - Only present in new workflows with relations support

5. **Commit Stage** (`update_file`):
   - Updates local git repository files
   - Runs mapping transformations (`update-mapping-legacy`, `update-mapping`)
   - Commits compressed mappings to version control

### Bucket Isolation and Safety

The new workflows with relations support **do NOT overwrite or interfere with old data**:

- **Same bucket, different prefixes**: Both old and new workflows use `R2_PREFIX_BUCKET`, but write to isolated path prefixes
- **v0 paths**: Both systems continue to write hash-based mappings (backward compatible)
- **v1 paths**: Only new workflows write relations data (additive, no conflicts)
- **No destructive operations**: New workflows add functionality without removing or replacing existing data

This architecture allows for:
- Zero-downtime deployment of relations features
- Gradual migration from v0 to v1 APIs
- Rollback capability if issues arise
- Parallel operation of both systems during transition

## Thanks!

Developed with ❤️ at [prefix.dev](https://prefix.dev).
