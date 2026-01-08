from typing import Annotated

# Type aliases for common PyPI types
type PyPIName = Annotated[str, "Name of the package on PyPi"]
type PyPIVersion = Annotated[str, "Version of the package on PyPi"]
type CondaVersion = Annotated[str, "Version of the package on Conda"]
type CondaPackageName = Annotated[str, "Name of the package on Conda"]
type CondaFileName = Annotated[
    str, "File name of the package on Conda, e.g boltons-21.0.0-py310h06a4308_0.conda"
]
type PyPISourceUrl = Annotated[str, "Url of the package when its not on a PyPI index"]
