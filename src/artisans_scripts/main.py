import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

import attrs
import httpx
from prompt_toolkit import prompt

_LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
_HANDLER = logging.StreamHandler(stream=sys.stderr)
_HANDLER.setLevel(_LOGLEVEL)
_FORMATTER = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
_HANDLER.setFormatter(_FORMATTER)
logging.basicConfig(level=_LOGLEVEL, handlers=[_HANDLER])
LOGGER = logging.getLogger(__name__)


# get all coworkers with TariffId != null and Archived == false
# tool testedness is stored in team IDs


@attrs.frozen(kw_only=True)
class NexudusBearerToken:
    access_token: str = attrs.field(repr=lambda _value: "****")
    refresh_token: str = attrs.field(repr=lambda _value: "****")
    expires_in_ms: int
    issued_at: datetime = attrs.field(repr=lambda value: value.isoformat())
    expires_at: datetime = attrs.field(repr=lambda value: value.isoformat())

    @classmethod
    def from_json(
        cls, response_json: Mapping[str, Any], now: Optional[datetime] = None
    ):
        current_time = now if now else datetime.now()
        expires_in_ms = response_json["expires_in"]
        expires_at = current_time + timedelta(milliseconds=expires_in_ms)

        return cls(
            access_token=response_json["access_token"],
            refresh_token=response_json["refresh_token"],
            expires_in_ms=expires_in_ms,
            issued_at=current_time,
            expires_at=expires_at,
        )

    def as_headers(self) -> Mapping[str, str]:
        return {"authorization": f"Bearer {self.access_token}"}


# it looks like the bearer tokens last for 20 minutes, so I don't know if we'll
# ever actually need to refresh anything for these oneoff scripts
# def _refresh_bearer_token(old_token: NexudusBearerToken) -> NexudusBearerToken:
#     content = f"grant_type=refresh_token&refresh_token=f{old_token.refresh_token}"
#     response = (
#         httpx.post("https://spaces.nexudus.com/api/token", content=content)
#         .raise_for_status()
#         .json()
#     )

#     return NexudusBearerToken.from_json(response)


def main():
    LOGGER.info("I am running")
    login_email = prompt("what is your nexudus login email? ")
    password = prompt("what is your nexudus password? ", is_password=True)
    auth_request_body = (
        f"grant_type=password&username={login_email}&password={password}"
    )
    response = (
        httpx.post("https://spaces.nexudus.com/api/token", content=auth_request_body)
        .raise_for_status()
        .json()
    )

    nexudus_bearer_token = NexudusBearerToken.from_json(response)

    shopbot_team_id = int(os.environ.get("SHOPBOT_TEAM_ID") or "0")
    shopbot_team = (
        httpx.get(
            f"https://spaces.nexudus.com/api/spaces/teams/{shopbot_team_id}",
            headers=nexudus_bearer_token.as_headers(),
        )
        .raise_for_status()
        .json()
    )

    LOGGER.info(
        "your username is %s and your password is redacted :)",
        login_email,
        nexudus_bearer_token,
    )

    LOGGER.info("the shopbot user coworker IDs are %s", shopbot_team["CoworkerIDs"])


if __name__ == "__main__":
    main()
