# Based on the gitlab reporter from buildbot

from __future__ import absolute_import, print_function

from twisted.internet import defer

from buildbot.process.properties import Properties
from buildbot.process.results import statusToString
from buildbot.reporters import http, utils
from buildbot.util import httpclientservice
from buildbot.util.logger import Logger

logger = Logger()

STATUS_EMOJIS = {
    "success": ":sunglassses:",
    "warnings": ":meow_wow:",
    "failure": ":skull:",
    "skipped": ":slam:",
    "exception": ":skull:",
    "retry": ":facepalm:",
    "cancelled": ":slam:",
}
STATUS_COLORS = {
    "success": "#36a64f",
    "warnings": "#fc8c03",
    "failure": "#fc0303",
    "skipped": "#fc8c03",
    "exception": "#fc0303",
    "retry": "#fc8c03",
    "cancelled": "#fc8c03",
}


class SlackStatusPush(http.HttpStatusPushBase):
    name = "SlackStatusPush"
    neededDetails = dict(wantProperties=True)

    def checkConfig(self, endpoint, channel=None, username=None, **kwargs):
        if not isinstance(endpoint, str):
            endpoint.error("endpoint must be a string")
        elif not endpoint.startswith("http"):
            endpoint.error('endpoint should start with "http..."')
        if channel and not isinstance(channel, str):
            channel.error("channel must be a string")
        if username and not isinstance(username, str):
            username.error("username must be a string")

    @defer.inlineCallbacks
    def reconfigService(
        self, endpoint, channel=None, username=None, verbose=False, **kwargs
    ):

        yield super().reconfigService(**kwargs)

        self.endpoint = endpoint
        self.channel = channel
        self.username = username
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, self.endpoint, debug=self.debug, verify=self.verify
        )
        self.verbose = verbose
        self.project_ids = {}

    @defer.inlineCallbacks
    def getAttachments(self, build, key):
        sourcestamps = build["buildset"]["sourcestamps"]
        attachments = []

        for sourcestamp in sourcestamps:
            sha = sourcestamp["revision"]
            if sha is None:
                # No special revision for this, so ignore it
                continue
            title = "Build #{buildid}".format(buildid=build["buildid"])
            project = sourcestamp["project"]
            if project:
                title += " for {project} {sha}".format(project=project, sha=sha)

            fields = []
            branch_name = sourcestamp["branch"]
            if branch_name:
                fields.append({"title": "Branch", "value": branch_name, "short": True})
            repositories = sourcestamp["repository"]
            if repositories:
                fields.append(
                    {"title": "Repository", "value": repositories, "short": True}
                )
            responsible_users = yield utils.getResponsibleUsersForBuild(
                self.master, build["buildid"]
            )
            if responsible_users:
                fields.append(
                    {
                        "title": "Commiters",
                        "value": ", ".join(responsible_users),
                        "short": True,
                    }
                )
            attachments.append(
                {
                    "title": title,
                    "title_link": build["url"],
                    "fallback": "{}: <{}>".format(title, build["url"]),
                    "text": "Status: *{status}*".format(
                        status=statusToString(build["results"])
                    ),
                    "color": STATUS_COLORS.get(statusToString(build["results"]), ""),
                    "mrkdwn_in": ["text", "title", "fallback"],
                    "fields": fields,
                }
            )
        return attachments

    @defer.inlineCallbacks
    def getBuildDetailsAndSendMessage(self, build, key):
        yield utils.getDetailsForBuild(self.master, build, **self.neededDetails)
        text = yield self.getMessage(build, key)
        postData = {"text": text}
        attachments = yield self.getAttachments(build, key)
        if attachments:
            postData["attachments"] = attachments
        if self.channel:
            postData["channel"] = self.channel

        postData["icon_emoji"] = STATUS_EMOJIS.get(
            statusToString(build["results"]), ":facepalm:"
        )
        extra_params = yield self.getExtraParams(build, key)
        postData.update(extra_params)
        return postData

    def getMessage(self, build, event_name):
        event_messages = {
            "new": "Buildbot started build %s" % build["builder"]["name"],
            "finished": "Buildbot finished build %s with result: %s"
            % (build["builder"]["name"], statusToString(build["results"])),
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

        sourcestamps = build["buildset"]["sourcestamps"]

        for sourcestamp in sourcestamps:
            sha = sourcestamp["revision"]
            if sha is None:
                # No special revision for this, so ignore it
                continue

            logger.info("posting to {url}", url=self.endpoint)
            try:
                response = yield self._http.post("", json=postData)
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
