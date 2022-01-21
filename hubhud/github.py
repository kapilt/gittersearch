"""Extract github events data for a project from clickhouse
https://ghe.clickhouse.tech
"""
from dataclasses import dataclass, field, fields
from datetime import datetime
import difflib
from enum import Enum
import logging

from clickhouse_driver import Client
import sqlalchemy as rdb

from .schema import mapper_registry, F, Array


log = logging.getLogger("hubhud.github")


class EventType(Enum):
    # col: event_type
    CommitCommentEvent = 1
    CreateEvent = 2
    DeleteEvent = 3
    ForkEvent = 4
    GollumEvent = 5
    IssueCommentEvent = 6
    IssuesEvent = 7
    MemberEvent = 8
    PublicEvent = 9
    PullRequestEvent = 10
    PullRequestReviewCommentEvent = 11
    PushEvent = 12
    ReleaseEvent = 13
    SponsorshipEvent = 14
    WatchEVent = 15
    GistEvent = 16
    FollowEvent = 17
    DownloadEvent = 18
    PullRequestReviewEvent = 19
    ForkApplyEvent = 20
    Event = 21
    TeamAddEvent = 22


class ActionType(Enum):
    # col: action
    none = 0
    created = 1
    added = 2
    edited = 3
    deleted = 4
    opened = 5
    closed = 6
    reopened = 7
    assigned = 8
    unassigned = 9
    labeled = 10
    unlabled = 11
    review_requested = 12
    review_request_removed = 13
    synchronize = 14
    started = 15
    published = 16
    update = 17
    create = 18
    fork = 19
    merged = 20


class RefType(Enum):
    # col: ref_type
    none = 0
    branch = 1
    tag = 2
    repository = 3
    unknown = 4


class StateType(Enum):
    # col: state
    none = 0
    open = 1
    closed = 2


class AuthorAssociationType(Enum):
    # col: author_association
    NONE = 0
    CONTRIBUTOR = 1
    OWNER = 2
    COLLABORATOR = 2
    MEMBER = 4
    MANNEQUIN = 5


class MergeableState(Enum):
    # col: mergeable_state
    unknown = 0
    dirty = 1
    clean = 2
    unstable = 3
    draft = 4


class ReviewType(Enum):
    # col: review_state
    none = 0
    approved = 1
    changes_requested = 2
    commented = 3
    dismissed = 4
    pending = 5


@mapper_registry.mapped
@dataclass
class GithubEvent:
    __tablename__ = "github_event"
    __sa_dataclass_metadata_key__ = "sa"

    id: int = field(
        init=False,
        metadata={
            "sa": rdb.Column(
                rdb.Integer, rdb.Identity(start=1, cycle=True), primary_key=True
            )
        },
    )
    file_time: datetime = F(rdb.DateTime)
    event_type: str = F(rdb.String(30))  # todo enum
    actor_login: str = F(rdb.String(64))
    repo_name: str = F(rdb.String(256))
    created_at: datetime = F(rdb.DateTime)
    updated_at: datetime = F(rdb.DateTime)
    action: str = F(rdb.String(32))  # todo enum
    comment_id: int = F(rdb.BigInteger)
    body: str = F(rdb.String)
    path: str = F(rdb.String)
    position: str = F(rdb.Integer)
    line: str = F(rdb.Integer)
    ref: str = F(rdb.String)
    ref_type: str = F(rdb.String)  # todo enum
    creator_user_login: str = F(rdb.String)
    number: str = F(rdb.Integer)  # todo small int
    title: str = F(rdb.String)
    labels: list[str] = F(Array(rdb.String))
    state: str = F(rdb.String)  # todo enum
    locked: int = F(rdb.Integer)  # bool?
    assignee: str = F(rdb.String)
    assignees: list[str] = F(Array(rdb.String))
    comments: int = F(rdb.Integer)
    author_association: str = F(rdb.String)  # todo enum
    closed_at: datetime = F(rdb.DateTime)
    merged_at: datetime = F(rdb.DateTime)
    merge_commit_sha: str = F(rdb.String)
    requested_reviewers: F(Array(rdb.String), None)  # x
    requested_teams: F(Array(rdb.String), None)  # x
    head_ref: F(rdb.String, None)  # x
    head_sha: F(rdb.String, None)  # x
    base_ref: F(rdb.String, None)  # x
    base_sha: F(rdb.String, None)  # x
    merged: F(rdb.SmallInteger, None)  # bool
    mergeable: F(rdb.SmallInteger, None)  # bool
    rebaseable: F(rdb.SmallInteger, None)  # bool
    mergeable_state: F(rdb.String, None)  # todo enum
    merged_by: F(rdb.String, None)
    review_comments: F(rdb.SmallInteger, None)
    maintainer_can_modify: F(rdb.SmallInteger, None)  # bool?
    commits: F(rdb.SmallInteger, None)
    additions: F(rdb.SmallInteger, None)
    deletions: F(rdb.SmallInteger, None)
    changed_files: F(rdb.SmallInteger, None)
    diff_hunk: F(rdb.String, None)
    original_position: F(rdb.String, None)
    commit_id: F(rdb.String, None)
    original_commit_id: F(rdb.String, None)
    push_size: F(rdb.SmallInteger, None)
    push_distinct_size: F(rdb.SmallInteger, None)
    member_login: F(rdb.String, None)
    release_tag_name: F(rdb.String, None)
    release_name: F(rdb.String, None)
    review_state: F(rdb.String, None)  # todo enum


def get_events(project, start=None, end=None, limit=0, direction=""):
    client = get_client()
    query = """
    select *
    from github_events
    where repo_name = %(project)s
    """
    if start:
        query += " and created_at > %(start)s"
    if end:
        query += " and created_at < %(end)s"

    assert direction in ("desc", "asc", "")
    query += " order by created_at %s" % direction

    if limit:
        query += " limit %(limit)s"

    params = {
        "start": start,
        "end": end,
        "limit": limit,
        "project": project,
    }

    block_size = 10000
    results_iter = client.execute_iter(
        query, params, settings={"block_size": block_size}, with_column_types=True
    )
    schema = next(results_iter)
    snames = check_schema_diff(GithubEvent, schema)

    for r in results_iter:
        # convert to dict, because we reorder to handle null fields coming back from db.
        yield GithubEvent(**dict(zip(snames, r)))


def check_schema_diff(klass, schema):
    snames = [s[0] for s in schema]
    knames = [f.name for f in fields(klass) if f.name != "id"]

    if snames == knames:
        return snames

    raise AssertionError(
        "Schema Delta: \n%s" % ("\n".join(difflib.context_diff(knames, snames)))
    )


def get_client():
    return Client(
        secure=True,
        user="explorer",
        host="gh-api.clickhouse.tech",
    )


def sync(session, project: str, rename: str):
    last = (
        session.query(GithubEvent)
        .order_by(rdb.desc(GithubEvent.created_at))
        .limit(1)
        .one_or_none()
    )
    params = {}
    if last:
        params["start"] = last.created_at
    count = 0
    for e in get_events(project, **params):
        if rename:
            e.repo_name = rename
        session.add(e)
        count += 1
        if count % 1000 == 0:
            log.info("added %d events for %s", count, project)
    session.commit()
    return count
