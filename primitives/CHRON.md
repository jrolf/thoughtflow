# CHRON

> Schedule manager for recurring jobs. Define, execute, edit, and delete timed tasks with cron expressions or fixed intervals.

## Philosophy

Agents don't just respond to requests — many need to act on a schedule. A monitoring agent checks health every five minutes. A reporting agent compiles daily summaries at 9am. A cleanup agent runs weekly maintenance on Sundays at 2am.

CHRON is the primitive that makes time-driven behavior a first-class concept in ThoughtFlow. It separates *what* runs from *when* it runs, so the same ACTION, THOUGHT, AGENT, or WORKFLOW can be invoked on demand or on a schedule without changing its implementation.

The key design insight is that the **schedule definition is data, not infrastructure**. CHRON doesn't depend on system cron, Kubernetes CronJobs, or CloudWatch Events — though it works perfectly alongside them. It provides two execution modes:

- **Tick mode**: An external clock (Lambda trigger, system cron) calls `tick()` periodically. CHRON checks what's due and runs it. The process can be ephemeral.
- **Loop mode**: `run()` or `start()` runs a self-managed scheduling loop in-process. The process is long-lived.

Both modes share the same job registry, the same CRUD operations, and the same state tracking. Switching between them requires no code changes to the jobs themselves.

## How It Works

CHRON holds a registry of named jobs. Each job has:

- A **schedule** — either a standard 5-field cron expression (`"0 9 * * *"`) or a fixed interval in seconds (`every=300`)
- An **action** — any callable that accepts a MEMORY instance (ACTION, THOUGHT, AGENT, WORKFLOW, or a plain function)
- **State** — last_run, next_run, run_count, last_duration_ms, last_error

When `tick()` is called (manually or by the scheduler loop), CHRON compares the current time against each job's `next_run`. Jobs whose `next_run` has passed are executed sequentially. After execution, `next_run` is recomputed.

By default, each job execution receives a **fresh MEMORY** instance. You can alternatively provide a shared MEMORY (for jobs that accumulate state across runs) or a `memory_factory` callable (for custom initialization per run).

### Cron Expression Parsing

CHRON includes a pure-Python cron expression parser (zero dependencies). It supports:

- Wildcards: `*`
- Exact values: `30`
- Ranges: `1-5`
- Steps: `*/15`, `1-10/3`
- Lists: `1,15,30`
- Day-of-week: 0=Sunday, 6=Saturday (7 is also accepted as Sunday)
- Standard OR-logic when both day-of-month and day-of-week are restricted

### Catch-Up Behavior

When a process restarts after downtime, some jobs may have missed their scheduled runs. The `catch_up` parameter controls what happens:

- `catch_up=False` (default): The schedule jumps ahead to the next future occurrence. Missed runs are lost.
- `catch_up=True`: After executing a due job, `next_run` is computed from the *previous* scheduled time, not from now. This means missed runs are replayed one-per-tick until the schedule catches up to the present.

### State Persistence

Job state can optionally persist to a JSON file (`state_file` parameter). This allows:

- Surviving process restarts without losing run history
- Detecting missed runs for catch-up
- Multiple processes sharing awareness of the last execution time

When no `state_file` is provided, state lives in memory only.

## Inputs & Configuration

### CHRON Constructor

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | No | "chron" | Identifier for this scheduler instance. |
| state_file | No | None | Path to JSON file for persisting job state across restarts. |
| timezone | No | "UTC" | Default timezone for cron evaluation (e.g. "America/New_York"). |

### add() Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| name | Yes | — | Unique name for this job. |
| schedule | One of | — | Cron expression (5 fields: minute hour day month weekday). |
| every | these two | — | Interval in seconds between runs. |
| action | Yes | — | Callable that receives a MEMORY as its first argument. |
| enabled | No | True | Whether the job starts active. |
| catch_up | No | False | Replay missed runs instead of skipping to the future. |
| memory | No | None | Shared MEMORY instance for all executions. |
| memory_factory | No | None | Callable returning a fresh MEMORY per execution. |

## Usage

```python
from thoughtflow import CHRON, MEMORY

# Create a scheduler
chron = CHRON(name="ops", state_file="chron_state.json")

# Add a cron-based job: 9am daily
chron.add(
    "daily_report",
    schedule="0 9 * * *",
    action=report_workflow,
)

# Add an interval-based job: every 5 minutes
chron.add(
    "health_check",
    every=300,
    action=check_health,
)

# Add a job that's initially paused
chron.add(
    "weekly_cleanup",
    schedule="0 2 * * 0",
    action=cleanup_action,
    enabled=False,
)

# CRUD operations
chron.edit("health_check", every=600)    # Change interval
chron.pause("daily_report")              # Disable temporarily
chron.resume("daily_report")             # Re-enable
chron.remove("weekly_cleanup")           # Delete entirely
chron.list()                             # All jobs with state
chron.get("health_check")               # Single job info

# Execution: tick mode (serverless)
results = chron.tick()
for r in results:
    print(r["name"], r["status"], r["duration_ms"])

# Execution: loop mode (daemon)
chron.start(tick_interval=30)  # Background thread
# ... application runs ...
chron.stop()                   # Clean shutdown

# Manual trigger (ignores schedule)
chron.fire("daily_report")

# Shared memory across executions
shared = MEMORY()
chron.add("accumulator", every=60, action=my_action, memory=shared)

# Catch-up for missed runs
chron.add("critical", schedule="0 * * * *", action=hourly_check, catch_up=True)
```

## Relationship to Other Primitives

- **WORKFLOW**: WORKFLOW orchestrates *what runs in what order* within a single execution. CHRON orchestrates *what runs at what times* across many executions. They are complementary — a WORKFLOW is a natural choice as a CHRON job's action.
- **ACTION / THOUGHT / AGENT**: Any of these can serve as a CHRON job's action. They all follow the `memory = thing(memory)` contract that CHRON expects.
- **SLEEP**: SLEEP pauses within a single execution for a known duration. CHRON spaces out executions over calendar time. SLEEP is intra-run; CHRON is inter-run.
- **WAIT**: WAIT polls a condition within a run. CHRON is time-driven. A CHRON job could contain a WAIT if the scheduled task needs to poll for readiness.
- **NOOP**: A CHRON job can use NOOP as a placeholder action during development, before the real logic is ready.
- **NOTIFY**: Natural pairing — CHRON fires a job, and the job's last step sends a NOTIFY with the results.
- **MEMORY**: Each job execution receives a MEMORY. By default it's fresh; `memory=` shares one; `memory_factory=` creates custom ones.

## Considerations for Future Development

- **Async execution**: Support for `asyncio`-based actions and non-blocking execution of multiple due jobs.
- **Concurrency**: Parallel execution of independent jobs within a single tick, using thread pools.
- **Distributed locking**: For multi-process deployments, optional lock coordination so only one process runs a given job (e.g., using a file lock or Redis).
- **Job dependencies**: Run job B only after job A completes successfully — combining CHRON's time awareness with WORKFLOW's step dependencies.
- **Cron aliases**: Human-friendly shortcuts like `"@hourly"`, `"@daily"`, `"@weekly"` in addition to raw cron expressions.
- **Jitter**: Random offset added to scheduled times to avoid thundering-herd problems when many jobs share the same schedule.
- **Web dashboard**: A lightweight status page showing all jobs, their state, and recent execution history.
