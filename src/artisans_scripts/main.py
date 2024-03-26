from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Any, Collection, Mapping, Optional

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
class NexudusCoworker:
    display_name: str
    coworker_id: int
    team_ids: Collection[int]
    email_address: str

    @classmethod
    def from_json(cls, response_json: Mapping[str, Any]) -> NexudusCoworker:
        team_ids_response_value = response_json["TeamIds"]
        team_ids: set[int] = (
            {int(team_id) for team_id in response_json["TeamIds"].split(",")}
            if team_ids_response_value
            else set()
        )
        return NexudusCoworker(
            display_name=response_json["FullName"],
            coworker_id=response_json["Id"],
            team_ids=team_ids,
            email_address=response_json["Email"],
        )


@attrs.frozen(kw_only=True)
class NexudusTeam:
    display_name: str
    team_id: int
    coworker_ids: Collection[int]  # this is sort of redundant


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


class NexudusBearerTokenManager:
    current_bearer_token: NexudusBearerToken

    def __init__(self, bearer_token: NexudusBearerToken) -> None:
        self.current_bearer_token = bearer_token

    def refresh_bearer_token(self) -> None:
        content = f"grant_type=refresh_token&refresh_token=f{self.current_bearer_token.refresh_token}"
        response = (
            httpx.post("https://spaces.nexudus.com/api/token", content=content)
            .raise_for_status()
            .json()
        )
        self.current_bearer_token = NexudusBearerToken.from_json(response)

    def as_request_headers(self) -> Mapping[str, str]:
        return {"authorization": f"Bearer {self.current_bearer_token.access_token}"}

    @classmethod
    def new_instance(cls):
        login_email = prompt("what is your nexudus login email? ")
        password = prompt("what is your nexudus password? ", is_password=True)
        auth_request_body = (
            f"grant_type=password&username={login_email}&password={password}"
        )
        response = (
            httpx.post(
                "https://spaces.nexudus.com/api/token", content=auth_request_body
            )
            .raise_for_status()
            .json()
        )

        return cls(NexudusBearerToken.from_json(response))


def get_all_coworkers(nexudus_bearer_token_manager: NexudusBearerTokenManager):
    query_parameters = {
        "page": 1,
        "size": 25,
        "orderBy": "Id",
        # n.b. the API docs say this field is supposed to be an int, but the nexudus
        # dashboard uses this same API endpoint with a _notnull_ value here
        "Coworker_Tariff": "notnull",
    }
    all_coworkers: list[NexudusCoworker] = []
    is_complete = False
    pages_fetched = 0
    max_pages = 5
    expected_records: Optional[int] = None
    while not is_complete:
        try:
            response = (
                httpx.get(
                    "https://spaces.nexudus.com/api/spaces/coworkers",
                    params=query_parameters,
                    headers=nexudus_bearer_token_manager.as_request_headers(),
                )
                .raise_for_status()
                .json()
            )

            current_page = response["CurrentPage"]
            total_pages = response["TotalPages"]
            has_next_page = response["HasNextPage"]
            if expected_records is None:
                expected_records = response["TotalItems"]
            pages_fetched += 1
            LOGGER.info(
                "we've fetched %s pages. we're on page %s of %s. We expect %s records",
                pages_fetched,
                current_page,
                total_pages,
                expected_records,
            )
            if pages_fetched >= max_pages or not has_next_page:
                is_complete = True
            else:
                #otherwise, advance the cursor
                query_parameters["page"] = current_page + 1
            current_page_coworkers = [
                NexudusCoworker.from_json(coworker) for coworker in response["Records"]
            ]
            all_coworkers += current_page_coworkers
        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.UNAUTHORIZED.value:
                nexudus_bearer_token_manager.refresh_bearer_token()
            else:
                raise e
    return all_coworkers


def main():
    nexudus_bearer_token_manager = NexudusBearerTokenManager.new_instance()

    # shopbot_team_id = int(os.environ.get("SHOPBOT_TEAM_ID") or "0")
    # shopbot_team = (
    #     httpx.get(
    #         f"https://spaces.nexudus.com/api/spaces/teams/{shopbot_team_id}",
    #         headers=nexudus_bearer_token_manager.as_request_headers(),
    #     )
    #     .raise_for_status()
    #     .json()
    # )

    all_coworkers = get_all_coworkers(nexudus_bearer_token_manager)
    # LOGGER.info("the shopbot user coworker IDs are %s", shopbot_team["CoworkerIDs"])


if __name__ == "__main__":
    main()
