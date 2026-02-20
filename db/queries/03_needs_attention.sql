SELECT
    po.po_number,
    COALESCE(
        (
            SELECT a.reasons
            FROM po_alerts a
            WHERE a.po_number = po.po_number
            ORDER BY a.created_at DESC
            LIMIT 1
        ),
        ARRAY[]::text[]
    ) AS reasons
FROM purchase_orders po
WHERE po.po_number = 'PO-2025-0472';
