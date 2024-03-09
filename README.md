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

`parselmouth` is a utility designed to facilitate the mapping of Conda package names to their corresponding PyPI names. This tool automates the process of generating and updating mappings on an hourly basis, ensuring that users have access to the most accurate and up-to-date information.

Example of mapping for `numpy-1.26.4-py311h64a7726_0.conda` with sha256 `3f4365e11b28e244c95ba8579942b0802761ba7bb31c026f50d1a9ea9c728149`

```json
{
   "pypi_normalized_names":[
      "numpy"
   ],
   "versions":{
      "numpy":"1.26.4"
   },
   "conda_name":"numpy",
   "package_name":"numpy-1.26.4-py311h64a7726_0.conda",
   "direct_url":[
      "https://github.com/numpy/numpy/releases/download/v1.26.4/numpy-1.26.4.tar.gz"
   ]
}
```



Developed with ❤️ at [prefix.dev](https://prefix.dev).

