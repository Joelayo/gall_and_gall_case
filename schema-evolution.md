# Schema Evolution: Bronze → Silver → Gold Layers

## Raw Data Schema (JSON Input)

### Source: `assignment_data.json`
```json
{
  "before": null,
  "after": {
    "TransactionID": "string",
    "StoreID": "string", 
    "WorkstationID": "string",
    "OperatorID": "string",
    "TenderDateTimestamp": "long",
    "ControlType": "string|null",
    "LineItem": [
      {
        "SalesItem": {
          "ItemID": "string",
          "ItemDescription": "string", 
          "DepartmentID": "string",
          "Amount": "double",
          "Quantity": "int"
        },
        "ReturnItem": {
          "ItemID": "string",
          "ItemDescription": "string",
          "DepartmentID": "string", 
          "Amount": "double",
          "Quantity": "int"
        },
        "Discount": {
          "ItemList": [
            {
              "ItemID": "string",
              "DiscountAmount": "double"
            }
          ]
        },
        "TransactionInfo": {
          "InfoType": "string"  // e.g., "Canceled"
        }
      }
    ]
  },
  "source": {...},
  "op": "string",
  "ts_ms": "long",
  "transaction": null
}
```

## Bronze Layer Schema

```sql
bronze_schema = {
  "before": "struct<...>",
  "after": "struct<
    TransactionID: string,
    StoreID: string,
    WorkstationID: string, 
    OperatorID: string,
    TenderDateTimestamp: long,
    ControlType: string,
    LineItem: array<struct<
      SalesItem: struct<
        ItemID: string,
        ItemDescription: string,
        DepartmentID: string,
        Amount: double,
        Quantity: int
      >,
      ReturnItem: struct<
        ItemID: string,
        ItemDescription: string,
        DepartmentID: string,
        Amount: double, 
        Quantity: int
      >,
      Discount: struct<
        ItemList: array<struct<
          ItemID: string,
          DiscountAmount: double
        >>
      >,
      TransactionInfo: struct<
        InfoType: string
      >
    >>
  >",
  "source": "struct<...>",
  "op": "string",
  "ts_ms": "long",
  "transaction": "string",
  
  "ingestion_timestamp": "timestamp",
  "source_file": "string"
}
```

## Silver Layer Schema

```sql
silver_schema = {
  "TransactionID": "string",
  "StoreID": "string", 
  "WorkstationID": "string",
  "OperatorID": "string",
  "TenderDateTimestamp": "long",
  "item_id": "string",                    
  "item_description": "string",            
  "department_id": "string",              
  "gross_amount": "double",               
  "quantity": "int",                      
  "total_discount_amount": "double",      
  "net_amount": "double"                  
}
```


## Gold Layer Schema (Dimensional Model)


#### Fact Table: `fact_transaction_items`
```sql
fact_transaction_items_schema = {
  "product_key": "long",              
  "store_key": "long",                 
  "date_key": "long",                 
  "transaction_id": "string",         
  "transaction_timestamp": "long",    
  "quantity": "int",                  
  "gross_amount": "double",           
  "total_discount_amount": "double",  
  "net_amount": "double"              
}
```

#### Dimension Table: `dim_products`
```sql
dim_products_schema = {
  "product_key": "long",              
  "item_id": "string",                
  "item_description": "string",       
  "department_id": "string"           
}
```

#### Dimension Table: `dim_stores`  
```sql
dim_stores_schema = {
  "store_key": "long",                
  "StoreID": "string"                 
}
```

#### Dimension Table: `dim_date`
```sql
dim_date_schema = {
  "date_key": "long",                 
  "transaction_date": "date"          
}
```

