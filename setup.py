from distutils.core import setup


setup(
    name="vtmenu",
    version="1.0.0",
    description="VT-100 Launcher Menu",
    author="DragonMinded",
    license="Public Domain",
    packages=[
        "menu",
    ],
    install_requires=[
        req for req in open("requirements.txt").read().split("\n") if len(req) > 0
    ],
    python_requires=">3.8",
    entry_points={
        "console_scripts": [
            "vtmenu = menu.__main__:cli",
        ],
    },
)
