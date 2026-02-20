SELECT
    wr.id,
    wr.state,
    wr.started_at,
    wr.finished_at,
    wr.error_message
FROM workflow_runs wr
ORDER BY wr.id DESC
LIMIT 10;

SELECT
    wr.id,
    wr.state,
    wr.started_at,
    wr.finished_at,
    COUNT(*) FILTER (WHERE por.state = 'PENDING') AS pending_tasks,
    COUNT(*) FILTER (WHERE por.state = 'RUNNING') AS running_tasks,
    COUNT(*) FILTER (WHERE por.state = 'SUCCESS') AS success_tasks,
    COUNT(*) FILTER (WHERE por.state = 'FAILED') AS failed_tasks
FROM workflow_runs wr
LEFT JOIN purchase_order_runs por ON por.workflow_run_id = wr.id
GROUP BY wr.id, wr.state, wr.started_at, wr.finished_at
ORDER BY wr.id DESC
LIMIT 10;

SELECT
    wr.id,
    wr.state,
    wr.started_at
FROM workflow_runs wr
WHERE wr.state = 'RUNNING'
ORDER BY wr.started_at DESC;

SELECT
    wr.id,
    wr.state,
    wr.started_at,
    wr.finished_at
FROM workflow_runs wr
WHERE wr.state IN ('SUCCESS', 'FAILED')
ORDER BY wr.finished_at DESC
LIMIT 20;

SELECT
    por.id,
    por.workflow_run_id,
    por.test_name,
    por.po_number,
    por.state,
    por.updated_at
FROM purchase_order_runs por
WHERE por.state = 'RUNNING'
ORDER BY por.updated_at DESC;

SELECT
    por.id,
    por.workflow_run_id,
    por.test_name,
    por.po_number,
    por.state,
    por.attempts,
    por.error_message,
    por.updated_at
FROM purchase_order_runs por
ORDER BY por.id DESC
LIMIT 50;

SELECT
    h.purchase_order_run_id,
    h.from_state,
    h.to_state,
    h.changed_at,
    h.error_message
FROM purchase_order_run_state_history h
ORDER BY h.id DESC
LIMIT 100;
