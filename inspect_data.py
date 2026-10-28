
import pandas as pd

# Load the dataset
df = pd.read_csv("data/reservoir_daily.csv")

# Convert date text into proper dates
df["date"] = pd.to_datetime(df["date"])

# Select Mettur Reservoir records
mettur = df[df["reservoir_slug"] == "mettur"].copy()

# Sort records by date
mettur = mettur.sort_values("date")

print("\n--- METTUR DATASET ---")
print("Number of records:", len(mettur))

print("\n--- FIRST 5 RECORDS ---")
print(
    mettur[
        ["date", "level_ft", "capacity_mcft","storage_mcft", "inflow_cusecs", "outflow_cusecs"]
    ].head().to_string(index=False)
)

print("\n--- STORAGE STATISTICS (MCFT) ---")
print(mettur["storage_mcft"].describe())

print("\n--- MISSING VALUES IN METTUR DATA ---")
print(
    mettur[
        ["level_ft", "storage_mcft", "inflow_cusecs", "outflow_cusecs"]
    ].isnull().sum()
)

print("\n--- DATE RANGE ---")
print("Start:", mettur["date"].min())
print("End:", mettur["date"].max())
