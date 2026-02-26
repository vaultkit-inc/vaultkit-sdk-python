import os
from vaultkit import VaultKitClient

client = VaultKitClient(
    base_url=os.environ["VAULTKIT_URL"],
    token=os.environ["VAULTKIT_TOKEN"],
    org=os.environ["VAULTKIT_ORG"],
)

# 1) discovery
print("---- datasets ----")
datasets = client.datasets(environment="production")
for d in datasets:
    print(d.dataset, d.datasource)

# 2) schema (pick one dataset from discovery)
if datasets:
    ds = datasets[0].dataset
    print("\n---- schema ----", ds)
    schema = client.schema(ds, environment="production")
    print("fields:", schema.field_names[:10])

# 3) query lifecycle (this will poll+fetch inside execute)
print("\n---- execute ----")

ds = datasets[0].dataset if datasets else "customers"

schema = client.schema(ds, environment="production")
fields = schema.field_names[:3]  # pick a subset

print("dataset:", ds)
print("fields:", fields)

result = client.execute(
    dataset=ds,
    fields=fields,
    filters=None,
    limit=5,
    purpose="local sdk smoke test",
    requester_region="US",
)

print("row_count:", result.row_count)
print("data sample:", result.data)