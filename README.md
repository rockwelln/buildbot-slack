Buildbot plugin to publish status on Slack
==========================================

This Buildbot plugin sends messages to a Slack channel when each build finishes with a handy link to the build results.

This plugin is based on many other reporter plugins made for Slack ; Contributions are welcome!

## Install

### via pip

```
pip install buildbot-slack
```

## Setup

Create a new incoming webhook in your slack account. (see https://api.slack.com/tutorials/slack-apps-hello-world)

Then in your master.cfg, add the following:

```
c['services'].append(reporters.SlackStatusPush(
    endpoint="/services/<YOUR_WEBHOOK_ENDPOINT>",
))
```

### Additional Options:
```
  channel = None
  host_url = "https://hooks.slack.com"
```

Have fun!
