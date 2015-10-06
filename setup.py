import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()

setup(
    name='score.css',
    version='0.1.1',
    description='Helpers for managing css with The SCORE Framework',
    long_description=README,
    author='strg.at',
    author_email='score@strg.at',
    url='http://score-framework.org',
    keywords='score framework web css sass',
    packages=['score.css'],
    install_requires=[
        'score.webassets >= 0.1',
        'score.tpl >= 0.1',
        'libsass >= 0.4',
    ],
    extras_require={
        'compression': [
            'csscompressor >= 0.9',
        ]
    },
)
