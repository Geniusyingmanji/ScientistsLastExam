"""Single-attempt model client with both per-run and campaign receipts."""
from .microecology.agent import AuditedWorldClient
from .microecology.protocol import digest


class CampaignClient(AuditedWorldClient):
    def __init__(self, config, directory, ledger, episode, *, max_attempts=16, active_limit=8, rpm=60):
        super().__init__(config, directory, max_attempts=max_attempts)
        self.campaign_ledger, self.episode = ledger, episode
        self.active_limit, self.rpm = active_limit, rpm

    def _request_once(self, url, payload, headers, *, stream):
        if self._attempts >= self._max_attempts:
            raise RuntimeError("episode attempt budget exhausted")
        attempt = self.campaign_ledger.reserve(self.episode, digest(payload), active_limit=self.active_limit, rpm=self.rpm,
                                               wait_seconds=min(60, self.config.timeout_seconds))
        try:
            result = super()._request_once(url, payload, headers, stream=stream)
        except BaseException as exc:
            self.campaign_ledger.finish(attempt, "failed" if isinstance(exc, Exception) else "interrupted",
                                        {"exception_type": type(exc).__name__, "diagnostic": self.last_transport_error})
            raise
        self.campaign_ledger.finish(attempt, "returned", self.last_response_metadata)
        return result
