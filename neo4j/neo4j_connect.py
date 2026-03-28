from neo4j import GraphDatabase

# connection details
uri = "bolt://localhost:7687"
username = "neo4j"
password = "password"   # docker la potta password

driver = GraphDatabase.driver(uri, auth=(username, password))


# 🔹 Step 1: check connection
def check():
    with driver.session() as session:
        result = session.run("RETURN 'Connected' AS msg")
        for r in result:
            print(r["msg"])


# 🔹 Step 2: create data
def create_data():
    with driver.session() as session:
        session.run("""
        CREATE (a:Account {name:'A'})
        CREATE (b:Account {name:'B'})
        CREATE (a)-[:SEND {amount:15000}]->(b)
        """)


# 🔹 Step 3: detect fraud
def detect_fraud():
    with driver.session() as session:
        result = session.run("""
        MATCH (a)-[t:SEND]->(b)
        WHERE t.amount > 10000
        RETURN a.name AS sender, b.name AS receiver, t.amount AS amount
        """)

        for r in result:
            print(r["sender"], "->", r["receiver"], ":", r["amount"])


# 🔹 Run functions
check()
create_data()
detect_fraud()