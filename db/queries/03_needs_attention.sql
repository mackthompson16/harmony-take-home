SELECT
    po.po_number,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN po.total_amount > 15000 THEN 'amount_exceeds_threshold' END,
        CASE WHEN po.due_date <= CURRENT_DATE + INTERVAL '7 days' THEN 'due_soon' END,
        CASE WHEN po.is_urgent THEN 'subject_contains_urgent' END,
        CASE WHEN po.vendor IS NULL OR po.order_date IS NULL OR po.due_date IS NULL THEN 'required_fields_missing' END
    ], NULL) AS reasons
FROM purchase_orders po
WHERE po.po_number = 'PO-2025-0472';
