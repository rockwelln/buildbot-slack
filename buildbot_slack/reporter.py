# Based on the gitlab reporter from buildbot

from __future__ import absolute_import, print_function

from twisted.internet import defer

from buildbot.process.properties import Properties
from buildbot.process.results import statusToString
from buildbot.reporters import http, utils
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

logger = Logger()

DEFAULT_HOST = "https://hooks.slack.com"


class SlackStatusPush(http.HttpStatusPushBase):
    name = "SlackStatusPush"
    neededDetails = dict(wantProperties=True)

    def checkConfig(self, endpoint, channel=None, host_url=None, **kwargs):
        if not isinstance(endpoint, str):
            endpoint.error("endpoint must be a string")
        elif not endpoint.startswith("/"):
            endpoint.error('endpoint should start with "/"')
        if channel and not isinstance(channel, str):
            channel.error("channel must be a string")
        if host_url and not isinstance(host_url, str):
            host_url.error("host_url must be a string")

    @defer.inlineCallbacks
    def reconfigService(
        self, endpoint, channel=None, host_url=DEFAULT_HOST, verbose=False, **kwargs
    ):

        yield super().reconfigService(**kwargs)

        self.baseURL = host_url.rstrip("/")
        self.endpoint = endpoint
        self.channel = channel
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, self.baseURL, debug=self.debug, verify=self.verify
        )
        self.verbose = verbose
        self.project_ids = {}

    @defer.inlineCallbacks
    def getBuildDetailsAndSendMessage(self, build, key):
        yield utils.getDetailsForBuild(self.master, build, **self.neededDetails)
        text = yield self.getMessage(build, key)
        postData = {"text": text}
        extra_params = yield self.getExtraParams(build, key)
        postData.update(extra_params)
        return postData

    def getMessage(self, build, event_name):
        event_messages = {
            "new": "Buildbot started build %s here: %s"
            % (build["builder"]["name"], build["url"]),
            "finished": "Buildbot finished build %s with result %s here: %s"
            % (
                build["builder"]["name"],
                statusToString(build["results"]),
                build["url"],
            ),
        }
        return event_messages.get(event_name, "")

    # returns a Deferred that returns None
    def buildStarted(self, key, build):
        return self.send(build, key[2])

    # returns a Deferred that returns None
    def buildFinished(self, key, build):
        return self.send(build, key[2])

    def getExtraParams(self, build, event_name):
        return {}

    @defer.inlineCallbacks
    def send(self, build, key):
        postData = yield self.getBuildDetailsAndSendMessage(build, key)
        if not postData:
            return

        props = Properties.fromDict(build["properties"])
        props.master = self.master

        sourcestamps = build["buildset"]["sourcestamps"]

        for sourcestamp in sourcestamps:
            sha = sourcestamp["revision"]
            if sha is None:
                # No special revision for this, so ignore it
                continue

            logger.info("posting to {url}", url=self.endpoint)
            try:
                response = yield self._http.post(self.endpoint, json=postData)
                if response.code != 200:
                    content = yield response.content()
                    logger.error(
                        "{code}: unable to upload status: {content}",
                        code=response.code,
                        content=content,
                    )
            except Exception as e:
                logger.error(
                    "Failed to send status for {repo} at {sha}: {error}",
                    repo=sourcestamp["repository"],
                    sha=sha,
                    error=e,
                )
