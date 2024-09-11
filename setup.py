from setuptools import setup, find_packages, Extension

# Requirements  for the package
with open('requirements.txt') as f:
    requirements = [
        # 'psycopg2-binary',
        # 'python-dotenv',
        # 'buelon==1.0.58',
        line.strip() for line in
        f.read().splitlines()
        if line.strip() != '' and not line.strip().startswith('#')
    ]

# Read the long description from the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cronevents",
    version="0.0.26",
    author="Daniel Olson",
    author_email="daniel@orphos.cloud",
    description="A package to run cron jobs(events)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(),
    package_name="cronevents",
    install_requires=requirements,
    # entry_points={
    #     'console_scripts': ['cevents=buelon.command_line:cli'],
    # },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    keywords="cron jobs",
)
