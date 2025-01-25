# nodetools

Post Fiat Foundation tools for node setup and management.

## Prerequisites

- Ubuntu operating system
- Python 3.11 or greater
- PostgreSQL 16 or greater with pgvector extension

## Installation Guide


### 1. Install pgvector Extension

First, install the required build dependencies:

```bash
sudo apt install build-essential postgresql-server-dev-16
```

Clone and build the pgvector repository:

```bash
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```


### 2. Install NodeTools

Add NodeTools as a dependency to your Python project's `setup.py`:

```python
install_requires=[
'nodetools @ git+https://github.com/Skelectric/nodetools.git',
# ... other dependencies
]
```

Install your project in development mode:

```bash
pip install -e .
```

### 3. Node Configuration

1. Run the node setup command:
```bash
nodetools setup-node
```

You will be prompted to provide:
- XRPL private key
- OpenRouter API key
- PostgreSQL database connection string

2. Initialize the database:

```bash
nodetools init-db
```

This will:
- Create the database `postfiat_db_testnet`
- Create the `postfiat` user
- Set up the required schema

### 4. Database Configuration

Connect to the database as postgres superuser:

```bash
bash
sudo -u postgres psql postfiat_db_testnet
```

Once connected, create the pgvector extension:

```sql
CREATE EXTENSION vector;
```

