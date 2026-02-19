SELECT
    po.id,
    po.po_number,
    po.vendor,
    po.order_date,
    po.due_date,
    po.total_amount,
    po.is_urgent,
    po.updated_at
FROM purchase_orders po
WHERE po.po_number = 'PO-2025-0472';

SELECT
    li.item_no,
    li.description,
    li.qty,
    li.unit_price,
    li.line_total
FROM purchase_order_line_items li
JOIN purchase_orders po ON po.id = li.purchase_order_id
WHERE po.po_number = 'PO-2025-0472'
ORDER BY li.item_no;
