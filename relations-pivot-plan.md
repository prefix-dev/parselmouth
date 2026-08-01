# Proposal: relation pivots for the conda to PyPI mapping data

This is a proposal for discussion, not a settled decision. The recommendations
below are open to feedback.

## 1. The problem with the current data

parselmouth maps conda packages to PyPI packages and publishes the result on
R2.

### The main lookup file is lossy

The per-package lookup is `pypi-to-conda-v1/{channel}/{pypi_name}.json`. It maps
a PyPI version to a single conda name, chosen by a Levenshtein best-match
heuristic:

```json
{
  "pypi_name": "addict",
  "conda_versions": { "2.2.1": "addict" }
}
```

It drops the conda version, the conda build, the conda subdir, the conda hash,
and every conda name except the best-match one.

### What that costs us

- **Version drift is invisible.** A conda recipe version and the PyPI version of
  the code inside it can differ. Measured against the relations table, this is
  2.27 percent of conda-forge relations and 4.39 percent of bioconda relations.
  Example: the conda `addict` 2.3.0 package contains Python metadata reporting
  version 2.2.1. We confirmed this by opening the artifact, so it is real
  upstream data, not an extraction bug. The current file only ever shows
  `2.2.1`.
- **Unmapped conda releases are invisible.** The file is keyed by PyPI version,
  so a conda release with no PyPI mapping does not appear at all.
- **Only one direction is published.** There is a PyPI-keyed lookup but no
  conda-keyed one. "What does conda package X map to across all its versions"
  is not served as a static artifact.

## 2. What this means for downstream users

### The web frontend

The frontend that browses the conda to PyPI mapping cannot show a version
history with both versions, cannot flag drift, and cannot show conda releases
that lack a PyPI counterpart.

### pixi

pixi consumes the PyPI name to conda name mapping to translate PyPI
dependencies into conda packages. The current `pypi-to-conda-v1` shape is
adequate for that.

This makes pixi a compatibility constraint rather than a consumer we need to
fix. The existing `pypi-to-conda-v1/{channel}/{pypi_name}.json` files should
keep working unchanged. Everything proposed below is additive.

## 3. Proposed change

### Shape: static per-name files

We propose publishing the data as static per-name JSON files on R2 behind the
CDN. Static files are read the same way by every consumer (pixi in Rust, the
browser, Python scripts): an exact-name HTTP lookup the CDN can cache.

### The artifacts

| Artifact | Status | Purpose |
|---|---|---|
| `hash-v0/{conda_hash}` | exists, unchanged | per-artifact ground truth, also the per-hash form |
| `relations-v1/{channel}/relations.jsonl.gz` | exists, unchanged | bulk table: regeneration source and offline analysis |
| `relations-by-conda-v1/{channel}/{conda_name}.json` | new | conda-keyed pivot |
| `relations-by-pypi-v1/{channel}/{pypi_name}.json` | new | PyPI-keyed pivot |
| `names-v1/{channel}/index.json` | new (replaces the git-committed mapping) | name index plus bulk name-level mapping |

Today the name-level data is the git-committed `compressed_mapping.json`, served
from `raw.githubusercontent.com`. We propose publishing it to R2 instead, so
external consumers use one base URL and one CORS configuration instead of two
origins.

### The names index

The names index serves two use cases from one file: enumeration (which conda
and PyPI names exist, for autocomplete and discovery) and the bulk name-level
mapping (conda name to PyPI name, with no per-version detail).

```json
{
  "schema_version": "1",
  "channel": "conda-forge",
  "conda_names": ["...sorted, mapped and unmapped..."],
  "pypi_names": ["...sorted distinct..."],
  "mapping": { "numpy": ["numpy"], "7za": null, "addict": ["addict"] }
}
```

- `conda_names` and `pypi_names` are pre-sorted, so a consumer reads either side
  the same way with no client-side work.
- `mapping` is the bulk conda to PyPI name mapping. A `null` value means the
  conda package has no PyPI mapping, so mapped versus conda-only is one filter
  on `mapping`.
- Names appear both in an array and in `mapping`. The redundancy is small and
  gzip absorbs most of it, since they are the same repeated strings.

This index is name-level only. It is not redundant with the pivots, which carry
per-version detail. A consumer uses the index for autocomplete and a quick
name-level answer, and a pivot only when it needs versions.

### Pivot file layout

A pivot carries the full row, not a reduction. It only changes which name sits
at the top of the file.

```jsonc
// relations-by-conda-v1/conda-forge/addict.json
{
  "schema_version": "1",
  "channel": "conda-forge",
  "conda_name": "addict",
  "pypi_packages": [
    {
      "pypi_name": "addict",        // null for the unmapped group
      "levenshtein": 0,             // distance to "addict"; groups sort by this
      "rows": [
        { "conda_version": "2.3.0", "conda_build": "py36h9f0ad1d_0",
          "conda_subdir": "linux-64", "conda_hash": "abc123",
          "pypi_version": "2.2.1", "direct_url": null }
      ]
    }
  ]
}
```

`relations-by-pypi-v1/{channel}/{pypi_name}.json` has the same shape with the
keys swapped: `pypi_name` at the top, a `conda_packages` list, `conda_name`
inside each group.

### Design points

- The conda pivot is built from the v0 index, not the relations table, so conda
  artifacts with no PyPI mapping still appear, in a group with `pypi_name` set
  to null. That is how unmapped releases become visible.
- `conda_hash` is the row identity and the link to ground truth. Any row can be
  verified with one fetch of `hash-v0/{conda_hash}`, which is immutable.
- Each pivot groups by the other side's name, ordered by Levenshtein distance to
  the file's key name, closest first. The distance is stored as `levenshtein`
  because the heuristic is wrong for renamed packages (conda `pytorch` to PyPI
  `torch` is distance 2), and a consumer should be able to see and override it.
  Ties break alphabetically so files are byte-stable, which the incremental
  upload step relies on.
- `pypi_version` is null when a mapping exists but the version could not be
  read (the `0.0.0` and `0+unknown` sentinels normalize to null).

### Questions this would answer

| Question | Why you would ask it | How the data answers it |
|---|---|---|
| Which conda packages does PyPI `requests` map to | You have a PyPI dependency and need the conda equivalent | One fetch of `relations-by-pypi-v1/.../requests.json` |
| Which PyPI package does conda `flask` map to | Identify a conda package's PyPI identity | One fetch of `relations-by-conda-v1/.../flask.json` |
| Does conda `gcloud` vendor packages | Vendored copies cause hidden duplicate installs | Conda pivot for `gcloud`: find one `conda_hash` under two `pypi_name` groups |
| Is there version drift for package X | If conda and PyPI versions differ, a tool cannot assume they match | Either pivot: compare `conda_version` and `pypi_version` per row |
| Which conda or PyPI names are mapped | Autocomplete and discovery | The names index |
| Was PyPI `flask` vendored then removed for conda package X | Track when a bundled copy appeared or disappeared | Conda pivot for X: see which `conda_version` rows include a `flask` row |

### Caveat: build-level divergence

Builds of the same conda version can disagree, for example a rebuild that
removes an accidentally vendored package. Rows are per hash, so this is
represented in the data. A consumer that collapses to version level should flag
a version where builds differ rather than silently pick one.

### Caveat: the PyPI side is not exhaustive

The conda side is complete. The pivots are built from the conda channel index,
so every conda package appears, including ones with no PyPI mapping.

The PyPI side is not. parselmouth only sees a PyPI package when it is found
inside a conda artifact, and it has no list of all PyPI packages to compare
against. A PyPI release that was never packaged for conda is simply absent from
the data.

So unmapped conda packages can be listed directly, but unmapped PyPI packages
can only be found by exclusion: take a full PyPI package list and subtract the
names this data knows. Absence of a PyPI name here means "not observed in any
conda package", not "confirmed to have no conda mapping".

## 4. Options considered and set aside

Recorded here so they can be revisited if the requirements change.

### A query API on Cloudflare D1

A SQLite database at the edge with a Worker in front would allow arbitrary query
shapes from one dataset. It is a server, so it adds a network round trip per
query, which is poor for a pixi solve loop, and keeping it in sync with the
hourly regeneration needs care. Static files serve every consumer with no
server. D1 would be worth revisiting if unbounded analytical queries become a
requirement.

### A prebuilt SQLite file queried over HTTP range requests

Every language can read SQLite, and the browser can range-read pages with a
WASM build. The browser path adds significant WASM weight, and native consumers
re-downloading a large database on each refresh is awkward. For exact-name
lookup, static per-name files are simpler.

### Normalized id lists

Storing only row ids in the pivots with a separate id-to-row store would remove
the duplication, but it reintroduces an N+1 fetch pattern: rendering one package
would need one request per row. Keeping full rows in each pivot stores rows
twice, which is cheap on R2, and keeps the access pattern at one fetch per
question.
