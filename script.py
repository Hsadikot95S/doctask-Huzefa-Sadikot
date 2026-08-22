from packages.db import models
from packages.db.database import Base

for name, table in sorted(Base.metadata.tables.items()):
    print(f'\n=== {name} ===')

    print('COLUMNS:')
    for c in table.columns:
        print(f'  {c.name}: {c.type}')

    print('PRIMARY KEY:', [c.name for c in table.primary_key.columns])

    print('FOREIGN KEYS:')
    for fk in table.foreign_keys:
        print(f'  {fk.parent} -> {fk.target_fullname}')

    print('UNIQUE CONSTRAINTS:')
    for c in table.constraints:
        if c.__class__.__name__ == 'UniqueConstraint':
            print(f'  {[x.name for x in c.columns]}')

    print('INDEXES:')
    for idx in table.indexes:
        print(f'  {idx.name}: {[x.name for x in idx.columns]}')

