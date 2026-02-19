SELECT upsert_purchase_order(
    pg_read_file('/work/tests/test1/test1.json')::jsonb
) AS purchase_order_id;
