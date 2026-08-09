from setuptools import setup, Extension

cpb_file_module = Extension(
    'cpb_file',
    sources=['cpbtool.c'],
)

setup(
    name='cpb_file',
    version='1.0',
    description='cpb_file helper',
    ext_modules=[cpb_file_module],
)