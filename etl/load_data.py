from cassandra.cluster import Cluster

cluster = Cluster(['192.168.0.24'])
print("Starting Cassandra cluster...")
session = cluster.connect()
session.set_keyspace('air_quality')


session.shutdown()
print("Cassandra cluster shutdown")