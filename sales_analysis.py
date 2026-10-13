import sqlite3
import pandas as pd
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)


def setup_database(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY,
        name TEXT,
        city TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        amount REAL,
        order_date TEXT
    )
    """)
    customers = [
        (1, "Ali", "Tehran"),
        (2, "Sara", "Isfahan"),
        (3, "Reza", "Mashhad"),
        (4, "Maryam", "Tehran"),
        (5, "Nima", "Shiraz")
    ]

    orders = [
        (1, 150.0, "10-01-2024"),
        (2, 300.5, "12-01-2024"),
        (1, 85.0, "15-01-2024"),
        (3, 500.0, "20-01-2024"),
        (4, 120.0, "20-01-2024"),
        (4, 120.0, "22-01-2024")
    ]

    cursor.execute("DELETE FROM customers")
    cursor.execute("DELETE FROM orders")

    cursor.executemany(
        "INSERT INTO customers (customer_id, name, city) VALUES (?, ?, ?)",
        customers
    )

    cursor.executemany(
        "INSERT INTO orders (customer_id, amount, order_date) VALUES (?, ?, ?)",
        orders
    )

    connection.commit()


def extract_data(connection: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_customers = pd.read_sql_query("SELECT * FROM customers", connection)
    df_orders = pd.read_sql_query("SELECT * FROM orders", connection)
    return df_customers, df_orders


def transform_data(
        df_customers: pd.DataFrame,
        df_orders: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    df_merged = pd.merge(df_customers, df_orders, on="customer_id", how="outer")
    df_merged['order_date'] = pd.to_datetime(df_merged['order_date'], dayfirst=True)
    df_merged['month'] = df_merged['order_date'].dt.month_name()
    city_sales = df_merged.groupby("city", as_index=False)['amount'].sum()
    city_summary = df_merged.groupby("city", as_index=False).agg(
        total_sales=('amount', 'sum'),
        order_count=('order_id', 'count')
    )
    inactive_mask = df_merged['order_id'].isna()
    inactive_customers = df_merged.loc[inactive_mask, ['name', 'city']]
    df_merged['amount'] = df_merged['amount'].fillna(0.0)
    top_customers = df_merged.groupby("name", as_index=False)['amount'].agg('sum')
    top_customers = top_customers.sort_values(by="amount", ascending=False).reset_index(drop=True)
    city_customers = df_merged.groupby(['city', 'name'], as_index=False)['amount'].sum()
    city_customers = city_customers.sort_values(by=['city', 'amount'], ascending=[True, False]).reset_index(drop=True)
    high_sales_cities = city_sales[city_sales['amount'] >= 400].reset_index(drop=True)
    return {
        "merged": df_merged,
        "city_sales": city_sales,
        "inactive": inactive_customers,
        "city_summary": city_summary,
        "top_customers": top_customers,
        "city_customers": city_customers,
        "high_sales": high_sales_cities
    }


def save_summary(
        connection: sqlite3.Connection,
        df: pd.DataFrame,
        table_name: str
) -> None:
    df.to_sql(name=table_name, con=connection, if_exists="replace", index=False)


def main():
    connection = sqlite3.connect("ecommerce.db")
    try:
        setup_database(connection)
        df_customers, df_orders = extract_data(connection)
        results = transform_data(df_customers, df_orders)
        save_summary(
            connection=connection,
            df=results['city_summary'],
            table_name="city_sales_summary"
        )
        save_summary(
            connection=connection,
            df=results['top_customers'],
            table_name="top_customers"
        )
        df_check = pd.read_sql_query("SELECT * FROM city_sales_summary", connection)
        df_top_check = pd.read_sql_query("SELECT * FROM top_customers", connection)

        print("--- Customers ---")
        print(df_customers)
        print("\n--- Orders ---")
        print(df_orders)

        print("\n--- merged ---")
        print(results['merged'])

        print("\n--- Inactive Customers ---")
        print(results['inactive'])

        print("\n--- City Sales ---")
        print(results['city_sales'])

        print("\n--- City Summary ---")
        print(results['city_summary'])

        print("\n--- Top Customers ---")
        print(results['top_customers'])

        print("\n--- City Customers ---")
        print(results['city_customers'])

        print("\n--- High Sales ---")
        print(results['high_sales'])

        print("\n--- From SQLite Table: city_sales_summary ---")
        print(df_check)
        print("\n--- From SQLite Table: top_customers ---")
        print(df_top_check)

        query_city_sales = """
        SELECT c.city,
        COALESCE(SUM(o.amount), 0) AS total_sales,
        COUNT(*) AS row_count,
        COUNT(o.order_id) AS order_count,
        CASE
            WHEN SUM(o.amount) IS NULL THEN 'No Sales'
            WHEN SUM(o.amount) >= 400 THEN 'High'
            WHEN SUM(o.amount) >= 200 THEN 'Medium'
            ELSE 'Low'
        END AS sales_level

        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        GROUP BY c.city
        """
        df_sql_city_sales = pd.read_sql_query(query_city_sales, connection)

        print("\n--- Direct SQL City Sales (LEFT JOIN) ---")
        print(df_sql_city_sales)

        query_above_average_orders = """
        SELECT *
        FROM orders
        WHERE amount >(
            SELECT AVG(amount)
            FROM orders
        )
        """

        df_above_average_orders = pd.read_sql_query(
            query_above_average_orders,
            connection
        )

        print("\n--- Orders Above Average ---")
        print(df_above_average_orders)

    finally:
        connection.close()
        print("\n[Database connection closed safely.]")

if __name__ == "__main__":
    main()
