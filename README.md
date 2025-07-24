# Gall & Gall POS Data Engineering Pipeline

This project contains a data pipeline to ingest and process Point of Sale (POS) transactional data. The pipeline is built using PySpark and containerized with Docker.

## 🏛️ Architecture

The pipeline follows the **Medallion Architecture** to progressively refine data into a query-ready state.

* **Bronze Layer**: Ingests the raw source JSON data without any transformation. This layer serves as the immutable source of truth. The data is stored in Parquet format for efficiency.
* **Silver Layer**: Cleanses and conforms the data from the Bronze layer. This involves:
    * Parsing nested transaction details.
    * Filtering out non-transactional records (e.g., operator sign-offs).
    * Attributing discounts to their corresponding sales items.
    * Creating a single, clean table of all sales and return line items.
* **Gold Layer**: Transforms the cleaned Silver data into a business-ready **Star Schema**. This model is optimized for the finance department and data analysts who use SQL. It consists of:
    * `fact_transaction_items`: A central fact table with quantitative measures (amounts, quantities).
    * `dim_products`, `dim_stores`, `dim_date`: Dimension tables with descriptive attributes.

This approach ensures data quality, governance, and provides an easy-to-use structure for analytical queries.

## 🚀 Deployment Options

### Option 1: Local Development (Docker with Local Storage)

**Prerequisites:**
* Docker
* Docker Compose

**Steps:**
1. Clone this repository
2. Place the `assignment_data.json` file inside the `data/` directory
3. Run the pipeline:
    ```bash
    docker-compose up --build
    ```
4. Once complete, processed data will be available in the `output/` directory

### Option 2: Docker with Azure Data Lake Storage (ADLS)

**Prerequisites:**
* Docker
* Docker Compose  
* Azure subscription with ADLS Gen2 storage account
* Configured Azure Service Principal (see setup below)

**Steps:**
1. Complete the [Azure ADLS Setup](#azure-adls-setup) (one-time setup)
2. Create a `.env` file with your Azure credentials:
    ```bash
    AZURE_STORAGE_ACCOUNT_NAME=your_storage_account_name
    AZURE_CONTAINER_NAME=data
    AZURE_TENANT_ID=your_tenant_id
    AZURE_CLIENT_ID=your_service_principal_client_id
    AZURE_CLIENT_SECRET=your_service_principal_secret
    ```
3. Run the pipeline:
    ```bash
    docker-compose up --build
    ```
4. Processed data will be stored in ADLS under `/bronze/`, `/silver/`, and `/gold/` folders

## ⚙️ Azure ADLS Setup

### Step 1: Create Storage Account with Data Lake Gen2

```bash
# Set variables
RESOURCE_GROUP="your-resource-group"
STORAGE_ACCOUNT="yourstorageaccount"  # Must be globally unique
LOCATION="westeurope"

# Create resource group (if not exists)
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create storage account with Data Lake Gen2 enabled
az storage account create \
    --name $STORAGE_ACCOUNT \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS \
    --kind StorageV2 \
    --enable-hierarchical-namespace true

# Create container for data
az storage container create \
    --name data \
    --account-name $STORAGE_ACCOUNT
```

### Step 2: Create Service Principal

```bash
# Create service principal
az ad sp create-for-rbac \
    --name "gall-and-gall-etl-sp" \
    --role "Storage Blob Data Contributor" \
    --scopes "/subscriptions/{subscription-id}/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"
```

**Save the output values:**
- `appId` → `AZURE_CLIENT_ID`
- `password` → `AZURE_CLIENT_SECRET` 
- `tenant` → `AZURE_TENANT_ID`

### Step 3: Assign Storage Blob Data Contributor Role

```bash
# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id --output tsv)

# Get the service principal object ID
SP_OBJECT_ID=$(az ad sp show --id $AZURE_CLIENT_ID --query id --output tsv)

# Assign Storage Blob Data Contributor role
az role assignment create \
    --assignee-object-id $SP_OBJECT_ID \
    --assignee-principal-type ServicePrincipal \
    --role "Storage Blob Data Contributor" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"
```

### Step 4: Verify Setup

```bash
# Test access (optional)
az storage blob list \
    --container-name data \
    --account-name $STORAGE_ACCOUNT \
    --auth-mode login
```

## 📂 Project Structure

```
gall_and_gall_case/
├── data/                  # Input data location (local mode)
│   └── assignment_data.json
├── output/                # Output location (local mode)
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── src/                   # Source code for the ETL pipeline
│   └── main.py
├── Dockerfile             # Container environment definition
├── docker-compose.yml     # Container orchestration
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md              # This documentation
```

## 🔧 Technical Details

* **Technology Stack**: PySpark 3.5.0, Python 3.9, Docker
* **Data Format**: Input JSON, Output Parquet (optimized for analytics)
* **Processing Engine**: Apache Spark
* **Container Runtime**: Docker with OpenJDK 17
* **Cloud Storage**: Azure Data Lake Storage Gen2 (optional)

## 📊 Output Schema

### Gold Layer Tables

**fact_transaction_items**
- TransactionID, item_id, StoreID, WorkstationID, OperatorID
- transaction_date, gross_amount, quantity, total_discount_amount, net_amount

**dim_products**
- item_id, item_description, department_id

**dim_stores**
- StoreID (extendable for store metadata)

**dim_date**
- transaction_date, year, month, day, day_of_week