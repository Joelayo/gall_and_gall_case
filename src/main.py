import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    explode,
    input_file_name,
    when,
    coalesce,
    monotonically_increasing_id,
    from_unixtime,
    to_date,
)

def main():
    """
    Main ETL script for processing Gall & Gall POS data.
    """

    # --- Configuration for ADLS ---
    storage_account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    container_name = os.environ.get("AZURE_CONTAINER_NAME")
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")

    # Check if running in local mode (no Azure credentials)
    use_local_storage = not all([storage_account_name, container_name, tenant_id, client_id, client_secret])
    
    if use_local_storage:
        print("🏠 Running in LOCAL mode (no Azure credentials found)")
        spark = SparkSession.builder \
            .appName("GallAndGallETL-Local") \
            .getOrCreate()
        
        # Define local paths
        raw_data_path = "data/assignment_data.json"
        bronze_output_path = "output/bronze"
        silver_output_path = "output/silver"
        gold_output_path = "output/gold"
    else:
        print("☁️ Running in AZURE mode")
        spark = SparkSession.builder \
            .appName("GallAndGallETL-ADLS") \
            .config("spark.jars", "/app/jars/hadoop-azure-3.3.4.jar,/app/jars/azure-storage-8.6.6.jar") \
            .config("spark.hadoop.fs.defaultFS", "file:///") \
            .config(f"spark.hadoop.fs.azure.account.auth.type.{storage_account_name}.dfs.core.windows.net", "OAuth") \
            .config(f"spark.hadoop.fs.azure.account.oauth.provider.type.{storage_account_name}.dfs.core.windows.net", "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider") \
            .config(f"spark.hadoop.fs.azure.account.oauth2.client.id.{storage_account_name}.dfs.core.windows.net", client_id) \
            .config(f"spark.hadoop.fs.azure.account.oauth2.client.secret.{storage_account_name}.dfs.core.windows.net", client_secret) \
            .config(f"spark.hadoop.fs.azure.account.oauth2.client.endpoint.{storage_account_name}.dfs.core.windows.net", f"https://login.microsoftonline.com/{tenant_id}/oauth2/token") \
            .getOrCreate()

        # Define ADLS paths
        base_path = f"abfss://{container_name}@{storage_account_name}.dfs.core.windows.net"
        raw_data_path = f"{base_path}/raw/assignment_data.json"
        bronze_output_path = f"{base_path}/bronze"
        silver_output_path = f"{base_path}/silver"
        gold_output_path = f"{base_path}/gold"

    # --- BRONZE LAYER ---
    print("Starting Bronze layer processing...")
    df_bronze = spark.read.option("multiLine", "true").json(raw_data_path)
    df_bronze = df_bronze.withColumn("ingestion_timestamp", current_timestamp()) \
                           .withColumn("source_file", input_file_name())
    df_bronze.write.mode("overwrite").parquet(bronze_output_path)
    print("Successfully wrote data to Bronze layer.")

    # --- SILVER LAYER ---
    print("Starting Silver layer processing...")
    df_silver_raw = spark.read.parquet(bronze_output_path)
    
    # Select the payload and filter out records without a LineItem array or with ControlType
    df_transactions = df_silver_raw.select("after.*") \
        .filter(col("LineItem").isNotNull()) \
        .filter(col("ControlType").isNull())

    df_exploded = df_transactions.withColumn("item", explode("LineItem"))

    # Identify and filter out canceled transactions
    canceled_transactions_df = df_exploded \
        .filter(col("item.TransactionInfo.InfoType") == "Canceled") \
        .select("TransactionID").distinct()
    
    canceled_ids = [row.TransactionID for row in canceled_transactions_df.collect()]
    df_cleaned = df_exploded.filter(~col("TransactionID").isin(canceled_ids))

    # Process Sales and Return items
    df_sales_items = df_cleaned \
        .filter(col("item.SalesItem").isNotNull() | col("item.ReturnItem").isNotNull()) \
        .select(
            "TransactionID", "StoreID", "WorkstationID", "OperatorID", "TenderDateTimestamp",
            coalesce(col("item.SalesItem.ItemID"), col("item.ReturnItem.ItemID")).alias("item_id"),
            coalesce(col("item.SalesItem.ItemDescription"), col("item.ReturnItem.ItemDescription")).alias("item_description"),
            coalesce(col("item.SalesItem.DepartmentID"), col("item.ReturnItem.DepartmentID")).alias("department_id"),
            when(col("item.ReturnItem").isNotNull(), col("item.ReturnItem.Amount") * -1).otherwise(col("item.SalesItem.Amount")).alias("gross_amount"),
            when(col("item.ReturnItem").isNotNull(), col("item.ReturnItem.Quantity") * -1).otherwise(col("item.SalesItem.Quantity")).alias("quantity")
        ).filter(col("item_id").isNotNull()) # Ensure we only have items with an ID

    # Process and attribute discounts
    df_discounts = df_cleaned \
        .filter(col("item.Discount").isNotNull()) \
        .select("TransactionID", explode("item.Discount.ItemList").alias("discount_item")) \
        .select(
            "TransactionID",
            col("discount_item.ItemID").alias("item_id"),
            col("discount_item.DiscountAmount").alias("discount_amount")
        )
    
    df_agg_discounts = df_discounts.groupBy("TransactionID", "item_id").sum("discount_amount") \
                                 .withColumnRenamed("sum(discount_amount)", "total_discount_amount")

    # Join discounts back to sales items
    df_silver = df_sales_items.join(df_agg_discounts, ["TransactionID", "item_id"], "left") \
        .na.fill(0, ["total_discount_amount"]) \
        .withColumn("net_amount", col("gross_amount") - col("total_discount_amount"))

    df_silver.write.mode("overwrite").parquet(silver_output_path)
    print("Successfully wrote data to Silver layer.")

    # --- GOLD LAYER ---
    print("Starting Gold layer processing...")
    df_gold_source = spark.read.parquet(silver_output_path)
    df_gold_source = df_gold_source.withColumn(
        "transaction_date", to_date(from_unixtime(col("TenderDateTimestamp") / 1000))
    )

    # Dimension: dim_products
    dim_products = df_gold_source.select("item_id", "item_description", "department_id") \
        .distinct() \
        .withColumn("product_key", monotonically_increasing_id())

    # Dimension: dim_stores
    dim_stores = df_gold_source.select("StoreID").distinct() \
        .withColumn("store_key", monotonically_increasing_id())

    # Dimension: dim_date
    dim_date = df_gold_source.select("transaction_date").distinct() \
        .withColumn("date_key", monotonically_increasing_id())

    # Fact Table: fact_transaction_items
    fact_transaction_items = df_gold_source \
        .join(dim_products, on=["item_id", "item_description", "department_id"], how="left") \
        .join(dim_stores, on="StoreID", how="left") \
        .join(dim_date, on="transaction_date", how="left") \
        .select(
            col("product_key"),
            col("store_key"),
            col("date_key"),
            col("TransactionID").alias("transaction_id"),
            col("TenderDateTimestamp").alias("transaction_timestamp"),
            col("quantity"),
            col("gross_amount"),
            col("total_discount_amount"),
            col("net_amount")
        )
    
    # Write Gold Layer tables
    fact_transaction_items.write.mode("overwrite").parquet(f"{gold_output_path}/fact_transaction_items")
    dim_products.write.mode("overwrite").parquet(f"{gold_output_path}/dim_products")
    dim_stores.write.mode("overwrite").parquet(f"{gold_output_path}/dim_stores")
    dim_date.write.mode("overwrite").parquet(f"{gold_output_path}/dim_date")
    print("Successfully wrote data to Gold layer.")

    spark.stop()

if __name__ == "__main__":
    main()