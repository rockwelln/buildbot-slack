from setuptools import setup

import buildbot_slack

with open("README.md", "r") as f:
    long_description = f.read()


setup(
    name="buildbot-slack",
    version=buildbot_slack.__version__,
    description="buildbot plugin for integration with Slack.",
    author="Norman Denayer",
    author_email="denayer.norman@gmail.com",
    url="https://github.com/rockwelln/buildbot-slack",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=["buildbot_slack"],
    requires=["buildbot (>=2.0.0)", "treq (>=18.6)"],
    entry_points={
        "buildbot.reporters": [
            "SlackStatusPush = buildbot_slack.reporter:SlackStatusPush"
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Plugins",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Topic :: Software Development :: Build Tools",
    ],
)
