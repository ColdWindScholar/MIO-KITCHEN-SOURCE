from setuptools import setup, Extension

mio_core_module = Extension(
    'mio_core',
    sources=['core.c'],
)

setup(
    name='mio_core',
    version='1.0',
    description='C Core For Mio-Kitchen/TIK5.',
    ext_modules=[mio_core_module],
)