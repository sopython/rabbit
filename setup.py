from setuptools import setup

setup(
    name='rabbit',
    version='0.0.1',
    description='A chat assistant for Stack Overflow room owners',

    install_requires=[
        'bs4',
        'sqlalchemy',
        'autobahn',
        'requests',
        'websockets'
    ],

    packages=['rabbit'],

    entry_points=dict(
        console_scripts=[
            'rabbit_userscript=rabbit.userscript_server:main',
            'rabbit=rabbit.main:main',
        ]
    )
)
