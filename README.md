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

## Thanks!

Developed with ❤️ at [prefix.dev](https://prefix.dev).
