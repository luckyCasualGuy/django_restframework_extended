from setuptools import setup, find_packages

VERSION = '0.0.3'
DESCRIPTION = 'Django Rest Framework Extended Functionalities'
LONG_DESCRIPTION = 'This package is very opinionated'

setup(
    name="django_restframework_extended",
    version=VERSION,
    author="Manan Lad",
    author_email="luckycasualguy@gmail.com",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=find_packages(),
    install_requires=[],
    keywords=['python', 'django', 'restframework', 'extended', 'cerberus'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
    ]
)