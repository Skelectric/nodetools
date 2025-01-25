SELECT 
    tm.*,
    p.processed,
    p.rule_name,
    p.response_tx_hash,
    p.notes,
    p.reviewed_at
FROM transaction_memos tm
LEFT JOIN transaction_processing_results p ON tm.hash = p.hash
WHERE 
    (tm.destination = $1 OR tm.account = $1) AND  -- Filter by node address
    CASE 
        WHEN $2 = TRUE THEN TRUE  -- include_processed is TRUE
        ELSE (p.hash IS NULL or p.processed = FALSE)     -- include null or false processed
    END
ORDER BY 
    CASE WHEN $3 = 'datetime ASC' THEN tm.datetime END ASC,
    CASE WHEN $3 = 'datetime DESC' THEN tm.datetime END DESC
OFFSET CASE
    WHEN CAST($4 AS INTEGER) IS NULL THEN 0
    ELSE CAST($4 AS INTEGER)::integer
END
LIMIT CASE 
    WHEN CAST($5 AS INTEGER) IS NULL THEN NULL 
    ELSE CAST($5 AS INTEGER)::integer 
END
