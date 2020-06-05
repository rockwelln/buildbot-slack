[![PyPI version](https://badge.fury.io/py/buildbot-slack.svg)](https://badge.fury.io/py/buildbot-slack)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Buildbot plugin to publish status on Slack
==========================================

This Buildbot plugin sends messages to a Slack channel when each build starts / finishes with a handy link to the build results.

This plugin is based on many other reporter plugins made for Slack

Contributions are welcome!

## Install

### via pip

```
pip install buildbot-slack
```

## Setup

Create a new incoming webhook in your slack account. (see https://api.slack.com/tutorials/slack-apps-hello-world)

Then in your master.cfg, add the following:

```
from buildbot.plugins import reporters
c['services'].append(reporters.SlackStatusPush(
    endpoint=<YOUR_WEBHOOK_ENDPOINT>,
))
```

### Additional Options:
```
  channel = None
  username = None
  attachments = True
```

Have fun!
