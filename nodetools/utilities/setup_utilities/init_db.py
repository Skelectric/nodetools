from sqlalchemy import create_engine, text, exc
import getpass
import argparse
from nodetools.utilities.credentials import CredentialManager
import sys
import subprocess
import platform
from nodetools.sql.sql_manager import SQLManager
import traceback
from typing import Optional, List
from nodetools.sql.schema_extension import SchemaExtension
from nodetools.configuration.configuration import get_node_config
import importlib
import os

def load_schema_extensions() -> Optional[List[SchemaExtension]]:
    """Load schema extensions from node config and environment"""
    extensions = []
    
    # Load from node config
    try:
        node_config = get_node_config()
        for ext_path in node_config.schema_extensions:
            try:
                module_path, class_name = ext_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                extension_class = getattr(module, class_name)
                extensions.append(extension_class())
            except Exception as e:
                print(f"Warning: Failed to load extension {ext_path}: {e}")
    except FileNotFoundError:
        print("No node configuration found. Skipping config-based extensions.")
    
    return extensions

def extract_node_name(postgres_key: str) -> str:
    """Extract node name from PostgreSQL credential key.
    
    Example: 'mynode_postgresconnstring_testnet' -> 'mynode'
            'mynode_postgresconnstring' -> 'mynode'
    """
    # Remove '_testnet' suffix if present
    base_key = postgres_key.replace('_testnet', '')
    # Remove '_postgresconnstring' suffix
    node_name = base_key.replace('_postgresconnstring', '')
    return node_name

def check_prerequisites() -> tuple[bool, list[str]]:
    """Check if all prerequisites are met for database initialization.
    
    Returns:
        tuple: (bool: all prerequisites met, list: error messages)
    """
    errors = []
    
    # Check if PostgreSQL is installed
    try:
        if platform.system() == 'Windows':
            subprocess.run(['where', 'psql'], check=True, capture_output=True)
        else:
            subprocess.run(['which', 'psql'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        errors.append("PostgreSQL is not installed or not in PATH. Please install PostgreSQL first.")
    
    # Check if PostgreSQL service is running
    try:
        if platform.system() == 'Windows':
            subprocess.run(['sc', 'query', 'postgresql'], check=True, capture_output=True)
        else:
            subprocess.run(['systemctl', 'status', 'postgresql'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        errors.append("PostgreSQL service is not running. Please start the PostgreSQL service.")
    
    # Check for psycopg2
    try:
        import psycopg2
    except ImportError:
        errors.append("psycopg2 is not installed. Please install it with: pip install psycopg2-binary")
    
    return len(errors) == 0, errors

def try_fix_permissions(user: str, db_name: str) -> bool:
    """Attempt to fix permissions by granting necessary privileges."""
    try:
        print(f"\nAttempting to grant privileges to user '{user}'...")
        sudo_password = getpass.getpass("Enter sudo password to grant database privileges: ")
        
        commands = [
            f'ALTER USER {user} WITH CREATEDB;',
            f'GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {user};',
            # Use -d flag instead of \c
            (f'GRANT ALL PRIVILEGES ON SCHEMA public TO {user};', db_name)
        ]
        
        for cmd in commands:
            if isinstance(cmd, tuple):
                # If command needs specific database
                command, database = cmd
                process = subprocess.Popen(
                    ['sudo', '-S', '-u', 'postgres', 'psql', '-d', database, '-c', command],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                # Regular command
                process = subprocess.Popen(
                    ['sudo', '-S', '-u', 'postgres', 'psql', '-c', cmd],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            stdout, stderr = process.communicate(input=sudo_password + '\n')
            
            if process.returncode != 0:
                print(f"Command failed: {stderr}")
                return False
                
        print(f"Successfully granted privileges to {user}")
        return True
            
    except Exception as e:
        print(f"Failed to fix permissions: {e}")
        print("\nIf automatic privilege granting failed, you can run these commands manually:")
        print(f"sudo -u postgres psql -c 'ALTER USER {user} WITH CREATEDB;'")
        print(f"sudo -u postgres psql -c 'GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {user};'")
        print(f"sudo -u postgres psql -d {db_name} -c 'GRANT ALL PRIVILEGES ON SCHEMA public TO {user};'")
        return False

def check_and_create_role(base_conn_string: str) -> tuple[bool, list[str]]:
    """Check database permissions and create postfiat role if needed.
    
    Args:
        base_conn_string: Connection string to postgres database
        
    Returns:
        tuple: (bool: success, list: error messages)
    """
    errors = []
    try:
        engine = create_engine(base_conn_string)
        with engine.connect() as conn:
            # Extract username from connection string
            user = base_conn_string.split('://')[1].split(':')[0]

            # Check if we have superuser privileges
            result = conn.execute(text("SELECT current_setting('is_superuser')")).scalar()
            is_superuser = (result.lower() == 'on')
            
            if not is_superuser:
                print(f"\nUser '{user}' needs superuser privileges for initial setup.")
                if input("Would you like to try to fix this automatically? (y/n): ").lower() == 'y':
                    if try_fix_permissions(user):
                        print("Permissions fixed! Please run this script again.")
                        sys.exit(0)
                
                errors.append(
                    "\nTo fix this manually, you can either:\n"
                    "1. Connect as the postgres superuser by modifying your connection string:\n"
                    "   postgresql://postgres:yourpassword@localhost:5432/postgres\n"
                    "2. Or grant superuser privileges to your current user with:\n"
                    "   sudo -u postgres psql -c 'ALTER USER your_username WITH SUPERUSER;'\n"
                    "\nAfter fixing permissions, run this script again."
                )
                return False, errors
            
            # Check if postfiat role exists, create if it doesn't
            result = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname='postfiat'")).first()
            if not result:
                try:
                    conn.execute(text("CREATE ROLE postfiat WITH LOGIN PASSWORD 'default_password'"))
                    print("Created 'postfiat' role with default password. Please change it!")
                except Exception as e:
                    errors.append(f"Failed to create postfiat role: {str(e)}")
            
            # Check if we can create databases
            try:
                conn.execute(text("CREATE DATABASE test_permissions"))
                conn.execute(text("DROP DATABASE test_permissions"))
            except Exception as e:
                errors.append(f"Connected user cannot create databases: {str(e)}")
                
    except Exception as e:
        errors.append(f"Failed to connect to PostgreSQL: {str(e)}")
    
    return len(errors) == 0, errors

def revoke_all_privileges(db_conn_string: str) -> None:
    """Revoke all privileges from a user for testing purposes."""
    try:
        # Extract username and database from connection string
        user = db_conn_string.split('://')[1].split(':')[0]
        db_name = db_conn_string.split('/')[-1]
        
        print(f"Revoking privileges from user '{user}'...")
        
        # These commands don't require the database to exist
        subprocess.run(['sudo', '-u', 'postgres', 'psql', '-c', 
                       f"ALTER USER {user} NOSUPERUSER NOCREATEDB;"], check=True)
        
        # Check if database exists before trying to revoke its privileges
        result = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-c',
                               f"SELECT 1 FROM pg_database WHERE datname = '{db_name}';"],
                              capture_output=True, text=True)
        
        if "1 row" in result.stdout:
            subprocess.run(['sudo', '-u', 'postgres', 'psql', '-c', 
                          f"REVOKE ALL PRIVILEGES ON DATABASE {db_name} FROM {user};"], check=True)
            subprocess.run(['sudo', '-u', 'postgres', 'psql', '-d', db_name, '-c',
                          f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {user};"], check=True)
            print(f"Database privileges revoked for {db_name}")
        else:
            print(f"Database {db_name} does not exist yet - skipping database-specific privileges")
        
        print("User privileges revoked successfully!")
        
    except subprocess.CalledProcessError as e:
        print(f"Error revoking privileges: {e}")

def create_database_if_needed(db_conn_string: str) -> bool:
    """Create the database if it doesn't exist.
    
    Args:
        db_conn_string: Full PostgreSQL connection string
        
    Returns:
        bool: True if database was created, False if it already existed
    """
    try:
        # Extract database name from connection string
        db_name = db_conn_string.split('/')[-1]
        
        # Create a connection string to the default postgres database
        base_conn = db_conn_string.rsplit('/', 1)[0] + '/postgres'
        engine = create_engine(base_conn)
        
        with engine.connect() as conn:
            # Don't recreate if it exists
            exists = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")).first() is not None
            if not exists:
                try:
                    # First try with current user
                    conn.execute(text("COMMIT"))
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    print(f"Created database: {db_name}")
                    return True
                except Exception as e:
                    if "permission denied to create database" in str(e):
                        print("Attempting to create database as postgres user...")
                        try:
                            subprocess.run(['sudo', '-u', 'postgres', 'createdb', db_name], check=True)
                            print(f"Successfully created database: {db_name}")
                            return True
                        except subprocess.CalledProcessError as e:
                            print(f"Failed to create database as postgres user: {e}")
                            return False
                    raise e
            return False
            
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

def init_database(drop_tables: bool = False, create_db: bool = False, schema_extensions: Optional[List[SchemaExtension]] = None):
    """Initialize the PostgreSQL database with required tables and views.
    
    Args:
        drop_tables: If True, drops and recreates tables. If False, only creates if not exist
                    and updates views/indices. Default False for safety.
    """
    try:
        # Check prerequisites first
        print("\nChecking prerequisites...")
        prereqs_met, errors = check_prerequisites()
        if not prereqs_met:
            print("\nPrerequisite checks failed:")
            for error in errors:
                print(f"- {error}")
            print("\nPlease fix these issues and try again.")
            return

        encryption_password = getpass.getpass("Enter your encryption password: ")
        cm = CredentialManager(password=encryption_password)

        # Get all credentials and find the PostgreSQL connection string
        all_creds = cm.list_credentials()
        postgres_keys = [key for key in all_creds if 'postgresconnstring' in key]

        if not postgres_keys:
            print("\nNo PostgreSQL connection strings found!")
            print("Please run setup_credentials.py first to configure your database credentials.")
            return
        
        sql_manager = SQLManager()

        for postgres_key in postgres_keys:
            # Extract node name from PostgreSQL credential key
            node_name = extract_node_name(postgres_key)
            network_type = "testnet" if "_testnet" in postgres_key else "mainnet"

            # Skip sigildb initialization
            if 'sigildb' in node_name.lower():
                print(f"\nSkipping initialization for {node_name} as it's a SigilDB instance...")
                continue
        
            print(f"\nInitializing database for {node_name} ({network_type})...")

            db_conn_string = cm.get_credential(postgres_key)

            if create_db:
                created = create_database_if_needed(db_conn_string)
                if created:
                    print("Database created successfully!")
                else:
                    print("Database already exists or couldn't be created.")
                    print("Attempting to continue with initialization...")

            # Create a new engine with the target database
            try:
                engine = create_engine(db_conn_string)
                with engine.connect() as conn:
                    # Test connection
                    conn.execute(text("SELECT 1"))
            except Exception as e:
                print(f"\nError connecting to database: {e}")
                print("Please ensure the database exists and you have proper permissions.")
                return

            engine = create_engine(db_conn_string)

            try:
                with engine.connect() as connection:

                    if drop_tables:
                        table_names = sql_manager.get_table_names('init', 'create_tables')

                        print(f"\nThe following {network_type} tables will be dropped:")
                        for table_name in table_names:
                            print(f"- {table_name}")
            
                        confirm = input(f"WARNING: This will drop existing {network_type} tables. Are you sure you want to continue? (y/n): ")
                        if confirm.lower() != "y":
                            print("Database initialization cancelled.")
                            return
                        
                        # Drop the tables
                        for table_name in table_names:
                            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE;"))
                            connection.commit()
                            print(f"✓ Dropped table: {table_name}")
                        print("\nAll tables dropped successfully.")

                    # Initialize core database objects in correct order
                    print("\nInitializing core database objects...")

                    # 1. Create Tables
                    print("- Creating tables...")
                    for stmt in sql_manager.load_statements('init', 'create_tables'):
                        connection.execute(text(stmt))
                        connection.commit()

                    # 2. Create Functions
                    print("- Creating functions...")
                    for stmt in sql_manager.load_statements('init', 'create_functions'):
                        connection.execute(text(stmt))
                        connection.commit()

                    # 3. Create Views
                    print("- Creating views...")
                    for stmt in sql_manager.load_statements('init', 'create_views'):
                        connection.execute(text(stmt))
                        connection.commit()

                    # 4. Create Triggers
                    print("- Creating triggers...")
                    for stmt in sql_manager.load_statements('init', 'create_triggers'):
                        connection.execute(text(stmt))
                        connection.commit()

                    # 5. Create Indices
                    print("- Creating indices...")
                    for stmt in sql_manager.load_statements('init', 'create_indices'):
                        connection.execute(text(stmt))
                        connection.commit()

                    # Grant privileges
                    print("- Granting table privileges...")
                    # Get actual table names from our SQLManager
                    table_names = sql_manager.get_table_names('init', 'create_tables')
                    for table in table_names:
                        connection.execute(text(f"GRANT ALL PRIVILEGES ON TABLE {table} TO postfiat;"))

                    # Grant view privileges
                    print("- Granting view privileges...")
                    result = connection.execute(text("""
                        SELECT format('GRANT SELECT ON %I TO postfiat;', viewname)
                        FROM pg_views
                        WHERE schemaname = 'public'
                    """))
                    for (grant_stmt,) in result:
                        connection.execute(text(grant_stmt))
                        connection.commit()

                    # Backfill triggers
                    print("\nBackfilling existing records for triggers...")
                    backfill_queries = [
                        # Add any backfill queries needed for triggers
                        "UPDATE postfiat_tx_cache SET hash = hash;",  # Trigger memo processing
                    ]
                    
                    for query in backfill_queries:
                        try:
                            connection.execute(text(query))
                            connection.commit()
                            print("✓ Successfully processed backfill query")
                        except Exception as e:
                            print(f"Warning: Backfill query failed: {e}")

                    if schema_extensions:
                        print(f"\nApplying schema extensions for {node_name}...")
                        for extension in schema_extensions:
                            print(f"Applying extension: {extension.__class__.__name__}")

                            # Follow same order as core schema
                            for step, statements in [
                                ("tables", extension.get_table_definitions()),
                                ("functions", extension.get_function_definitions()),
                                ("views", extension.get_view_definitions()),
                                ("triggers", extension.get_trigger_definitions()),
                                ("indices", extension.get_index_definitions())
                            ]:
                                if statements:
                                    print(f"- Creating {step}...")
                                    for statement in statements:
                                        connection.execute(text(statement))
                                        connection.commit()

                            # Grant privileges
                            for table, privilege in extension.get_privileges():
                                connection.execute(text(f"GRANT {privilege} ON TABLE {table} TO postfiat;"))
                                connection.commit()

                    # Get lists of objects we expect from our SQL files
                    expected_tables = sql_manager.get_table_names('init', 'create_tables')
                    expected_functions = sql_manager.get_function_names('init', 'create_functions')
                    expected_views = sql_manager.get_view_names('init', 'create_views')
                    expected_triggers = sql_manager.get_trigger_names('init', 'create_triggers')
                    expected_indices = sql_manager.get_index_names('init', 'create_indices')

                    # Add expected objects from schema extensions
                    if schema_extensions:
                        for extension in schema_extensions:
                            # For each extension, parse its SQL statements to get object names
                            extension_tables = sql_manager.get_table_names_from_statements(
                                extension.get_table_definitions())
                            extension_functions = sql_manager.get_function_names_from_statements(
                                extension.get_function_definitions())
                            extension_views = sql_manager.get_view_names_from_statements(
                                extension.get_view_definitions())
                            extension_triggers = sql_manager.get_trigger_names_from_statements(
                                extension.get_trigger_definitions())
                            extension_indices = sql_manager.get_index_names_from_statements(
                                extension.get_index_definitions())
                            
                            expected_tables.extend(extension_tables)
                            expected_functions.extend(extension_functions)
                            expected_views.extend(extension_views)
                            expected_triggers.extend(extension_triggers)
                            expected_indices.extend(extension_indices)

                    # Verify schema
                    print("\nVerifying schema...")
                    verify_schema_query = sql_manager.load_query('init', 'verify_schema')
                    verify_schema_params = {
                        'expected_tables': expected_tables,
                        'expected_functions': expected_functions,
                        'expected_views': expected_views,
                        'expected_triggers': expected_triggers,
                        'expected_indices': expected_indices,
                        'all_expected': expected_tables + expected_functions + expected_views + 
                                      expected_triggers + expected_indices                   
                    }
                    result = connection.execute(text(verify_schema_query), verify_schema_params)
                    schema_info = result.fetchall()
                    
                    for object_type, count, objects, expected_count in schema_info:
                        print(f"\n{object_type}s ({count} created):")
                        for obj in objects:
                            print(f"  - {obj}")
                        
                        # Get the expected list for this type
                        expected = {
                            'Table': expected_tables,
                            'Function': expected_functions,
                            'View': expected_views,
                            'Trigger': expected_triggers,
                            'Index': expected_indices
                        }[object_type]
                        
                        # Check if any expected objects are missing
                        missing = set(expected) - set(objects)
                        if missing:
                            print(f"  WARNING: Missing {object_type.lower()}s:")
                            for obj in missing:
                                print(f"  - {obj}")

                    print("\nDatabase initialization completed successfully!")
                    print("Status:")
                    print(f"- Tables configured (drop_tables={drop_tables})")
                    print("- Functions created")
                    print("- Triggers created and backfilled")
                    print("- Indices updated")
                    print("- Views updated")

            except Exception as e:
                if "permission denied for schema public" in str(e):
                    print("\nPermission denied. The database exists but your user needs additional privileges.")
                    user = db_conn_string.split('://')[1].split(':')[0]
                    db_name = db_conn_string.split('/')[-1]
                    if try_fix_permissions(user, db_name):
                        print("\nPermissions fixed! Retrying initialization...")
                        return init_database(drop_tables=drop_tables, create_db=create_db)
                print(f"Error initializing database: {e}")
                return

    except Exception as e:
        print(f"Error initializing database: {e}")
        print(traceback.format_exc())

def print_prerequisites():
    """Print prerequisites information."""
    print("""
        Prerequisites for database initialization:
        ----------------------------------------
        1. PostgreSQL must be installed
        2. PostgreSQL service must be running
        3. psycopg2 must be installed (pip install psycopg2-binary)
        4. User must have superuser privileges in PostgreSQL
        5. Network configuration must be set up

        For Ubuntu/Debian:
        sudo apt-get update
        sudo apt-get install postgresql postgresql-contrib

        For Windows:
        Download and install from: https://www.postgresql.org/download/windows/
        """)

def main(drop_tables=False, create_db=False, help_install=False, revoke_privileges=False):
    """Entry point for CLI command
    
    Args:
        drop_tables (bool): Drop and recreate tables if True
        create_db (bool): Create database if it doesn't exist
        help_install (bool): Show installation prerequisites
        revoke_privileges (bool): Revoke privileges for testing
    """
    try:

        if help_install:
            print_prerequisites()
            sys.exit(0)
        
        if revoke_privileges:
            # Get credentials and revoke privileges
            encryption_password = getpass.getpass("Enter your encryption password: ")
            cm = CredentialManager(password=encryption_password)
            postgres_keys = [key for key in cm.list_credentials() if 'postgresconnstring' in key]
            
            for key in postgres_keys:
                db_conn_string = cm.get_credential(key)
                revoke_all_privileges(db_conn_string)
            sys.exit(0)

        schema_extensions = load_schema_extensions()
        init_database(drop_tables=drop_tables, create_db=create_db, schema_extensions=schema_extensions)

    except KeyboardInterrupt:
        print("\nDatabase initialization cancelled.")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the NodeTools database.")
    parser.add_argument("--drop-tables", action="store_true", help="Drop and recreate tables (WARNING: Destructive)")
    parser.add_argument("--create-db", action="store_true", help="Create the database if it doesn't exist")
    parser.add_argument("--help-install", action="store_true", help="Show installation prerequisites")
    parser.add_argument("--revoke-privileges", action="store_true", help="Revoke privileges for testing (WARNING: Destructive)")
    args = parser.parse_args()
    
    main(
        drop_tables=args.drop_tables,
        create_db=args.create_db,
        help_install=args.help_install,
        revoke_privileges=args.revoke_privileges
    )
