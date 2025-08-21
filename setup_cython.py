"""
Cython build setup for ERP Platform
"""

import os
import numpy
from setuptools import setup, Extension
from Cython.Build import cythonize
from Cython.Compiler import Options

# Enable profiling for Cython code (for development)
Options.docstrings = True
Options.emit_code_comments = True

# Define Cython extensions
extensions = [
    # CSV Processor
    Extension(
        "erp_platform.cython_modules.csv_processor_cy",
        ["src/erp_platform/cython_modules/csv_processor_cy.pyx"],
        include_dirs=[numpy.get_include()],
        extra_compile_args=["-O3", "-march=native", "-ffast-math"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    
    # JSON Processor
    Extension(
        "erp_platform.cython_modules.json_processor_cy",
        ["src/erp_platform/cython_modules/json_processor_cy.pyx"],
        include_dirs=[numpy.get_include()],
        extra_compile_args=["-O3", "-march=native"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    
    # SAP Data Transformer
    Extension(
        "erp_platform.cython_modules.sap_transformer_cy",
        ["src/erp_platform/cython_modules/sap_transformer_cy.pyx"],
        include_dirs=[numpy.get_include()],
        extra_compile_args=["-O3", "-march=native", "-ffast-math"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    
    # Math Utils
    Extension(
        "erp_platform.cython_modules.math_utils_cy",
        ["src/erp_platform/cython_modules/math_utils_cy.pyx"],
        include_dirs=[numpy.get_include()],
        extra_compile_args=["-O3", "-march=native", "-ffast-math", "-fopenmp"],
        extra_link_args=["-fopenmp"],
        define_macros=[("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")],
    ),
    
    # String Utilities
    Extension(
        "erp_platform.cython_modules.string_utils_cy",
        ["src/erp_platform/cython_modules/string_utils_cy.pyx"],
        extra_compile_args=["-O3", "-march=native"],
    ),
]

# Cython compiler directives
compiler_directives = {
    "language_level": 3,
    "boundscheck": False,
    "wraparound": False,
    "initializedcheck": False,
    "cdivision": True,
    "embedsignature": True,
    "profile": True,  # Enable profiling during development
    "linetrace": True,  # Enable line tracing
}

if __name__ == "__main__":
    setup(
        ext_modules=cythonize(
            extensions,
            compiler_directives=compiler_directives,
            build_dir="build/cython",
            annotate=True,  # Generate HTML annotation files
        ),
        zip_safe=False,
    )