# db_test.py - Save this file and run it locally
import mysql.connector
import sys

# Connection parameters
config = {
    'user': 'kc099',     # Replace with your MySQL username
    'password': 'Roboworks23!', # Replace with your MySQL password
    'host': '68.178.150.182',    # Your GoDaddy server IP
    'database': 'testdata', # Replace with your database name
    'port': 3306,                # MySQL port
    'connect_timeout': 10        # Timeout in seconds
}

print(f"Attempting to connect to MySQL server at {config['host']}:{config['port']}...")

try:
    # Attempt connection
    conn = mysql.connector.connect(**config)

    if conn.is_connected():
        print("Connected successfully!")

        # Connection info
        db_info = conn.get_server_info()
        print(f"MySQL Server version: {db_info}")

        # Execute test query
        cursor = conn.cursor()
        cursor.execute("SELECT 'Connection test successful!' as message")
        result = cursor.fetchone()
        print(f"Query result: {result[0]}")

        # Close connection
        cursor.close()
        conn.close()
        print("Connection closed.")

except mysql.connector.Error as err:
    print(f"Error: {err}")
    sys.exit(1)
