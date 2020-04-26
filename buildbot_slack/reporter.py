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
DEFAULT_HOST = "https://hooks.slack.com"  # deprecated


class SlackStatusPush(http.HttpStatusPushBase):
    name = "SlackStatusPush"
    neededDetails = dict(wantProperties=True)

    def checkConfig(
        self, endpoint, channel=None, host_url=None, username=None, **kwargs
    ):
        if not isinstance(endpoint, str):
            logger.warning(
                "[SlackStatusPush] endpoint should be a string, got '%s' instead",
                type(endpoint).__name__,
            )
        elif not endpoint.startswith("http"):
            logger.warning(
                '[SlackStatusPush] endpoint should start with "http...", endpoint: %s',
                endpoint,
            )
        if channel and not isinstance(channel, str):
            logger.warning(
                "[SlackStatusPush] channel must be a string, got '%s' instead",
                type(channel).__name__,
            )
        if username and not isinstance(username, str):
            logger.warning(
                "[SlackStatusPush] username must be a string, got '%s' instead",
                type(username).__name__,
            )
        if host_url and not isinstance(host_url, str):  # deprecated
            logger.warning(
                "[SlackStatusPush] host_url must be a string, got '%s' instead",
                type(host_url).__name__,
            )
        elif host_url:
            logger.warning(
                "[SlackStatusPush] argument host_url is deprecated and will be removed in the next release: specify the full url as endpoint"
            )

    @defer.inlineCallbacks
    def reconfigService(
        self,
        endpoint,
        channel=None,
        host_url=None,  # deprecated
        username=None,
        attachments=True,
        verbose=False,
        **kwargs
    ):

        yield super().reconfigService(**kwargs)

        self.baseUrl = host_url and host_url.rstrip("/")  # deprecated
        if host_url:
            logger.warning(
                "[SlackStatusPush] argument host_url is deprecated and will be removed in the next release: specify the full url as endpoint"
            )
        self.endpoint = endpoint
        self.channel = channel
        self.username = username
        self.attachments = attachments
        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master,
            self.baseUrl or self.endpoint,
            debug=self.debug,
            verify=self.verify,
        )
        self.verbose = verbose
        self.project_ids = {}

    @defer.inlineCallbacks
    def getAttachments(self, build, key):
        sourcestamps = build["buildset"]["sourcestamps"]
        attachments = []

        for sourcestamp in sourcestamps:
            sha = sourcestamp["revision"]

            title = "Build #{buildid}".format(buildid=build["buildid"])
            project = sourcestamp["project"]
            if project:
                title += " for {project} {sha}".format(project=project, sha=sha)
            sub_build = bool(build["buildset"]["parent_buildid"])
            if sub_build:
                title += " {relationship}: #{parent_build_id}".format(
                    relationship=build["buildset"]["parent_relationship"],
                    parent_build_id=build["buildset"]["parent_buildid"],
                )

            fields = []
            if not sub_build:
                branch_name = sourcestamp["branch"]
                if branch_name:
                    fields.append(
                        {"title": "Branch", "value": branch_name, "short": True}
                    )
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
        postData = {}
        if self.attachments:
            attachments = yield self.getAttachments(build, key)
            if attachments:
                postData["attachments"] = attachments
        else:
            text += " here: " + build["url"]
        postData["text"] = text

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
                logger.info("no special revision for this")

            logger.info("posting to {url}", url=self.endpoint)
            try:
                if self.baseUrl:
                    # deprecated
                    response = yield self._http.post(self.endpoint, json=postData)
                else:
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
