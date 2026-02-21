SELECT upsert_purchase_order(
    pg_read_file('/work/tests/attention_suite/parsed/no_flags.json')::jsonb
) AS purchase_order_id;
