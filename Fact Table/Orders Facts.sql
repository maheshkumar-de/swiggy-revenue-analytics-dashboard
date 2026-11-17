
-- =========================================================
-- POST: ORDER ITEM FACT
-- CONSUMPTION SCHEMA
-- HISTORICAL FACT BACKFILL
-- CORRECTED VERSION
-- =========================================================


-- =========================================================
-- 1. SETUP
-- =========================================================

USE ROLE SYSADMIN;
USE WAREHOUSE ADHOC_WH;
USE DATABASE SANDBOX;
USE SCHEMA CONSUMPTION_SCH;


-- =========================================================
-- 2. CREATE FACT TABLE IF IT DOES NOT EXIST
-- Do not use CREATE OR REPLACE
-- =========================================================

CREATE TABLE IF NOT EXISTS CONSUMPTION_SCH.ORDER_ITEM_FACT (
    ORDER_ITEM_FACT_SK NUMBER AUTOINCREMENT
        COMMENT 'Surrogate Key (EDW)',

    ORDER_ITEM_ID NUMBER
        COMMENT 'Order Item ID from source',

    ORDER_ID NUMBER
        COMMENT 'Order ID from source',

    CUSTOMER_DIM_KEY NUMBER,
    CUSTOMER_ADDRESS_DIM_KEY NUMBER,
    RESTAURANT_DIM_KEY NUMBER,
    RESTAURANT_LOCATION_DIM_KEY NUMBER,
    MENU_DIM_KEY NUMBER,
    DELIVERY_AGENT_DIM_KEY NUMBER,
    ORDER_DATE_DIM_KEY NUMBER,

    QUANTITY NUMBER,
    PRICE NUMBER(10,2),
    SUBTOTAL NUMBER(10,2),

    DELIVERY_STATUS VARCHAR,
    ESTIMATED_TIME VARCHAR
)
COMMENT = 'Item level order fact table';


-- =========================================================
-- 3. INSERT MISSING DATE INTO DATE_DIM
-- Missing date: 2023-11-21
-- Idempotent: will not insert the same date twice
-- =========================================================

INSERT INTO CONSUMPTION_SCH.DATE_DIM (
    DATE_DIM_HK,
    CALENDAR_DATE,
    YEAR,
    QUARTER,
    MONTH,
    WEEK,
    DAY_OF_YEAR,
    DAY_OF_WEEK,
    DAY_OF_THE_MONTH,
    DAY_NAME
)
SELECT
    HASH(SHA1_HEX(DATE '2023-11-21')),
    DATE '2023-11-21',
    YEAR(DATE '2023-11-21'),
    QUARTER(DATE '2023-11-21'),
    MONTH(DATE '2023-11-21'),
    WEEK(DATE '2023-11-21'),
    DAYOFYEAR(DATE '2023-11-21'),
    DAYOFWEEK(DATE '2023-11-21'),
    DAY(DATE '2023-11-21'),
    DAYNAME(DATE '2023-11-21')
WHERE NOT EXISTS (
    SELECT 1
    FROM CONSUMPTION_SCH.DATE_DIM
    WHERE CALENDAR_DATE = DATE '2023-11-21'
);


-- Verify date

SELECT *
FROM CONSUMPTION_SCH.DATE_DIM
WHERE CALENDAR_DATE = DATE '2023-11-21';


-- =========================================================
-- 4. CHECK SOURCE RECORD COUNT
-- Expected: 38 rows, 38 distinct items, 16 orders
-- =========================================================

SELECT
    COUNT(*) AS TOTAL_SOURCE_ITEMS,
    COUNT(DISTINCT oi.ORDER_ITEM_ID) AS DISTINCT_ITEMS,
    COUNT(DISTINCT oi.ORDER_ID_FK) AS DISTINCT_ORDERS
FROM CLEAN_SCH.ORDER_ITEM oi
INNER JOIN CLEAN_SCH.ORDERS o
    ON oi.ORDER_ID_FK = o.ORDER_ID
WHERE oi._STG_FILE_NAME IN (
    'Initial/Order/Item/order-Item-initial.csv',
    'Delta/Order/Item/day-01-order-item.csv',
    'Delta/Order/Item/day-02-order-item.csv'
);


-- =========================================================
-- 5. CHECK MULTIPLE DELIVERY RECORDS
-- Expected: no results
-- =========================================================

SELECT
    ORDER_ID_FK,
    COUNT(*) AS DELIVERY_RECORDS
FROM CLEAN_SCH.DELIVERY
GROUP BY ORDER_ID_FK
HAVING COUNT(*) > 1;


-- =========================================================
-- 6. PREVIEW CORRECTED MERGE SOURCE
-- IMPORTANT:
-- Run this query before cleanup and MERGE.
-- Expected: 38 rows and 38 distinct order items.
-- =========================================================

WITH DELIVERY_ONE AS (
    SELECT
        ORDER_ID_FK,
        DELIVERY_AGENT_ID_FK,
        DELIVERY_STATUS,
        ESTIMATED_TIME
    FROM CLEAN_SCH.DELIVERY
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ORDER_ID_FK
        ORDER BY DELIVERY_AGENT_ID_FK
    ) = 1
),

SOURCE_DATA AS (
    SELECT
        oi.ORDER_ITEM_ID,
        oi.ORDER_ID_FK

    FROM CLEAN_SCH.ORDER_ITEM oi

    INNER JOIN CLEAN_SCH.ORDERS o
        ON oi.ORDER_ID_FK = o.ORDER_ID

    INNER JOIN CONSUMPTION_SCH.CUSTOMER_DIM c
        ON o.CUSTOMER_ID_FK = c.CUSTOMER_ID
       AND c.IS_CURRENT = TRUE

    INNER JOIN CONSUMPTION_SCH.CUSTOMER_ADDRESS_DIM ca
        ON ca.CUSTOMER_ID_FK = c.CUSTOMER_ID
       AND ca.IS_CURRENT = TRUE

    INNER JOIN CONSUMPTION_SCH.RESTAURANT_DIM r
        ON o.RESTAURANT_ID_FK = r.RESTAURANT_ID
       AND r.IS_CURRENT = TRUE

    INNER JOIN CONSUMPTION_SCH.RESTAURANT_LOCATION_DIM rl
        ON r.LOCATION_ID_FK = rl.LOCATION_ID
       AND rl.CURRENT_FLAG = TRUE

    INNER JOIN CONSUMPTION_SCH.MENU_DIM m
        ON oi.MENU_ID_FK = m.MENU_ID

    INNER JOIN CONSUMPTION_SCH.DATE_DIM dd
        ON dd.CALENDAR_DATE = DATE(o.ORDER_DATE)

    LEFT JOIN DELIVERY_ONE d
        ON o.ORDER_ID = d.ORDER_ID_FK

    LEFT JOIN CONSUMPTION_SCH.DELIVERY_AGENT_DIM da
        ON d.DELIVERY_AGENT_ID_FK = da.DELIVERY_AGENT_ID
       AND da.IS_CURRENT = TRUE

    WHERE oi._STG_FILE_NAME IN (
        'Initial/Order/Item/order-Item-initial.csv',
        'Delta/Order/Item/day-01-order-item.csv',
        'Delta/Order/Item/day-02-order-item.csv'
    )
)

SELECT
    COUNT(*) AS TOTAL_SOURCE_ROWS,
    COUNT(DISTINCT ORDER_ITEM_ID) AS DISTINCT_ORDER_ITEMS,
    COUNT(DISTINCT ORDER_ID_FK) AS DISTINCT_ORDERS
FROM SOURCE_DATA;


-- =========================================================
-- 6A. CLEAN EXISTING DUPLICATE FACT RECORDS
-- Keep one record for each ORDER_ITEM_ID + ORDER_ID.
-- The corrected MERGE will update the retained records.
-- =========================================================

DELETE FROM CONSUMPTION_SCH.ORDER_ITEM_FACT AS TARGET
USING (
    SELECT
        ORDER_ITEM_FACT_SK
    FROM CONSUMPTION_SCH.ORDER_ITEM_FACT
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ORDER_ITEM_ID, ORDER_ID
        ORDER BY ORDER_ITEM_FACT_SK
    ) > 1
) AS DUPLICATES
WHERE TARGET.ORDER_ITEM_FACT_SK =
      DUPLICATES.ORDER_ITEM_FACT_SK;


-- Verify duplicate cleanup

SELECT
    ORDER_ITEM_ID,
    ORDER_ID,
    COUNT(*) AS RECORD_COUNT
FROM CONSUMPTION_SCH.ORDER_ITEM_FACT
GROUP BY ORDER_ITEM_ID, ORDER_ID
HAVING COUNT(*) > 1;


-- =========================================================
-- 6B. CORRECTED FACT TABLE MERGE
-- =========================================================

MERGE INTO CONSUMPTION_SCH.ORDER_ITEM_FACT AS TARGET

USING (

    WITH DELIVERY_ONE AS (
        SELECT
            ORDER_ID_FK,
            DELIVERY_AGENT_ID_FK,
            DELIVERY_STATUS,
            ESTIMATED_TIME
        FROM CLEAN_SCH.DELIVERY
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY ORDER_ID_FK
            ORDER BY DELIVERY_AGENT_ID_FK
        ) = 1
    )

    SELECT
        oi.ORDER_ITEM_ID AS ORDER_ITEM_ID,
        oi.ORDER_ID_FK AS ORDER_ID,

        c.CUSTOMER_HK AS CUSTOMER_DIM_KEY,
        ca.CUSTOMER_ADDRESS_HK AS CUSTOMER_ADDRESS_DIM_KEY,
        r.RESTAURANT_HK AS RESTAURANT_DIM_KEY,
        rl.RESTAURANT_LOCATION_HK AS RESTAURANT_LOCATION_DIM_KEY,
        m.MENU_DIM_HK AS MENU_DIM_KEY,
        da.DELIVERY_AGENT_HK AS DELIVERY_AGENT_DIM_KEY,
        dd.DATE_DIM_HK AS ORDER_DATE_DIM_KEY,

        oi.QUANTITY::NUMBER AS QUANTITY,
        oi.PRICE AS PRICE,
        oi.SUBTOTAL AS SUBTOTAL,

        d.DELIVERY_STATUS AS DELIVERY_STATUS,
        d.ESTIMATED_TIME AS ESTIMATED_TIME

    FROM CLEAN_SCH.ORDER_ITEM oi

    INNER JOIN CLEAN_SCH.ORDERS o
        ON oi.ORDER_ID_FK = o.ORDER_ID

    -- Customer dimension
    INNER JOIN CONSUMPTION_SCH.CUSTOMER_DIM c
        ON o.CUSTOMER_ID_FK = c.CUSTOMER_ID
       AND c.IS_CURRENT = TRUE

    -- Customer address dimension
    INNER JOIN CONSUMPTION_SCH.CUSTOMER_ADDRESS_DIM ca
        ON ca.CUSTOMER_ID_FK = c.CUSTOMER_ID
       AND ca.IS_CURRENT = TRUE

    -- Restaurant dimension
    INNER JOIN CONSUMPTION_SCH.RESTAURANT_DIM r
        ON o.RESTAURANT_ID_FK = r.RESTAURANT_ID
       AND r.IS_CURRENT = TRUE

    -- Restaurant location dimension
    INNER JOIN CONSUMPTION_SCH.RESTAURANT_LOCATION_DIM rl
        ON r.LOCATION_ID_FK = rl.LOCATION_ID
       AND rl.CURRENT_FLAG = TRUE

    -- Menu dimension
    -- Historical menu records are required.
    -- Intentionally no IS_CURRENT filter.
    INNER JOIN CONSUMPTION_SCH.MENU_DIM m
        ON oi.MENU_ID_FK = m.MENU_ID

    -- Date dimension
    INNER JOIN CONSUMPTION_SCH.DATE_DIM dd
        ON dd.CALENDAR_DATE = DATE(o.ORDER_DATE)

    -- Optional delivery information
    LEFT JOIN DELIVERY_ONE d
        ON o.ORDER_ID = d.ORDER_ID_FK

    -- CORRECTED DELIVERY AGENT JOIN
    -- Only the current SCD Type 2 record is selected.
    LEFT JOIN CONSUMPTION_SCH.DELIVERY_AGENT_DIM da
        ON d.DELIVERY_AGENT_ID_FK = da.DELIVERY_AGENT_ID
       AND da.IS_CURRENT = TRUE

    WHERE oi._STG_FILE_NAME IN (
        'Initial/Order/Item/order-Item-initial.csv',
        'Delta/Order/Item/day-01-order-item.csv',
        'Delta/Order/Item/day-02-order-item.csv'
    )

) AS SOURCE_STM

ON TARGET.ORDER_ITEM_ID = SOURCE_STM.ORDER_ITEM_ID
AND TARGET.ORDER_ID = SOURCE_STM.ORDER_ID

WHEN MATCHED THEN
    UPDATE SET

        TARGET.CUSTOMER_DIM_KEY =
            SOURCE_STM.CUSTOMER_DIM_KEY,

        TARGET.CUSTOMER_ADDRESS_DIM_KEY =
            SOURCE_STM.CUSTOMER_ADDRESS_DIM_KEY,

        TARGET.RESTAURANT_DIM_KEY =
            SOURCE_STM.RESTAURANT_DIM_KEY,

        TARGET.RESTAURANT_LOCATION_DIM_KEY =
            SOURCE_STM.RESTAURANT_LOCATION_DIM_KEY,

        TARGET.MENU_DIM_KEY =
            SOURCE_STM.MENU_DIM_KEY,

        TARGET.DELIVERY_AGENT_DIM_KEY =
            SOURCE_STM.DELIVERY_AGENT_DIM_KEY,

        TARGET.ORDER_DATE_DIM_KEY =
            SOURCE_STM.ORDER_DATE_DIM_KEY,

        TARGET.QUANTITY =
            SOURCE_STM.QUANTITY,

        TARGET.PRICE =
            SOURCE_STM.PRICE,

        TARGET.SUBTOTAL =
            SOURCE_STM.SUBTOTAL,

        TARGET.DELIVERY_STATUS =
            SOURCE_STM.DELIVERY_STATUS,

        TARGET.ESTIMATED_TIME =
            SOURCE_STM.ESTIMATED_TIME

WHEN NOT MATCHED THEN

    INSERT (
        ORDER_ITEM_ID,
        ORDER_ID,
        CUSTOMER_DIM_KEY,
        CUSTOMER_ADDRESS_DIM_KEY,
        RESTAURANT_DIM_KEY,
        RESTAURANT_LOCATION_DIM_KEY,
        MENU_DIM_KEY,
        DELIVERY_AGENT_DIM_KEY,
        ORDER_DATE_DIM_KEY,
        QUANTITY,
        PRICE,
        SUBTOTAL,
        DELIVERY_STATUS,
        ESTIMATED_TIME
    )

    VALUES (
        SOURCE_STM.ORDER_ITEM_ID,
        SOURCE_STM.ORDER_ID,
        SOURCE_STM.CUSTOMER_DIM_KEY,
        SOURCE_STM.CUSTOMER_ADDRESS_DIM_KEY,
        SOURCE_STM.RESTAURANT_DIM_KEY,
        SOURCE_STM.RESTAURANT_LOCATION_DIM_KEY,
        SOURCE_STM.MENU_DIM_KEY,
        SOURCE_STM.DELIVERY_AGENT_DIM_KEY,
        SOURCE_STM.ORDER_DATE_DIM_KEY,
        SOURCE_STM.QUANTITY,
        SOURCE_STM.PRICE,
        SOURCE_STM.SUBTOTAL,
        SOURCE_STM.DELIVERY_STATUS,
        SOURCE_STM.ESTIMATED_TIME
    );


-- =========================================================
-- 7. FACT TABLE VALIDATION
-- Expected: 38 rows, 38 items, 16 orders
-- =========================================================

SELECT
    COUNT(*) AS TOTAL_FACT_RECORDS,
    COUNT(DISTINCT ORDER_ITEM_ID) AS DISTINCT_ORDER_ITEMS,
    COUNT(DISTINCT ORDER_ID) AS DISTINCT_ORDERS,
    SUM(SUBTOTAL) AS TOTAL_SUBTOTAL
FROM CONSUMPTION_SCH.ORDER_ITEM_FACT;


-- =========================================================
-- 8. CHECK DUPLICATE FACT RECORDS
-- Expected: no results
-- =========================================================

SELECT
    ORDER_ITEM_ID,
    ORDER_ID,
    COUNT(*) AS RECORD_COUNT
FROM CONSUMPTION_SCH.ORDER_ITEM_FACT
GROUP BY ORDER_ITEM_ID, ORDER_ID
HAVING COUNT(*) > 1;


-- =========================================================
-- 9. CHECK MISSING DIMENSION KEYS
-- =========================================================

SELECT
    COUNT_IF(CUSTOMER_DIM_KEY IS NULL) AS MISSING_CUSTOMER,
    COUNT_IF(CUSTOMER_ADDRESS_DIM_KEY IS NULL) AS MISSING_ADDRESS,
    COUNT_IF(RESTAURANT_DIM_KEY IS NULL) AS MISSING_RESTAURANT,
    COUNT_IF(RESTAURANT_LOCATION_DIM_KEY IS NULL) AS MISSING_LOCATION,
    COUNT_IF(MENU_DIM_KEY IS NULL) AS MISSING_MENU,
    COUNT_IF(DELIVERY_AGENT_DIM_KEY IS NULL) AS MISSING_DELIVERY_AGENT,
    COUNT_IF(ORDER_DATE_DIM_KEY IS NULL) AS MISSING_DATE
FROM CONSUMPTION_SCH.ORDER_ITEM_FACT;


-- =========================================================
-- 10. VIEW FINAL FACT TABLE
-- =========================================================

SELECT *
FROM CONSUMPTION_SCH.ORDER_ITEM_FACT
ORDER BY ORDER_ID, ORDER_ITEM_ID;
