import sys

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

setup(
    ext_modules=[
        Pybind11Extension(
            "planmargin._geometry",
            ["cpp/interaction_metrics.cpp"],
            cxx_std=20,
            extra_compile_args=(
                [] if sys.platform == "win32" else ["-Wall", "-Wextra", "-Wpedantic"]
            ),
        )
    ],
    cmdclass={"build_ext": build_ext},
)
