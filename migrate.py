import pandas as pd
from sqlalchemy import create_engine

# Step 1: Read the CSV file
csv_file = "survey_motivasi_lari_anak_muda.csv"
df = pd.read_csv(csv_file)

# Step 2: Set up PostgreSQL connection
db_username = "postgres"
db_password = "postgres"
db_host = "localhost"
db_port = "5432"
db_name = "sharing_session"

# Create connection string
connection_string = (
    f"postgresql://{db_username}:{db_password}@{db_host}:{db_port}/{db_name}"
)

# Create SQLAlchemy engine
engine = create_engine(connection_string)

# Step 3: Insert DataFrame into PostgreSQL
table_name = "motivations"
df.to_sql(table_name, engine, if_exists="replace", index=False)

print(f"Data inserted into {table_name} successfully!")
