from mcp.server.fastmcp import FastMCP
import os
import pymysql

mcp = FastMCP("mysql-server")

def _connect():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "123456"),
        database=os.getenv("MYSQL_DATABASE", "test"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

@mcp.tool()
def mysql_query(sql: str):
    """Run SQL query"""
    try:
        conn = _connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        finally:
            conn.close()
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run()
