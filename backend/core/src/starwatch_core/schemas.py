"""调度器与抓取器共用的 Pydantic 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from starwatch_core.constants import (
    ASSERTION_MAX_COUNT,
    COOKIE_MAX_COUNT,
    DEFAULT_LOAD_CONCURRENCY,
    DEFAULT_LOAD_REQUESTS,
    DEFAULT_TIMEOUT_SECONDS,
    DESCRIPTION_MAX_LENGTH,
    EXPECTED_MAX_LENGTH,
    EXPRESSION_MAX_LENGTH,
    EXTRACT_RULE_MAX_COUNT,
    FIELD_NAME_MAX_LENGTH,
    HEADER_MAX_COUNT,
    MAX_LOAD_CONCURRENCY,
    MAX_LOAD_DURATION_SECONDS,
    MAX_LOAD_QPS,
    MAX_LOAD_REQUESTS,
    MAX_TIMEOUT_SECONDS,
    MIN_TIMEOUT_SECONDS,
    NAME_MAX_LENGTH,
    QUERY_MAX_COUNT,
    SCHEDULE_MAX_LENGTH,
)

NotifyCategory = Literal["change", "failure", "block"]
DeliveryStatus = Literal["sent", "skipped", "failed", "not_implemented"]
DiffStatus = Literal["added", "removed", "modified", "unchanged"]
ExtractorKind = Literal["css", "xpath", "jsonpath", "regex"]
AssertionKind = Literal["status", "latency_ms", "body_contains", "jsonpath", "header"]


class ScheduleKind(StrEnum):
    """调度类型。"""

    CRON = "cron"
    INTERVAL = "interval"


class TaskType(StrEnum):
    """内置任务类型。"""

    PAGE_CHANGE = "page_change"
    API_CHECK = "api_check"
    LOAD_TEST = "load_test"


class Outcome(StrEnum):
    """一次运行的一等结果。拦截、空页面和超时都不会被折叠成「无变化」。"""

    BASELINE = "baseline"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    EMPTY = "empty"
    TIMEOUT = "timeout"


class HttpMethod(StrEnum):
    """抓取器支持的 HTTP 方法。"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class _StrictModel(BaseModel):
    """拒绝未声明字段，避免静默丢掉拼写错误的配置。"""

    model_config = ConfigDict(extra="forbid")


class ErrorBody(_StrictModel):
    """统一错误响应。"""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Health(_StrictModel):
    """服务健康检查。"""

    status: Literal["ok", "degraded"]
    service: str
    mongo: Literal["ok", "down", "skipped"] = "skipped"


class Schedule(_StrictModel):
    """已经解析过的调度。"""

    kind: ScheduleKind
    expression: str
    interval_seconds: int | None = None


class RequestSpec(_StrictModel):
    """一次出站请求的描述。由抓取器执行，调度器只保存它。"""

    method: HttpMethod = HttpMethod.GET
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    json_body: Any | None = None
    form_body: dict[str, str] | None = None
    raw_body: str | None = None
    cookies: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        ge=MIN_TIMEOUT_SECONDS,
        le=MAX_TIMEOUT_SECONDS,
    )
    follow_redirects: bool = True
    verify_tls: bool = True

    @model_validator(mode="after")
    def check_shape(self) -> Self:
        """限制请求体互斥，并拒绝过大的头、查询和 Cookie。"""
        selected = [
            self.json_body is not None,
            self.form_body is not None,
            self.raw_body is not None,
        ]
        if sum(selected) > 1:
            raise ValueError("json_body、form_body 和 raw_body 只能填写一种")
        if len(self.headers) > HEADER_MAX_COUNT:
            raise ValueError("请求头数量超出限制")
        if len(self.query) > QUERY_MAX_COUNT:
            raise ValueError("查询参数数量超出限制")
        if len(self.cookies) > COOKIE_MAX_COUNT:
            raise ValueError("Cookie 数量超出限制")
        for name, value in self.headers.items():
            if not name.strip() or "\n" in name or "\r" in name or "\n" in value or "\r" in value:
                raise ValueError("请求头包含空名称或换行")
        return self


class RequesterConfig(_StrictModel):
    """任务选中的请求器及其参数。"""

    name: str = Field(default="httpx", min_length=1, max_length=FIELD_NAME_MAX_LENGTH)
    params: dict[str, Any] = Field(default_factory=dict)


class ProxyConfig(_StrictModel):
    """任务选中的代理提供者及其参数。"""

    provider: str = Field(default="direct", min_length=1, max_length=FIELD_NAME_MAX_LENGTH)
    params: dict[str, Any] = Field(default_factory=dict)


class ExtractRule(_StrictModel):
    """从响应里取出一个具名字段。比较的是这些字段，而不是整页哈希。"""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    kind: ExtractorKind
    expression: str = Field(min_length=1, max_length=EXPRESSION_MAX_LENGTH)
    attribute: str | None = Field(default=None, max_length=FIELD_NAME_MAX_LENGTH)


class AssertionSpec(_StrictModel):
    """接口探活断言。"""

    kind: AssertionKind
    expected: str = Field(min_length=1, max_length=EXPECTED_MAX_LENGTH)
    path: str | None = Field(default=None, max_length=EXPRESSION_MAX_LENGTH)

    @model_validator(mode="after")
    def path_required(self) -> Self:
        """JSONPath 和响应头断言必须给出 path。"""
        if self.kind in {"jsonpath", "header"} and not self.path:
            raise ValueError(f"{self.kind} 断言需要 path")
        return self


class LoadSpec(_StrictModel):
    """饱和请求的并发、速率和停止条件。"""

    concurrency: int = Field(default=DEFAULT_LOAD_CONCURRENCY, ge=1, le=MAX_LOAD_CONCURRENCY)
    qps: float | None = Field(default=None, gt=0, le=MAX_LOAD_QPS)
    duration_seconds: float | None = Field(default=None, gt=0, le=MAX_LOAD_DURATION_SECONDS)
    request_count: int | None = Field(default=None, ge=1, le=MAX_LOAD_REQUESTS)

    @model_validator(mode="after")
    def ensure_budget(self) -> Self:
        """没有停止条件时使用默认请求次数，避免无界循环。"""
        if self.duration_seconds is None and self.request_count is None:
            self.request_count = DEFAULT_LOAD_REQUESTS
        return self


def _default_notify_on() -> list[NotifyCategory]:
    """默认在变化、失败和拦截时通知。"""
    return ["change", "failure", "block"]


class NotifySpec(_StrictModel):
    """外部通知槽位。应用内通知记录与此无关，仍会写入。"""

    provider: str = Field(default="none", min_length=1, max_length=FIELD_NAME_MAX_LENGTH)
    params: dict[str, Any] = Field(default_factory=dict)
    on: list[NotifyCategory] = Field(default_factory=_default_notify_on)


class TaskCreate(_StrictModel):
    """创建任务的请求体。schedule 在服务层解析。"""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=DESCRIPTION_MAX_LENGTH)
    enabled: bool = True
    schedule: str = Field(min_length=1, max_length=SCHEDULE_MAX_LENGTH)
    task_type: TaskType
    request: RequestSpec
    requester: RequesterConfig = Field(default_factory=RequesterConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    extract_rules: list[ExtractRule] = Field(
        default_factory=list, max_length=EXTRACT_RULE_MAX_COUNT
    )
    assertions: list[AssertionSpec] = Field(default_factory=list, max_length=ASSERTION_MAX_COUNT)
    load: LoadSpec | None = None
    notify: NotifySpec = Field(default_factory=NotifySpec)


class TaskPatch(_StrictModel):
    """只切换启用状态。"""

    enabled: bool


class Task(_StrictModel):
    """持久化后的任务。"""

    id: str
    name: str
    description: str
    enabled: bool
    schedule: Schedule
    task_type: TaskType
    request: RequestSpec
    requester: RequesterConfig
    proxy: ProxyConfig
    extract_rules: list[ExtractRule]
    assertions: list[AssertionSpec]
    load: LoadSpec | None
    notify: NotifySpec
    next_run_at: datetime
    last_run_at: datetime | None = None
    last_outcome: Outcome | None = None
    running: bool = False
    lock_token: str | None = None
    created_at: datetime
    updated_at: datetime


class FieldDiff(_StrictModel):
    """单个提取字段的前后差异。"""

    name: str
    status: DiffStatus
    before: list[str]
    after: list[str]


class DiffResult(_StrictModel):
    """一次快照比较。"""

    changed: bool
    fields: list[FieldDiff]


class LoadSample(_StrictModel):
    """压测中保留的少量样本，不保存每个请求的正文。"""

    status_code: int | None = None
    outcome: Outcome
    latency_ms: float | None = None
    error_type: str | None = None


class LoadSummary(_StrictModel):
    """一次饱和请求的汇总。"""

    total: int
    succeeded: int
    failed: int
    blocked: int
    timeouts: int
    latency_ms_p50: float | None = None
    latency_ms_p95: float | None = None
    status_histogram: dict[str, int] = Field(default_factory=dict)
    samples: list[LoadSample] = Field(default_factory=list)


class FetchRequest(_StrictModel):
    """调度器发给抓取器的请求。抓取器不读取数据库。"""

    request: RequestSpec
    requester: RequesterConfig = Field(default_factory=RequesterConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    extract_rules: list[ExtractRule] = Field(default_factory=list)
    load: LoadSpec | None = None
    task_type: TaskType


class FetchEnvelope(_StrictModel):
    """抓取器返回的归一化结果。变化与否由调度器决定。"""

    outcome: Outcome
    error_type: str | None = None
    error_message: str | None = None
    status_code: int | None = None
    latency_ms: float | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    body_truncated: bool = False
    extracted: dict[str, list[str]] = Field(default_factory=dict)
    final_url: str | None = None
    requester: str
    proxy_label: str | None = None
    load: LoadSummary | None = None


class TaskEvaluation(_StrictModel):
    """任务类型插件对一次抓取作出的判定。"""

    outcome: Outcome
    summary: str
    error_type: str | None = None
    error_message: str | None = None
    diff: DiffResult | None = None
    snapshot: dict[str, list[str]] | None = None
    notify: bool = False
    notify_category: NotifyCategory | None = None


class Run(_StrictModel):
    """一次执行的完整记录。"""

    id: str
    task_id: str
    task_name: str
    task_type: TaskType
    outcome: Outcome
    error_type: str | None = None
    error_message: str | None = None
    summary: str
    started_at: datetime
    finished_at: datetime
    latency_ms: float | None = None
    status_code: int | None = None
    final_url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    body_truncated: bool = False
    extracted: dict[str, list[str]] = Field(default_factory=dict)
    previous: dict[str, list[str]] | None = None
    diff: DiffResult | None = None
    load: LoadSummary | None = None
    requester: str
    proxy_label: str | None = None
    created_at: datetime


class RunSummary(_StrictModel):
    """运行列表使用的轻量投影。"""

    id: str
    task_id: str
    task_name: str
    task_type: TaskType
    outcome: Outcome
    error_type: str | None = None
    summary: str
    started_at: datetime
    finished_at: datetime
    latency_ms: float | None = None
    status_code: int | None = None


class Snapshot(_StrictModel):
    """网页监控最近一次成功提取的字段。"""

    task_id: str
    fields: dict[str, list[str]]
    updated_at: datetime


class Notification(_StrictModel):
    """应用内通知。外部通道的投递结果记在 delivery 上。"""

    id: str
    task_id: str
    task_name: str
    run_id: str
    category: NotifyCategory
    outcome: Outcome
    title: str
    message: str
    provider: str
    delivery: DeliveryStatus
    delivery_detail: str | None = None
    read: bool = False
    created_at: datetime


class PluginInfo(_StrictModel):
    """插件目录中的一条记录。"""

    slot: str
    name: str
    description: str
    implemented: bool


class Stats(_StrictModel):
    """总览计数。"""

    tasks: int = 0
    enabled: int = 0
    page_change: int = 0
    api_check: int = 0
    load_test: int = 0
    runs_today: int = 0
    changed_today: int = 0
    problems_today: int = 0
    unread_notifications: int = 0


class Page[T](_StrictModel):
    """偏移分页。"""

    items: list[T]
    total: int
    limit: int
    offset: int


def summarize_run(run: Run) -> RunSummary:
    """从完整运行记录生成列表项。"""
    return RunSummary(
        id=run.id,
        task_id=run.task_id,
        task_name=run.task_name,
        task_type=run.task_type,
        outcome=run.outcome,
        error_type=run.error_type,
        summary=run.summary,
        started_at=run.started_at,
        finished_at=run.finished_at,
        latency_ms=run.latency_ms,
        status_code=run.status_code,
    )
