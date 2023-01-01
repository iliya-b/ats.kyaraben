#!/usr/bin/env python3

import ats.kyaraben

from setuptools import setup, find_packages

PROJECT = 'ats.kyaraben'

try:
    long_description = open('README.rst', 'rt').read()
except IOError:
    long_description = ''

setup(
    name=PROJECT,
    version=ats.kyaraben.version,

    description='Kyaraben, the cute orchestrator',
    long_description=long_description,

    author='Jenkins',
    author_email='jenkins@rnd.alterway.fr',

    install_requires=[
        'ats.client',

        # server
        'aiohttp',
        'aiohttp-debugtoolbar',
        'aioamqp',
        'aiopg',
        'oath',
        'structlog',
        'ats.util',
        'petname',

        # userful for debugging
        # 'python-openstackclient',
        # 'python-heatclient'
    ],

    extras_require={
        'docs': (
            'wheel',
            'sphinx',
            'sphinx_rtd_theme',
            'sphinxcontrib-httpdomain',
            'sphinxcontrib-programoutput',
        )},
    namespace_packages=['ats'],
    packages=find_packages(),
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'kyaraben = ats.kyaraben.client.app:main',
            'kyaraben-server = ats.kyaraben.server.main:main',
            'kyaraben-worker = ats.kyaraben.worker.main:main',
            'kyaraben-retry = ats.kyaraben.retry.main:main',
        ],
        # for Cliff
        'kyaraben': [
            'gateway android ports = ats.kyaraben.client.gateway:AndroidPorts',
            'android apk install = ats.kyaraben.client.android_apk:Install',
            'android apk list = ats.kyaraben.client.android_apk:List',
            'android command status = ats.kyaraben.client.android:CommandStatus',
            'android create = ats.kyaraben.client.android:Create',
            'android delete = ats.kyaraben.client.android:Delete',
            'android display-url = ats.kyaraben.client.android:DisplayURL',
            'android list = ats.kyaraben.client.android:List',
            'android monkey run = ats.kyaraben.client.android:Monkey',
            'android otp = ats.kyaraben.client.android:GetOTP',
            'android properties = ats.kyaraben.client.android:Properties',
            'android show = ats.kyaraben.client.android:Show',
            'android test list = ats.kyaraben.client.android:TestList',
            'android test run = ats.kyaraben.client.android:TestRun',
            'android update = ats.kyaraben.client.android:Update',
            'image list = ats.kyaraben.client.image:List',
            'project apk delete = ats.kyaraben.client.project_apk:Delete',
            'project apk list = ats.kyaraben.client.project_apk:List',
            'project apk show = ats.kyaraben.client.project_apk:Show',
            'project apk upload = ats.kyaraben.client.project_apk:Upload',
            'project camera delete = ats.kyaraben.client.camera:Delete',
            'project camera list = ats.kyaraben.client.camera:List',
            'project camera upload = ats.kyaraben.client.camera:Upload',
            'project campaign run = ats.kyaraben.client.campaign:Run',
            'project campaign list = ats.kyaraben.client.campaign:List',
            'project campaign show = ats.kyaraben.client.campaign:Show',
            'project campaign delete = ats.kyaraben.client.campaign:Delete',
            'project create = ats.kyaraben.client.project:Create',
            'project delete = ats.kyaraben.client.project:Delete',
            'project list = ats.kyaraben.client.project:List',
            'project show = ats.kyaraben.client.project:Show',
            'project testsource create = ats.kyaraben.client.testsource:Upload',
            'project testsource update = ats.kyaraben.client.testsource:Update',
            'project testsource compile = ats.kyaraben.client.testsource:Compile',
            'project testsource list = ats.kyaraben.client.testsource:List',
            'project testsource show = ats.kyaraben.client.testsource:Show',
            'project testsource delete = ats.kyaraben.client.testsource:Delete',
            'project testsource download = ats.kyaraben.client.testsource:Download',
            'project update = ats.kyaraben.client.project:Update',
            'user quota = ats.kyaraben.client.user:Quota',
            'user whoami = ats.kyaraben.client.user:Whoami',
        ]
    },

    setup_requires=[],
    tests_require=['pytest', 'asynctest'],

    zip_safe=False,
)
